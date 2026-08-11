import pytest

from src.agents.implementation import ImplementationAgent
from src.llm.client import FakeLLMClient
from src.models.policy import CheckMethod, EvaluationResult, Severity, Status
from src.models.workflow import TechSpec

SPEC = TechSpec(
    feature_id="FEAT-001",
    title="Example",
    overview="Do the thing.",
    requirements=["Satisfy GLOBAL-001"],
    security_considerations=[],
    test_plan=[],
    governance_rule_ids=["GLOBAL-001"],
)


def test_implement_returns_configured_fixture():
    client = FakeLLMClient(fixtures={"initial_implementation": "print('hello')\n"})
    code = ImplementationAgent(client).implement(SPEC)
    assert code == "print('hello')\n"


def test_implement_without_fixture_raises():
    client = FakeLLMClient()
    with pytest.raises(NotImplementedError):
        ImplementationAgent(client).implement(SPEC)


def test_remediate_returns_configured_fixture():
    client = FakeLLMClient(fixtures={"remediated_implementation": "print('fixed')\n"})
    violation = EvaluationResult(
        rule_id="GLOBAL-001",
        description="n/a",
        severity=Severity.HIGH,
        status=Status.FAIL,
        evidence="n/a",
        explanation="n/a",
        confidence=1.0,
        method=CheckMethod.HYBRID,
    )
    code = ImplementationAgent(client).remediate("old code", [violation])
    assert code == "print('fixed')\n"
