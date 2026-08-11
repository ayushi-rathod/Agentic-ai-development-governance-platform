"""Skill eval for create-tech-spec: did it include all required sections?

Run against the real feature request and real resolved governance rather
than a synthetic fixture, per skills/create-tech-spec/SKILL.md.
"""

from pathlib import Path

from src.agents.policy_extractor import PolicyExtractorAgent
from src.agents.tech_spec import TechSpecAgent
from src.governance.loader import load_layers
from src.governance.resolver import GovernanceResolver
from src.llm.client import FakeLLMClient

ROOT = Path(__file__).resolve().parent.parent.parent

REQUIRED_SECTIONS = (
    "## Overview",
    "## Requirements",
    "## Security Considerations",
    "## Test Plan",
    "## Governance Rules Applied",
)


def test_tech_spec_includes_all_required_sections():
    """Did /create-tech-spec include all required sections?"""
    client = FakeLLMClient()
    layers = load_layers(ROOT / "governance", "sample-product", "payment-service")
    rules = GovernanceResolver(PolicyExtractorAgent(client)).resolve(layers).rules
    feature_request = (ROOT / "examples" / "sample-feature" / "feature-request.md").read_text()

    spec = TechSpecAgent(client).create("FEAT-001", feature_request, rules)
    rendered = spec.render_markdown()

    missing = [section for section in REQUIRED_SECTIONS if section not in rendered]
    assert not missing, f"tech spec is missing required sections: {missing}"


def test_tech_spec_traces_every_resolved_rule():
    client = FakeLLMClient()
    layers = load_layers(ROOT / "governance", "sample-product", "payment-service")
    rules = GovernanceResolver(PolicyExtractorAgent(client)).resolve(layers).rules
    feature_request = (ROOT / "examples" / "sample-feature" / "feature-request.md").read_text()

    spec = TechSpecAgent(client).create("FEAT-001", feature_request, rules)

    assert set(spec.governance_rule_ids) == {r.id for r in rules}


def test_tech_spec_surfaces_the_domain_specific_rule_as_a_security_consideration():
    client = FakeLLMClient()
    layers = load_layers(ROOT / "governance", "sample-product", "payment-service")
    rules = GovernanceResolver(PolicyExtractorAgent(client)).resolve(layers).rules
    feature_request = (ROOT / "examples" / "sample-feature" / "feature-request.md").read_text()

    spec = TechSpecAgent(client).create("FEAT-001", feature_request, rules)

    assert any(
        "DOMAIN-PAYMENT-SERVICE-001" in item for item in spec.security_considerations
    )
