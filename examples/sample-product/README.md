# sample-product

A small, fictional application used to demonstrate knowledge extraction
(`python -m src.main knowledge-extract --repo examples/sample-product`).
It is standalone -- not installed as a package, not part of this
project's own test suite, and not derived from any real system.

It implements two endpoints (`api/keys.py`: rotate a service account's API
key; `api/users.py`: look up a service account) so the extractor has a
real request → auth → service → model → test chain to discover, plus one
read-only endpoint for contrast with the privileged one.
