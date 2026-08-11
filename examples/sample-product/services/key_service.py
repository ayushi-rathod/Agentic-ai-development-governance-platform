"""Business logic for creating and rotating API keys.

This is where key material is generated and persisted -- api/keys.py
stays a thin handler and never touches hashing or storage directly.
"""

from __future__ import annotations

import secrets

import bcrypt

from models.key import ApiKey
from services.audit import audit_log

_KEYS: dict[str, ApiKey] = {}


def rotate_key(account_id: str) -> ApiKey:
    raw_key = secrets.token_hex(32)
    secret_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
    key = ApiKey(key_id=secrets.token_hex(8), account_id=account_id, secret_hash=secret_hash)
    _KEYS[key.key_id] = key
    audit_log("rotate_key", account_id)
    return key
