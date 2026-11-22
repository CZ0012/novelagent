"""Independent SG-036 boundary checks. No credentials, OAuth, or network calls."""
import pytest
from starlette.requests import Request
from apps.api.chatgpt_routes import is_local_plan_request


def local_request(*, peer="127.0.0.1", host="127.0.0.1:8123", origin=None, fetch_site=None):
    headers = [(b"host", host.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if fetch_site is not None:
        headers.append((b"sec-fetch-site", fetch_site.encode()))
    return Request({"type": "http", "method": "POST", "scheme": "http",
                    "path": "/settings/chatgpt/login", "raw_path": b"/settings/chatgpt/login",
                    "query_string": b"", "headers": headers,
                    "client": (peer, 1234), "server": ("127.0.0.1", 8123)})


@pytest.mark.parametrize("changes", [
    {"peer": "192.0.2.10"},
    {"host": "attacker.invalid:8123"},
    {"host": "127.0.0.1@attacker.invalid"},
    {"origin": "https://attacker.invalid"},
    {"origin": "null"},
    {"origin": "http://127.0.0.1:8123/"},
    {"origin": "http://127.0.0.1:8123@attacker.invalid"},
    {"origin": "http://localhost:9999"},
    {"fetch_site": "cross-site"},
])
def test_plan_rejects_untrusted_surfaces_even_if_cors_lists_remote(changes):
    assert not is_local_plan_request(local_request(**changes), ["https://attacker.invalid"])


@pytest.mark.parametrize("changes", [
    {},
    {"origin": "http://127.0.0.1:8123"},
    {"origin": "tauri://localhost"},
    {"origin": "http://tauri.localhost"},
    {"origin": "https://tauri.localhost"},
])
def test_plan_accepts_only_expected_local_surfaces(changes):
    assert is_local_plan_request(local_request(**changes), [])


def test_configured_development_origin_still_requires_loopback_peer_and_host():
    origins = ["http://localhost:5173"]
    assert is_local_plan_request(local_request(origin=origins[0]), origins)
    assert not is_local_plan_request(local_request(peer="192.0.2.10", origin=origins[0]), origins)
    assert not is_local_plan_request(local_request(host="attacker.invalid", origin=origins[0]), origins)
