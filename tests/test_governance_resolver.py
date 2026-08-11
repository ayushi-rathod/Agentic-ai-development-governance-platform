import pytest

from src.agents.policy_extractor import PolicyExtractorAgent
from src.governance.loader import GovernanceSource
from src.governance.resolver import GovernanceResolver, GovernanceViolationError
from src.llm.client import FakeLLMClient


def _resolver() -> GovernanceResolver:
    return GovernanceResolver(PolicyExtractorAgent(FakeLLMClient()))


GLOBAL_TEXT = (
    "1. **No hardcoded secrets** — Credentials must not be hardcoded.\n"
    "2. **Input validation** — Validate required fields.\n"
)
PRODUCT_TEXT = "1. **Rate limiting** — Public endpoints must enforce a rate limit.\n"
DOMAIN_TEXT = "1. **Audit logging** — Privileged operations must be logged.\n"


def test_merge_prefixes_ids_by_layer_and_tags_layer_field():
    layers = [
        GovernanceSource("global", GLOBAL_TEXT, []),
        GovernanceSource("product:sample-product", PRODUCT_TEXT, []),
        GovernanceSource("domain:payment-service", DOMAIN_TEXT, []),
    ]
    rule_set = _resolver().resolve(layers)

    ids = [r.id for r in rule_set.rules]
    assert ids == [
        "GLOBAL-001",
        "GLOBAL-002",
        "PRODUCT-SAMPLE-PRODUCT-001",
        "DOMAIN-PAYMENT-SERVICE-001",
    ]
    layers_by_id = {r.id: r.layer for r in rule_set.rules}
    assert layers_by_id["GLOBAL-001"] == "global"
    assert layers_by_id["PRODUCT-SAMPLE-PRODUCT-001"] == "product:sample-product"
    assert layers_by_id["DOMAIN-PAYMENT-SERVICE-001"] == "domain:payment-service"


def test_relaxation_marker_in_product_layer_raises():
    layers = [
        GovernanceSource("global", GLOBAL_TEXT, []),
        GovernanceSource(
            "product:sample-product",
            "1. **No secrets rule** — This override: the no-hardcoded-secrets rule is waived here.\n",
            [],
        ),
    ]
    with pytest.raises(GovernanceViolationError):
        _resolver().resolve(layers)


def test_relaxation_marker_in_domain_layer_raises():
    layers = [
        GovernanceSource("global", GLOBAL_TEXT, []),
        GovernanceSource(
            "domain:payment-service",
            "1. **Exception** — Authorization is exempt for internal callers.\n",
            [],
        ),
    ]
    with pytest.raises(GovernanceViolationError):
        _resolver().resolve(layers)


def test_global_layer_is_never_checked_for_relaxation():
    # "exempt" appearing in the *global* layer isn't a relaxation of
    # anything (nothing outranks it), so it must not raise.
    layers = [
        GovernanceSource(
            "global",
            "1. **Exemption process** — Requests for an exemption must be reviewed by security.\n",
            [],
        )
    ]
    rule_set = _resolver().resolve(layers)
    assert len(rule_set.rules) == 1
