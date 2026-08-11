from src.agents.tech_spec import TechSpecAgent
from src.llm.client import FakeLLMClient
from src.models.policy import PolicyRule, Severity

RULES = [
    PolicyRule(
        id="GLOBAL-001",
        description="Credentials must not be hardcoded.",
        category="secrets",
        severity=Severity.CRITICAL,
        detection_hint="secrets",
        layer="global",
    ),
    PolicyRule(
        id="PRODUCT-001",
        description="Public endpoints must enforce a rate limit.",
        category="rate_limiting",
        severity=Severity.MEDIUM,
        detection_hint=None,
        layer="product:sample-product",
    ),
]


def _agent() -> TechSpecAgent:
    return TechSpecAgent(FakeLLMClient())


def test_title_skips_generic_markdown_heading():
    request = "# Feature Request\n\nAdd an endpoint to rotate API keys.\n"
    spec = _agent().create("FEAT-001", request, RULES)
    assert spec.title == "Add an endpoint to rotate API keys."


def test_every_rule_is_traced_into_governance_rule_ids():
    spec = _agent().create("FEAT-001", "Do the thing.", RULES)
    assert spec.governance_rule_ids == ["GLOBAL-001", "PRODUCT-001"]


def test_security_relevant_rule_appears_in_security_considerations():
    spec = _agent().create("FEAT-001", "Do the thing.", RULES)
    assert any("GLOBAL-001" in item for item in spec.security_considerations)
    assert not any("PRODUCT-001" in item for item in spec.security_considerations)


def test_rendered_markdown_has_every_required_section():
    spec = _agent().create("FEAT-001", "Do the thing.", RULES)
    rendered = spec.render_markdown()
    for header in (
        "## Overview",
        "## Requirements",
        "## Security Considerations",
        "## Test Plan",
        "## Governance Rules Applied",
    ):
        assert header in rendered
