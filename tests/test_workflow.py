from pathlib import Path

from src.llm.client import FakeLLMClient
from src.models.policy import Status
from src.orchestration.workflow import Orchestrator

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "policies" / "sample_engineering_policy.md"
VIOLATING_PATH = ROOT / "examples" / "violating_code.py"
COMPLIANT_PATH = ROOT / "examples" / "compliant_code.py"


def _orchestrator() -> Orchestrator:
    return Orchestrator(FakeLLMClient())


def test_full_workflow_flags_every_checkable_rule_in_the_violating_example():
    result = _orchestrator().run(
        policy_text=POLICY_PATH.read_text(),
        policy_source=str(POLICY_PATH),
        code_text=VIOLATING_PATH.read_text(),
        code_source=str(VIOLATING_PATH),
    )

    assert len(result.rules) == 6
    assert not result.initial_report.passed

    checkable_categories = {
        "secrets",
        "sql_injection",
        "authorization",
        "input_validation",
        "error_handling",
    }
    checkable_rule_ids = {r.id for r in result.rules if r.category in checkable_categories}
    failed_rule_ids = {
        r.rule_id for r in result.initial_report.results if r.status is Status.FAIL
    }
    assert checkable_rule_ids == failed_rule_ids

    # Every failure should have a corresponding suggested fix.
    assert {f.rule_id for f in result.fixes} == failed_rule_ids


def test_compliant_reference_satisfies_every_checkable_rule():
    result = _orchestrator().run(
        policy_text=POLICY_PATH.read_text(),
        policy_source=str(POLICY_PATH),
        code_text=VIOLATING_PATH.read_text(),
        code_source=str(VIOLATING_PATH),
        reference_code=COMPLIANT_PATH.read_text(),
        reference_source=str(COMPLIANT_PATH),
    )

    assert result.reference_report is not None
    assert result.reference_report.fail_count == 0
    # Rule 6 has no deterministic checker, so the offline demo client can
    # never confidently pass it -- see README's tradeoffs section.
    assert result.reference_report.warning_count == 1
    assert result.reference_report.passed
