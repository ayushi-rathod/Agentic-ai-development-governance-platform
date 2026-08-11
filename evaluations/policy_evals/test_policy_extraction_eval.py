"""Policy eval: does layered governance resolve to the rules we expect?

Unlike tests/test_governance_resolver.py (which uses small synthetic
fixtures to isolate the merge/prefix/relaxation logic), this eval runs
against the actual bundled governance/ content -- it fails if someone
edits a governance markdown file in a way that silently changes what gets
extracted, even if every unit test still passes.
"""

from pathlib import Path

from src.agents.policy_extractor import PolicyExtractorAgent
from src.governance.loader import load_layers
from src.governance.resolver import GovernanceResolver
from src.llm.client import FakeLLMClient

ROOT = Path(__file__).resolve().parent.parent.parent
GOVERNANCE_ROOT = ROOT / "governance"

EXPECTED_CATEGORIES_BY_LAYER = {
    "global": {"secrets", "sql_injection", "authorization", "input_validation", "error_handling"},
    "product:sample-product": {"rate_limiting"},
    "domain:payment-service": {"audit_logging"},
}


def test_layered_governance_resolves_expected_categories_per_layer():
    layers = load_layers(GOVERNANCE_ROOT, "sample-product", "payment-service")
    resolver = GovernanceResolver(PolicyExtractorAgent(FakeLLMClient()))
    rule_set = resolver.resolve(layers)

    categories_by_layer: dict[str, set[str]] = {}
    for rule in rule_set.rules:
        categories_by_layer.setdefault(rule.layer, set()).add(rule.category)

    assert categories_by_layer == EXPECTED_CATEGORIES_BY_LAYER


def test_domain_layer_rule_is_strictly_additive_to_product_and_global():
    layers = load_layers(GOVERNANCE_ROOT, "sample-product", "payment-service")
    resolver = GovernanceResolver(PolicyExtractorAgent(FakeLLMClient()))
    rule_set = resolver.resolve(layers)

    global_categories = {r.category for r in rule_set.rules if r.layer == "global"}
    domain_categories = {r.category for r in rule_set.rules if r.layer == "domain:payment-service"}

    # "Extend, never relax": the domain layer must add something new, and
    # must not redefine any category the global layer already governs.
    assert domain_categories
    assert domain_categories.isdisjoint(global_categories)
