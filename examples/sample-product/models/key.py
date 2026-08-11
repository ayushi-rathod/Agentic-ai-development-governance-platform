"""Data model for a service account's API key."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApiKey:
    """A rotated credential belonging to a service account.

    secret_hash is a hash, never the raw key -- see services/key_service.py.
    """

    key_id: str
    account_id: str
    secret_hash: str
