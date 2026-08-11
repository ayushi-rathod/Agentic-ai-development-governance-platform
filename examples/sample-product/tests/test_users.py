"""Tests for the account lookup endpoint (api/users.py)."""

from __future__ import annotations

from api.users import get_user


def test_get_user_requires_account_id():
    try:
        get_user({})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_get_user_returns_account():
    result = get_user({"account_id": "acct-001"})
    assert result["status"] == "ok"
    assert result["account_id"] == "acct-001"
