from pathlib import Path

from src.agents.code_reviewer import CodeReviewAgent
from src.agents.evaluator import EvaluationAgent
from src.agents.implementation import ImplementationAgent
from src.agents.policy_extractor import PolicyExtractorAgent
from src.agents.tech_spec import TechSpecAgent
from src.governance.loader import load_layers
from src.governance.resolver import GovernanceResolver
from src.llm.client import FakeLLMClient
from src.models.workflow import ApprovalStatus, QCDecision
from src.orchestration.feature_workflow import FeatureWorkflow
from src.orchestration.qc_gate import QCGate

ROOT = Path(__file__).resolve().parent.parent
GOVERNANCE_ROOT = ROOT / "governance"
FIXTURES = ROOT / "examples" / "sample-feature" / "fixtures"
FEATURE_REQUEST = (ROOT / "examples" / "sample-feature" / "feature-request.md").read_text()


def _fixtures() -> dict[str, str]:
    return {
        "initial_implementation": (FIXTURES / "draft_implementation.py").read_text(),
        "remediated_implementation": (FIXTURES / "remediated_implementation.py").read_text(),
    }


def _resolved_rules(client):
    layers = load_layers(GOVERNANCE_ROOT, "sample-product", "payment-service")
    return GovernanceResolver(PolicyExtractorAgent(client)).resolve(layers).rules


def _workflow(client) -> FeatureWorkflow:
    reviewer = CodeReviewAgent(client)
    return FeatureWorkflow(
        tech_spec_agent=TechSpecAgent(client),
        implementation_agent=ImplementationAgent(client),
        evaluator=EvaluationAgent(reviewer),
        qc_gate=QCGate(),
    )


def test_draft_fails_only_the_domain_specific_audit_logging_rule():
    client = FakeLLMClient(fixtures=_fixtures())
    rules = _resolved_rules(client)
    result = _workflow(client).run(
        feature_id="FEAT-001",
        feature_request=FEATURE_REQUEST,
        product="sample-product",
        domain="payment-service",
        governance_rules=rules,
        approved=False,
        approver="engineering-lead",
        max_remediation_attempts=1,
    )

    first_attempt = result.attempts[0]
    failed_ids = {r.rule_id for r in first_attempt.report.results if r.status.value == "FAIL"}
    assert failed_ids == {"DOMAIN-PAYMENT-SERVICE-001"}


def test_remediation_converges_to_pass_within_one_attempt():
    client = FakeLLMClient(fixtures=_fixtures())
    rules = _resolved_rules(client)
    result = _workflow(client).run(
        feature_id="FEAT-001",
        feature_request=FEATURE_REQUEST,
        product="sample-product",
        domain="payment-service",
        governance_rules=rules,
        approved=False,
        approver="engineering-lead",
        max_remediation_attempts=1,
    )

    assert len(result.attempts) == 2  # draft + one remediation
    assert result.qc_decision is QCDecision.PASS
    assert result.final_attempt.report.fail_count == 0


def test_pass_without_approval_flag_is_pending():
    client = FakeLLMClient(fixtures=_fixtures())
    rules = _resolved_rules(client)
    result = _workflow(client).run(
        feature_id="FEAT-001",
        feature_request=FEATURE_REQUEST,
        product="sample-product",
        domain="payment-service",
        governance_rules=rules,
        approved=False,
        approver="engineering-lead",
        max_remediation_attempts=1,
    )
    assert result.approval_status is ApprovalStatus.PENDING
    assert result.approver is None


def test_pass_with_approval_flag_records_the_approver():
    client = FakeLLMClient(fixtures=_fixtures())
    rules = _resolved_rules(client)
    result = _workflow(client).run(
        feature_id="FEAT-001",
        feature_request=FEATURE_REQUEST,
        product="sample-product",
        domain="payment-service",
        governance_rules=rules,
        approved=True,
        approver="engineering-lead",
        max_remediation_attempts=1,
    )
    assert result.approval_status is ApprovalStatus.APPROVED
    assert result.approver == "engineering-lead"


def test_zero_remediation_attempts_blocks_immediately():
    # No "remediated_implementation" fixture configured -- if the workflow
    # tried to remediate anyway, this would raise NotImplementedError
    # instead of cleanly blocking.
    client = FakeLLMClient(fixtures={"initial_implementation": _fixtures()["initial_implementation"]})
    rules = _resolved_rules(client)
    result = _workflow(client).run(
        feature_id="FEAT-001",
        feature_request=FEATURE_REQUEST,
        product="sample-product",
        domain="payment-service",
        governance_rules=rules,
        approved=True,
        approver="engineering-lead",
        max_remediation_attempts=0,
    )
    assert result.qc_decision is QCDecision.BLOCK
    assert len(result.attempts) == 1
    assert result.approval_status is ApprovalStatus.NOT_REACHED
