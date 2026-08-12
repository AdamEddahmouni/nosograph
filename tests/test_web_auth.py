import json
import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from med_research.web.services import auth

pytestmark = pytest.mark.unit


def _request(*, headers=None, cookies=None, client_host="127.0.0.1") -> Request:
    all_headers = dict(headers or {})
    if cookies:
        all_headers["cookie"] = "; ".join(f"{key}={value}" for key, value in cookies.items())
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in all_headers.items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/workspace/notifications",
        "headers": raw_headers,
        "query_string": b"",
        "client": (client_host, 1234),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    request = Request(scope)
    return request


def test_local_session_is_signed_and_header_cannot_switch_identity(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv(
        "LOCAL_AUTH_USERS", json.dumps({"alice": "alice-password", "bob": "bob-password"})
    )

    issued = int(time.time())
    token = auth.create_session_token("alice", now=issued)
    assert auth.verify_session_token(token, now=issued + 1) == "alice"
    assert auth.verify_session_token(token + "x", now=issued + 1) is None

    request = _request(headers={"X-Researcher-ID": "bob"}, cookies={auth.SESSION_COOKIE: token})
    assert auth.get_researcher_id(request) == "alice"

    no_session = _request(headers={"X-Researcher-ID": "bob"})
    with pytest.raises(HTTPException) as error:
        auth.get_researcher_id(no_session)
    assert getattr(error.value, "status_code", None) == 401


def test_local_login_requires_configured_credentials(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("LOCAL_AUTH_USERS", "alice=secret")

    assert auth.authenticate_local_user("alice", "secret") == "alice"
    assert auth.authenticate_local_user("alice", "wrong") is None
    assert auth.authenticate_local_user("bob", "secret") is None


def test_proxy_principal_requires_trusted_source(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "proxy")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("AUTH_TRUSTED_PROXY_IPS", "10.0.0.5")

    trusted = _request(headers={"X-Authenticated-User": "alice"}, client_host="10.0.0.5")
    untrusted = _request(headers={"X-Authenticated-User": "bob"}, client_host="192.168.1.10")
    assert auth.get_researcher_id(trusted) == "alice"
    with pytest.raises(HTTPException) as error:
        auth.get_researcher_id(untrusted)
    assert getattr(error.value, "status_code", None) == 401
