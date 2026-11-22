import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from storygraph.services.chatgpt_login import (
    ChatGPTLoginError, ChatGPTLoginService, WindowsDPAPI, ISSUER, JWKS, TOKEN,
    RESOURCE, SCOPES, _request_json,
)


class SyntheticProtector:
    supported = True

    def protect(self, value):
        return base64.b64encode(value)

    def unprotect(self, value):
        return base64.b64decode(value)


@pytest.fixture
def setup_service(tmp_path):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk['kid'] = 'test-key'
    urls, calls = [], []
    service = None

    def request(url, form=None, **kwargs):
        calls.append((url, form))
        if url == JWKS:
            return {'keys': [jwk]}
        if url == TOKEN:
            attempt = list(service._attempts.values())[-1]
            claims = {'sub': 'synthetic-subject', 'iss': ISSUER, 'aud': form['client_id'],
                      'iat': int(time.time()), 'exp': int(time.time()) + 3600,
                      'nonce': attempt.get('nonce'), 'email': 'synthetic@example.invalid'}
            return {'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh',
                    'id_token': jwt.encode(claims, private, algorithm='RS256', headers={'kid': 'test-key'}),
                    'scope': SCOPES, 'token_type': 'Bearer', 'expires_in': 3600}
        return {'issuer': ISSUER, 'revocation_endpoint': ISSUER + '/api/accounts/oauth/revoke'}

    service = ChatGPTLoginService(tmp_path, protector=SyntheticProtector(), request_json=request,
                                  browser_open=lambda url: urls.append(url) or True)
    yield service, urls, calls, private
    service.close()


def complete(service):
    result = service.begin_login()
    attempt = service._attempts[result['attempt_id']]
    service._complete(attempt, {'state': [attempt['state']], 'code': ['synthetic-code'],
                                'client_id': ['oaiapp_synthetic']})
    return result['attempt_id'], service.status()['active_account_id']


def test_dynamic_pkce_host_identity_and_no_browser_credentials(setup_service):
    service, urls, calls, _ = setup_service
    attempt_id, account_id = complete(service)
    query = parse_qs(urlsplit(urls[0]).query)
    assert query['client_id'] == ['dynamic_agent_client']
    assert query['resource'] == [RESOURCE]
    assert query['agent_name_hint'] == ['StoryGraph Agent']
    assert query['code_challenge_method'] == ['S256']
    assert query['redirect_uri'][0].startswith('http://127.0.0.1:')
    exchange = next(form for url, form in calls if url == TOKEN)
    assert exchange['client_id'] == 'oaiapp_synthetic'
    assert exchange['redirect_uri'] == query['redirect_uri'][0]
    assert service.login_status(attempt_id)['status'] == 'completed'
    status = service.status()
    assert status['accounts'][0]['welcome_pending']
    assert service.access_token(account_id) == 'synthetic-access'
    assert 'synthetic-access' not in json.dumps(status)
    assert 'synthetic-refresh' not in urls[0]
    service.acknowledge_welcome(account_id)
    service.begin_login(account_id)
    returning = parse_qs(urlsplit(urls[-1]).query)
    assert returning['client_id'] == ['oaiapp_synthetic']
    assert returning['ext_agent_host_id'] == query['ext_agent_host_id']
    assert 'agent_name_hint' not in returning
    assert 'id_token_hint' not in returning
    assert not service.status()['accounts'][0]['welcome_pending']


@pytest.mark.parametrize('mutation', ['signature', 'issuer', 'audience', 'expiry', 'nonce'])
def test_reject_unverified_id_tokens(setup_service, mutation):
    service, _, _, private = setup_service
    claims = {'sub': 'synthetic', 'iss': ISSUER, 'aud': 'oaiapp_synthetic',
              'iat': int(time.time()), 'exp': int(time.time()) + 1000, 'nonce': 'expected'}
    if mutation == 'issuer':
        claims['iss'] = 'https://attacker.invalid'
    if mutation == 'audience':
        claims['aud'] = 'oaiapp_other'
    if mutation == 'expiry':
        claims['exp'] = int(time.time()) - 100
    if mutation == 'nonce':
        claims['nonce'] = 'other'
    if mutation == 'signature':
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims, private, algorithm='RS256', headers={'kid': 'test-key'})
    with pytest.raises(ChatGPTLoginError, match='identity_verification_failed'):
        service._verify_id(token, 'oaiapp_synthetic', 'expected')


@pytest.mark.parametrize('query,category', [
    ({'state': ['wrong'], 'code': ['secret']}, 'state_mismatch'),
    ({'error': ['access_denied']}, 'authorization_denied'),
    ({'code': ['secret']}, 'registration_incomplete'),
    ({'code': ['secret'], 'client_id': ['dynamic_agent_client']}, 'registration_incomplete'),
    ({'code': ['secret', 'again']}, 'invalid_callback'),
])
def test_invalid_callbacks_never_exchange(setup_service, query, category):
    service, _, calls, _ = setup_service
    result = service.begin_login()
    attempt = service._attempts[result['attempt_id']]
    query.setdefault('state', [attempt['state']])
    with pytest.raises(ChatGPTLoginError) as error:
        service._complete(attempt, query)
    assert error.value.category == category
    assert not calls
    assert service.status()['accounts'] == []


def test_cross_service_refresh_is_serialized_and_rotation_atomic(setup_service):
    service, _, _, _ = setup_service
    _, account_id = complete(service)
    with service._lock():
        data = service._load()
        data['accounts'][account_id]['expires_at'] = 0
        service._save(data)
    rotations = []

    def rotate(url, form=None):
        assert form['refresh_token'] == 'synthetic-refresh'
        assert 'scope' not in form
        rotations.append(form)
        time.sleep(.05)
        return {'access_token': 'rotated-access', 'refresh_token': 'rotated-refresh',
                'token_type': 'Bearer', 'expires_in': 3600}

    other = ChatGPTLoginService(service.directory, protector=SyntheticProtector(), request_json=rotate)
    service._request = rotate
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(lambda svc: svc.access_token(account_id), [service, other]))
    assert result == ['rotated-access', 'rotated-access']
    assert len(rotations) == 1
    assert other._load()['accounts'][account_id]['refresh_token'] == 'rotated-refresh'


def test_missing_scope_and_explicit_unknown_account_fail_closed(setup_service):
    service, _, calls, _ = setup_service
    _, account_id = complete(service)
    with service._lock():
        data = service._load()
        data['accounts'][account_id]['scopes'] = ['openid']
        service._save(data)
    before = len(calls)
    with pytest.raises(ChatGPTLoginError, match='plan_permission_required'):
        service.access_token(account_id)
    with pytest.raises(ChatGPTLoginError, match='sign_in_required'):
        service.access_token('unknown')
    assert not service.account_ready(account_id)
    assert len(calls) == before


def test_logout_retains_mapping_clears_tokens_and_reports_failed_revoke(setup_service):
    service, _, _, _ = setup_service
    _, account_id = complete(service)
    service._request = lambda *args, **kwargs: (_ for _ in ()).throw(OSError('private failure'))
    result = service.unlink(account_id)
    assert not result['remote_revocation_confirmed']
    record = service._load()['accounts'][account_id]
    assert record['client_id'] == 'oaiapp_synthetic'
    assert not {'access_token', 'refresh_token', 'id_token'}.intersection(record)
    assert service.status()['active_account_id'] is None


@pytest.mark.skipif(os.name != 'nt', reason='Windows DPAPI integration')
def test_windows_dpapi_ciphertext_at_rest(tmp_path):
    protector = WindowsDPAPI()
    plain = b'synthetic-credential-never-an-author-token'
    encrypted = protector.protect(plain)
    assert plain not in encrypted
    assert protector.unprotect(encrypted) == plain
    service = ChatGPTLoginService(tmp_path)
    with service._lock():
        data = service._load()
        data['synthetic'] = plain.decode()
        service._save(data)
    assert plain not in (tmp_path / 'credentials.dpapi').read_bytes()
    assert service._load()['synthetic'] == plain.decode()


def test_non_windows_storage_explicitly_unsupported(tmp_path):
    protector = SyntheticProtector()
    protector.supported = False
    service = ChatGPTLoginService(tmp_path, protector=protector)
    assert not service.status()['supported']
    with pytest.raises(ChatGPTLoginError, match='secure_storage_unsupported'):
        service.begin_login()


@pytest.mark.parametrize('url', ['http://auth.openai.com/token', 'https://attacker.invalid/token',
                                'https://auth.openai.com@attacker.invalid/token'])
def test_network_refuses_untrusted_endpoints(url):
    with pytest.raises(ChatGPTLoginError, match='unsafe_endpoint'):
        _request_json(url, {'token': 'synthetic'})

def test_forged_state_leaves_real_attempt_usable(setup_service):
    service, _, _, _ = setup_service
    result = service.begin_login()
    attempt = service._attempts[result['attempt_id']]
    with pytest.raises(ChatGPTLoginError, match='state_mismatch'):
        service._complete(attempt, {'state': ['forged'], 'code': ['ignored']})
    assert service.login_status(result['attempt_id'])['status'] == 'pending'
    service._complete(attempt, {'state': [attempt['state']], 'code': ['valid'],
                               'client_id': ['oaiapp_synthetic']})
    assert service.login_status(result['attempt_id'])['status'] == 'completed'


def test_failed_exchange_retains_unverified_issued_client_for_retry(setup_service):
    service, urls, _, _ = setup_service
    service._request = lambda *args, **kwargs: (_ for _ in ()).throw(
        ChatGPTLoginError('authorization_expired'))
    result = service.begin_login()
    attempt = service._attempts[result['attempt_id']]
    with pytest.raises(ChatGPTLoginError):
        service._complete(attempt, {'state': [attempt['state']], 'code': ['expired'],
                                   'client_id': ['oaiapp_synthetic']})
    status = service.status()
    assert status['active_account_id'] is None
    pending = status['accounts'][0]
    assert not pending['connected'] and not pending['plan_enabled']
    service.begin_login(pending['account_id'])
    assert parse_qs(urlsplit(urls[-1]).query)['client_id'] == ['oaiapp_synthetic']


def test_cross_process_logout_cannot_be_reversed_by_pending_callback(setup_service):
    service, _, _, _ = setup_service
    _, account_id = complete(service)
    result = service.begin_login(account_id)
    attempt = service._attempts[result['attempt_id']]
    other = ChatGPTLoginService(service.directory, protector=SyntheticProtector(),
                               request_json=lambda *args, **kwargs: {})
    other.unlink(account_id)
    with pytest.raises(ChatGPTLoginError, match='authorization_superseded'):
        service._complete(attempt, {'state': [attempt['state']], 'code': ['stale']})
    assert not service.status()['accounts'][0]['connected']
