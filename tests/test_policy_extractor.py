import pytest

from src.agents.policy_extractor import PolicyExtractorAgent
from src.llm.client import FakeLLMClient
from src.models.policy import Severity


@pytest.fixture
def extractor() -> PolicyExtractorAgent:
    return PolicyExtractorAgent(FakeLLMClient())


def test_extracts_known_category_with_expected_severity(extractor):
    text = "1. **No hardcoded secrets** — Credentials must not be hardcoded.\n"
    rule_set = extractor.extract(text, source="test.md")
    assert len(rule_set.rules) == 1
    rule = rule_set.rules[0]
    assert rule.id == "POL-001"
    assert rule.category == "secrets"
    assert rule.severity == Severity.CRITICAL


def test_extracts_multiple_rules_in_order(extractor):
    text = (
        "1. **No hardcoded secrets** — Credentials must not be hardcoded.\n"
        "2. **Observability** — Log significant state changes.\n"
    )
    rule_set = extractor.extract(text)
    assert [r.id for r in rule_set.rules] == ["POL-001", "POL-002"]
    assert rule_set.rules[1].category == "general"
    assert rule_set.rules[1].severity == Severity.MEDIUM


def test_raises_when_no_rules_found(extractor):
    with pytest.raises(ValueError):
        extractor.extract("This document has no numbered rules in it.")


def test_title_takes_priority_over_description_for_classification(extractor):
    # Regression test: "invalid input" in the description contains "valid"
    # as a substring, which must not shadow the title's clear "error
    # handling" signal and misroute this rule to the input_validation checker.
    text = (
        "1. **Explicit error handling** — Public functions must handle "
        "expected failure cases instead of letting invalid input raise "
        "uncaught exceptions.\n"
    )
    rule_set = extractor.extract(text)
    assert rule_set.rules[0].category == "error_handling"
