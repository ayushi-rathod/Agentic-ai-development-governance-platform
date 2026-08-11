# GLOSSARY.md

Domain terminology, defined only from what the repository supports.

### AuthorizationError

Raised when a caller is not authorized to perform an action.

Evidence: `auth/authorization.py:12`

### ServiceAccount

A non-human identity (e.g. a backend integration) that owns API keys.

Evidence: `models/account.py:9`

### ApiKey

A rotated credential belonging to a service account.

Evidence: `models/key.py:9`

