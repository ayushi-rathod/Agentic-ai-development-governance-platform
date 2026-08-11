from src.agents.code_reviewer import CodeReviewAgent
from src.llm.client import FakeLLMClient
from src.models.policy import CheckMethod, PolicyRule, Severity, Status

SECRET_RULE = PolicyRule(
    id="POL-001",
    description="Secrets must not be hardcoded.",
    category="secrets",
    severity=Severity.CRITICAL,
    detection_hint="secrets",
)

GENERAL_RULE = PolicyRule(
    id="POL-002",
    description="Changes should be logged.",
    category="general",
    severity=Severity.MEDIUM,
    detection_hint=None,
)


def _reviewer() -> CodeReviewAgent:
    return CodeReviewAgent(FakeLLMClient())


def test_deterministic_fail_is_reported_with_full_confidence():
    code = 'API_KEY = "sk-demo-123"\n'
    [result] = _reviewer().review(code, [SECRET_RULE])
    assert result.status is Status.FAIL
    assert result.confidence == 1.0
    assert result.method is CheckMethod.HYBRID
    assert "API_KEY" in result.evidence


def test_deterministic_pass_when_no_evidence_found():
    code = "import os\nAPI_KEY = os.environ.get('API_KEY', '')\n"
    [result] = _reviewer().review(code, [SECRET_RULE])
    assert result.status is Status.PASS
    assert result.confidence == 1.0
    assert result.method is CheckMethod.HYBRID


def test_rule_with_no_checker_falls_back_to_llm_and_low_confidence_pass_becomes_warning():
    code = "def do_something():\n    pass\n"
    [result] = _reviewer().review(code, [GENERAL_RULE])
    assert result.method is CheckMethod.LLM
    # FakeLLMClient always returns confidence 0.7 with no deterministic evidence,
    # which is below the "trust this PASS" threshold.
    assert result.status is Status.WARNING


def test_review_covers_every_rule_supplied():
    code = "x = 1\n"
    results = _reviewer().review(code, [SECRET_RULE, GENERAL_RULE])
    assert [r.rule_id for r in results] == ["POL-001", "POL-002"]
