"""Data model for a service account -- a non-human identity that owns API keys."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ServiceAccount:
    """A non-human identity (e.g. a backend integration) that owns API keys."""

    account_id: str
    name: str
