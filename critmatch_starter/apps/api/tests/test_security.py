import time

import pytest

from app.core.security import (
    SessionError,
    issue_session_token,
    verify_session_token,
)


def test_session_roundtrip():
    token = issue_session_token({"sub": "user-123", "role": "research_user"})
    claims = verify_session_token(token)
    assert claims["sub"] == "user-123"
    assert claims["role"] == "research_user"
    assert claims["exp"] > int(time.time())


def test_tampered_token_rejected():
    token = issue_session_token({"sub": "u"})
    bad = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    with pytest.raises(SessionError):
        verify_session_token(bad)
