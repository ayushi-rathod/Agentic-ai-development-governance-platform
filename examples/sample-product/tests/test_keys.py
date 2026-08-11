"""Tests for the API key rotation feature (api/keys.py).

Illustrative fixtures for the knowledge-extraction demo, structured like
real tests -- but sample-product isn't installed as a package or run by
this project's own test suite (see the repo-root tests/ for that).
"""

from __future__ import annotations

from api.keys import rotate_api_key
from auth.authorization import AuthorizationError


def test_rotate_api_key_requires_authorization():
    try:
        rotate_api_key({"account_id": "acct-001", "is_authorized": False})
        raise AssertionError("expected AuthorizationError")
    except AuthorizationError:
        pass


def test_rotate_api_key_requires_account_id():
    try:
        rotate_api_key({"is_authorized": True})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_rotate_api_key_returns_new_key_id():
    result = rotate_api_key({"account_id": "acct-001", "is_authorized": True})
    assert result["status"] == "ok"
    assert result["account_id"] == "acct-001"
    assert "key_id" in result
