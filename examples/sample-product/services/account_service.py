"""Business logic for looking up service accounts."""

from __future__ import annotations

from models.account import ServiceAccount

_ACCOUNTS = {
    "acct-001": ServiceAccount(account_id="acct-001", name="Example Service Account"),
}


def get_account(account_id: str) -> ServiceAccount:
    if account_id not in _ACCOUNTS:
        raise LookupError(f"unknown account: {account_id}")
    return _ACCOUNTS[account_id]
