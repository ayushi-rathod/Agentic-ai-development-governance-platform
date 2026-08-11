"""Shared audit-logging helper used by services that perform privileged actions."""

from __future__ import annotations


def audit_log(action: str, account_id: str) -> None:
    print(f"AUDIT: {action} performed for account {account_id}")
