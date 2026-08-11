# KNOWLEDGE.md

Generated from `examples/sample-product`. Evidence-backed findings only --
see FEATURES.yaml for the feature inventory and GLOSSARY.md for terms.

## Components

- **api/** -- API layer: HTTP-style route handlers. (3 files)
- **auth/** -- Authorization for privileged, state-changing actions. (2 files)
- **models/** -- Data models: plain dataclasses with no behavior, used by services/. (3 files)
- **services/** -- Business logic layer. (4 files)
- **tests/** -- Tests, one file per api/ handler it covers (see README.md). (3 files)

## Findings

### authorization_pattern

Privileged actions are authorized by calling require_authorization() before performing the action.

Evidence: `auth/authorization.py:16`
Confidence: 0.95

### validation_pattern

Handlers validate required fields with an explicit guard that raises ValueError before using them.

Evidence: `api/keys.py:11`, `api/users.py:10`
Confidence: 0.95

### test_organization

Tests are organized one-to-one with the source file they cover: api/keys.py <- tests/test_keys.py; api/users.py <- tests/test_users.py; auth/authorization.py <- tests/test_keys.py.

Evidence: `api/keys.py`, `api/users.py`, `auth/authorization.py`, `tests/test_keys.py`, `tests/test_users.py`
Confidence: 0.95

### files_change_together

Adding or changing a feature like api/keys.py typically touches its whole dependency chain: api/keys.py -> api/__init__.py -> auth/authorization.py -> services/key_service.py -> models/key.py -> services/audit.py.

Evidence: `api/keys.py`, `api/__init__.py`, `auth/authorization.py`, `services/key_service.py`, `models/key.py`, `services/audit.py`
Confidence: 0.95

### adding_an_endpoint

A new endpoint follows the same shape as api/keys.py: a thin api/ handler that validates input, calls the authorization check if the action is privileged, and delegates to a services/ function.

Evidence: `api/keys.py`, `api/__init__.py`, `auth/authorization.py`, `services/key_service.py`, `models/key.py`, `services/audit.py`
Confidence: 0.95

