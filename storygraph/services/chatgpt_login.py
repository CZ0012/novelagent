"""Official local ChatGPT OAuth. Only Windows DPAPI credential storage is supported."""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import jwt
from filelock import FileLock

ISSUER = "https://auth.openai.com"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN = ISSUER + "/api/accounts/oauth/token"
DISCOVERY = ISSUER + "/.well-known/openid-configuration"
JWKS = ISSUER + "/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPES = {"resource.invoke", "chatgpt.tokens.use.direct"}


class ChatGPTLoginError(RuntimeError):
    def __init__(self, category):
        self.category = category
        super().__init__(f"ChatGPT sign-in [{category}]. Please reconnect or try again.")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request_json(url, form=None, *, empty_ok=False):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != "auth.openai.com"
            or parts.query or parts.fragment):
        raise ChatGPTLoginError("unsafe_endpoint")
    request = Request(url, data=urlencode(form).encode() if form is not None else None,
                      headers={"Accept": "application/json", **(
                          {"Content-Type": "application/x-www-form-urlencoded"}
                          if form is not None else {})})
    try:
        with build_opener(_NoRedirect).open(request, timeout=20) as response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ChatGPTLoginError("invalid_response")
            if not raw and empty_ok:
                return {}
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ChatGPTLoginError("invalid_response")
            return result
    except HTTPError as exc:
        raise ChatGPTLoginError("authorization_expired" if exc.code in (400, 401, 403)
                                else "service_unavailable") from None
    except ChatGPTLoginError:
        raise
    except Exception:
        raise ChatGPTLoginError("connection_error") from None


class WindowsDPAPI:
    supported = os.name == "nt"

    def _crypt(self, data, decrypt):
        if not self.supported:
            raise ChatGPTLoginError("secure_storage_unsupported")
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

        buffer = ctypes.create_string_buffer(data)
        incoming = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        outgoing = Blob()
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
        function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                             ctypes.POINTER(Blob)]
        function.restype = wintypes.BOOL
        if not function(ctypes.byref(incoming), None, None, None, None, 1,
                        ctypes.byref(outgoing)):
            raise ChatGPTLoginError("secure_storage_error")
        try:
            return ctypes.string_at(outgoing.data, outgoing.size)
        finally:
            kernel32.LocalFree(outgoing.data)

    def protect(self, data):
        return self._crypt(data, False)

    def unprotect(self, data):
        return self._crypt(data, True)


def default_chatgpt_storage_dir():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "StoryGraph" / "chatgpt"


class ChatGPTLoginService:
    def __init__(self, storage_dir=None, *, protector=None, request_json=None,
                 browser_open=None, clock=None):
        self.directory = Path(storage_dir or default_chatgpt_storage_dir()).resolve()
        self.protector = protector or WindowsDPAPI()
        self._request = request_json or _request_json
        self._browser_open = browser_open or webbrowser.open
        self._clock = clock or time.time
        self._attempts = {}
        self._mutex = threading.RLock()
        self._jwks_cache = None
        self._jwks_at = 0

    def _lock(self):
        if not self.protector.supported:
            raise ChatGPTLoginError("secure_storage_unsupported")
        self.directory.mkdir(parents=True, exist_ok=True)
        return FileLock(str(self.directory / "credentials.lock"), timeout=30)

    def _load(self):
        path = self.directory / "credentials.dpapi"
        if not path.exists():
            return {"host_id": "urn:uuid:" + str(uuid.uuid4()), "accounts": {}, "active": None}
        try:
            return json.loads(self.protector.unprotect(path.read_bytes()))
        except Exception:
            raise ChatGPTLoginError("secure_storage_error") from None

    def _save(self, data):
        encrypted = self.protector.protect(json.dumps(data).encode())
        fd, name = tempfile.mkstemp(prefix="credential-", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.directory / "credentials.dpapi")
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def status(self):
        if not self.protector.supported:
            return {"supported": False, "accounts": [], "active_account_id": None,
                    "error": "secure_storage_unsupported"}
        with self._lock():
            data = self._load()
            accounts = []
            for account_id, item in data["accounts"].items():
                connected = bool(item.get("access_token"))
                accounts.append({"account_id": account_id, "client_id": item["client_id"],
                                 "email": item.get("email"), "label": item["label"],
                                 "connected": connected,
                                 "plan_enabled": connected and PLAN_SCOPES.issubset(item.get("scopes", [])),
                                 "welcome_pending": item.get("welcome_pending", False)})
            return {"supported": True, "accounts": accounts, "active_account_id": data["active"]}

    def account_ready(self, account_id=None):
        state = self.status()
        chosen = account_id if account_id is not None else state["active_account_id"]
        return any(a["account_id"] == chosen and a["connected"] and a["plan_enabled"]
                   for a in state["accounts"])

    def select_account(self, account_id):
        with self._lock():
            data = self._load()
            if account_id not in data["accounts"]:
                raise ChatGPTLoginError("account_not_found")
            data["active"] = account_id
            self._save(data)
        return self.status()

    def acknowledge_welcome(self, account_id):
        with self._lock():
            data = self._load()
            if account_id not in data["accounts"]:
                raise ChatGPTLoginError("account_not_found")
            data["accounts"][account_id]["welcome_pending"] = False
            self._save(data)
        return self.status()

    def begin_login(self, account_id=None):
        with self._mutex:
            if any(a["status"] == "pending" for a in self._attempts.values()):
                raise ChatGPTLoginError("login_in_progress")
            with self._lock():
                data = self._load()
                previous = data["accounts"].get(account_id) if account_id is not None else None
                if account_id is not None and previous is None:
                    raise ChatGPTLoginError("account_not_found")
                data['auth_epoch'] = data.get('auth_epoch', 0) + 1
                self._save(data)
            attempt_id = secrets.token_urlsafe(24)
            attempt = {"attempt_id": attempt_id, "status": "pending", "state": secrets.token_urlsafe(32),
                       "nonce": secrets.token_urlsafe(32), "verifier": secrets.token_urlsafe(64),
                       "expires": self._clock() + 600, "account_id": account_id,
                       "previous": dict(previous) if previous else None}
            attempt['auth_epoch'] = data['auth_epoch']
            service = self

            class CallbackHandler(BaseHTTPRequestHandler):
                def setup(self):
                    self.request.settimeout(3)
                    super().setup()

                def log_message(self, *args):
                    pass

                def do_GET(self):
                    expected_host = f"127.0.0.1:{self.server.server_port}"
                    if (self.headers.get("Host") != expected_host or
                            urlsplit(self.path).path != "/auth/callback" or len(self.path) > 16384):
                        self.send_error(400)
                        return
                    try:
                        service._complete(attempt, parse_qs(urlsplit(self.path).query,
                                                          keep_blank_values=True, max_num_fields=20))
                        message = b"Sign-in completed. You can close this window."
                    except Exception:
                        message = b"Sign-in could not be completed. Return to StoryGraph."
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
                    self.end_headers()
                    self.wfile.write(message)

            server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
            server.daemon_threads = True
            server.timeout = 0.25
            attempt["server"] = server
            attempt["redirect"] = f"http://127.0.0.1:{server.server_port}/auth/callback"
            self._attempts[attempt_id] = attempt
            params = {"client_id": previous["client_id"] if previous else "dynamic_agent_client",
                      "ext_agent_host_id": data["host_id"], "response_type": "code",
                      "redirect_uri": attempt["redirect"], "scope": SCOPES, "resource": RESOURCE,
                      "state": attempt["state"], "nonce": attempt["nonce"],
                      "code_challenge_method": "S256",
                      "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(
                          attempt["verifier"].encode()).digest()).decode().rstrip("=")}
            if previous is None:
                params["agent_name_hint"] = "StoryGraph Agent"
            # The optional id_token_hint is omitted to keep all tokens out of browser URLs.
            def listen():
                try:
                    while attempt["status"] == "pending" and self._clock() < attempt["expires"]:
                        server.handle_request()
                    with self._mutex:
                        if attempt["status"] == "pending":
                            attempt["status"] = "expired"
                finally:
                    server.server_close()
                    for secret in ("state", "nonce", "verifier", "previous"):
                        attempt.pop(secret, None)

            threading.Thread(target=listen, daemon=True, name="chatgpt-loopback").start()
            try:
                if not self._browser_open(AUTHORIZE + "?" + urlencode(params)):
                    raise ChatGPTLoginError("browser_unavailable")
            except Exception:
                attempt["status"] = "failed"
                attempt["error"] = "browser_unavailable"
            return self.login_status(attempt_id)

    def login_status(self, attempt_id):
        with self._mutex:
            attempt = self._attempts.get(attempt_id)
            if attempt is None:
                raise ChatGPTLoginError("attempt_not_found")
            return {key: attempt[key] for key in ("attempt_id", "status", "error", "account_id")
                    if key in attempt}

    def cancel_login(self, attempt_id):
        with self._mutex:
            attempt = self._attempts.get(attempt_id)
            if attempt is None:
                raise ChatGPTLoginError("attempt_not_found")
            if attempt["status"] == "pending":
                attempt["status"] = "cancelled"
            return self.login_status(attempt_id)

    def close(self):
        with self._mutex:
            for attempt in self._attempts.values():
                if attempt["status"] == "pending":
                    attempt["status"] = "cancelled"

    def _verify_id(self, token, client_id, nonce=None):
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise ValueError()
            if self._jwks_cache is None or self._clock() - self._jwks_at > 3600:
                self._jwks_cache = self._request(JWKS)
                self._jwks_at = self._clock()
            keys = [k for k in self._jwks_cache.get("keys", []) if k.get("kid") == header["kid"]]
            if not keys:
                self._jwks_cache = self._request(JWKS)
                self._jwks_at = self._clock()
                keys = [k for k in self._jwks_cache.get("keys", []) if k.get("kid") == header["kid"]]
            if len(keys) != 1:
                raise ValueError()
            claims = jwt.decode(token, jwt.PyJWK.from_dict(keys[0], algorithm="RS256").key,
                                algorithms=["RS256"], audience=client_id, issuer=ISSUER,
                                leeway=5, options={"require": ["sub", "iat", "exp"]})
            if not isinstance(claims["sub"], str) or not claims["sub"]:
                raise ValueError()
            if nonce is not None and not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
                raise ValueError()
            if isinstance(claims.get("aud"), list) and len(claims["aud"]) > 1 and claims.get("azp") != client_id:
                raise ValueError()
            return claims
        except Exception:
            raise ChatGPTLoginError("identity_verification_failed") from None

    def _token_record(self, response, old=None):
        if response.get("token_type", "").lower() != "bearer":
            raise ChatGPTLoginError("invalid_token_response")
        for key in ("access_token", "refresh_token"):
            if not isinstance(response.get(key), str) or not response[key] or len(response[key]) > 32768:
                raise ChatGPTLoginError("invalid_token_response")
        expiry = response.get("expires_in")
        if isinstance(expiry, bool) or not isinstance(expiry, (int, float)) or not 0 < expiry <= 86400:
            raise ChatGPTLoginError("invalid_token_response")
        scope = response.get("scope")
        if scope is None and old is not None:
            scopes = old["scopes"]
        elif isinstance(scope, str) and len(scope) <= 4096:
            scopes = scope.split()
        else:
            raise ChatGPTLoginError("invalid_token_response")
        return {"access_token": response["access_token"], "refresh_token": response["refresh_token"],
                "scopes": scopes, "expires_at": self._clock() + expiry,
                "earliest_refresh_at": response.get("earliest_refresh_at", 0)}

    def _complete(self, attempt, query):
        with self._mutex:
            try:
                if attempt["status"] != "pending" or self._clock() >= attempt["expires"]:
                    raise ChatGPTLoginError("attempt_expired")
                if any(len(v) != 1 for v in query.values()):
                    raise ChatGPTLoginError("invalid_callback")
                if not secrets.compare_digest(query.get("state", [""])[0], attempt["state"]):
                    raise ChatGPTLoginError("state_mismatch")
                if "error" in query:
                    raise ChatGPTLoginError("authorization_denied")
                previous = attempt["previous"]
                client_id = query.get("client_id", [previous["client_id"] if previous else ""])[0]
                if not re.fullmatch(r"oaiapp_[A-Za-z0-9_-]{1,200}", client_id):
                    raise ChatGPTLoginError("registration_incomplete")
                if previous and previous["client_id"] != client_id:
                    raise ChatGPTLoginError("account_mismatch")
                code = query.get("code", [""])[0]
                if not code or len(code) > 16384:
                    raise ChatGPTLoginError("invalid_callback")
                with self._lock():
                    if self._load().get('auth_epoch', 0) != attempt['auth_epoch']:
                        raise ChatGPTLoginError('authorization_superseded')
                # Retain an issued registration after a failed exchange, without
                # claiming an identity or activating unverified credentials.
                if previous is None:
                    pending_id = 'pending-' + hashlib.sha256(client_id.encode()).hexdigest()[:24]
                    with self._lock():
                        pending_data = self._load()
                        if pending_data.get('auth_epoch', 0) != attempt['auth_epoch']:
                            raise ChatGPTLoginError('authorization_superseded')
                        pending_data['accounts'].setdefault(pending_id, {
                            'client_id': client_id, 'label': 'ChatGPT registration ' + pending_id[-8:],
                            'welcome_pending': False})
                        self._save(pending_data)
                response = self._request(TOKEN, {"grant_type": "authorization_code", "client_id": client_id,
                    "code": code, "code_verifier": attempt["verifier"], "redirect_uri": attempt["redirect"],
                    "resource": RESOURCE})
                claims = self._verify_id(response.get("id_token", ""), client_id, attempt["nonce"])
                if previous and previous.get('subject') and claims["sub"] != previous["subject"]:
                    raise ChatGPTLoginError("account_mismatch")
                record = self._token_record(response)
                account_id = hashlib.sha256((ISSUER + "|" + client_id + "|" + claims["sub"]).encode()).hexdigest()[:32]
                with self._lock():
                    data = self._load()
                    if data.get('auth_epoch', 0) != attempt['auth_epoch']:
                        raise ChatGPTLoginError('authorization_superseded')
                    existing = data["accounts"].get(account_id)
                    record.update({"client_id": client_id, "subject": claims["sub"], "issuer": ISSUER,
                        "email": claims.get("email") if isinstance(claims.get("email"), str) else None,
                        "label": "ChatGPT " + account_id[:8], "id_token": response["id_token"],
                        "welcome_pending": existing.get("welcome_pending", False) if existing else True})
                    data["accounts"][account_id] = record
                    if previous and not previous.get('subject'):
                        data['accounts'].pop(attempt['account_id'], None)
                    data['accounts'].pop('pending-' + hashlib.sha256(client_id.encode()).hexdigest()[:24], None)
                    data["active"] = account_id
                    self._save(data)
                attempt["account_id"] = account_id
                attempt["status"] = "completed"
            except ChatGPTLoginError as exc:
                if exc.category in ('state_mismatch', 'invalid_callback'):
                    # A forged callback must not consume the legitimate attempt.
                    raise
                if attempt['status'] != 'pending':
                    raise
                attempt["status"] = "failed"
                attempt["error"] = exc.category
                raise
            except Exception:
                attempt["status"] = "failed"
                attempt["error"] = "sign_in_failed"
                raise ChatGPTLoginError("sign_in_failed") from None

    def access_token(self, account_id=None):
        # Encompass read, refresh and atomic replacement across API/CLI processes.
        with self._lock():
            data = self._load()
            chosen = account_id if account_id is not None else data["active"]
            item = data["accounts"].get(chosen)
            if not item or not item.get("access_token"):
                raise ChatGPTLoginError("sign_in_required")
            if not PLAN_SCOPES.issubset(item.get("scopes", [])):
                raise ChatGPTLoginError("plan_permission_required")
            if item["expires_at"] <= self._clock() + 60:
                earliest = item.get("earliest_refresh_at", 0)
                if isinstance(earliest, (int, float)) and earliest > self._clock():
                    raise ChatGPTLoginError("refresh_not_yet_available")
                try:
                    response = self._request(TOKEN, {"grant_type": "refresh_token", "client_id": item["client_id"],
                        "refresh_token": item["refresh_token"], "resource": RESOURCE})
                    update = self._token_record(response, item)
                    if response.get("id_token"):
                        claims = self._verify_id(response["id_token"], item["client_id"])
                        if claims["sub"] != item["subject"]:
                            raise ChatGPTLoginError("account_mismatch")
                        update["id_token"] = response["id_token"]
                    item.update(update)
                    self._save(data)
                except ChatGPTLoginError as exc:
                    if exc.category in ("authorization_expired", "account_mismatch", "identity_verification_failed"):
                        for key in ("access_token", "refresh_token", "id_token"):
                            item.pop(key, None)
                        self._save(data)
                    raise
            if not PLAN_SCOPES.issubset(item["scopes"]):
                raise ChatGPTLoginError("plan_permission_required")
            return item["access_token"]

    def unlink(self, account_id):
        confirmed = False
        with self._mutex, self._lock():
            data = self._load()
            item = data["accounts"].get(account_id)
            if item is None:
                raise ChatGPTLoginError("account_not_found")
            data['auth_epoch'] = data.get('auth_epoch', 0) + 1
            for attempt in self._attempts.values():
                if attempt.get("account_id") == account_id and attempt["status"] == "pending":
                    attempt["status"] = "cancelled"
            if item.get("refresh_token"):
                try:
                    discovery = self._request(DISCOVERY)
                    endpoint = discovery.get("revocation_endpoint")
                    if discovery.get("issuer") != ISSUER or endpoint != ISSUER + "/api/accounts/oauth/revoke":
                        raise ChatGPTLoginError("unsafe_endpoint")
                    for retry in range(3):
                        try:
                            self._request(endpoint, {"token": item["refresh_token"],
                                "token_type_hint": "refresh_token", "client_id": item["client_id"]}, empty_ok=True)
                            confirmed = True
                            break
                        except ChatGPTLoginError as exc:
                            if exc.category not in ('connection_error', 'service_unavailable') or retry == 2:
                                break
                            time.sleep(0.25 * (2 ** retry))
                except Exception:
                    pass
            for key in ("access_token", "refresh_token", "id_token"):
                item.pop(key, None)
            if data["active"] == account_id:
                data["active"] = None
            self._save(data)
        return {"account_id": account_id, "remote_revocation_confirmed": confirmed,
                "status": "signed_out"}


_default_service = None
_default_mutex = threading.Lock()


def get_default_chatgpt_login_service():
    global _default_service
    with _default_mutex:
        if _default_service is None:
            _default_service = ChatGPTLoginService()
        return _default_service
