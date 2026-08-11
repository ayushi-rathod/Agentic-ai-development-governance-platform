"""Workflow eval: does the governed feature-development workflow, driven
by the real workflows/feature-development.yaml config (not a hardcoded
attempt limit), converge exactly the way the CLI demo claims it does --
FAIL on the domain-specific rule, remediate once, PASS, then wait on
human approval?

Deliberately loads gate config from YAML the same way src/main.py does,
so this eval also catches a broken config wiring path that a pure unit
test constructing FeatureWorkflow directly would miss.
"""

from pathlib import Path

import yaml

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

ROOT = Path(__file__).resolve().parent.parent.parent


def _run(approved: bool):
    workflow_config = yaml.safe_load(
        (ROOT / "workflows" / "feature-development.yaml").read_text()
    )
    max_attempts = workflow_config["gates"]["qc"]["max_remediation_attempts"]

    client = FakeLLMClient(
        fixtures={
            "initial_implementation": (
                ROOT / "examples" / "sample-feature" / "fixtures" / "draft_implementation.py"
            ).read_text(),
            "remediated_implementation": (
                ROOT / "examples" / "sample-feature" / "fixtures" / "remediated_implementation.py"
            ).read_text(),
        }
    )
    layers = load_layers(ROOT / "governance", "sample-product", "payment-service")
    rules = GovernanceResolver(PolicyExtractorAgent(client)).resolve(layers).rules
    feature_request = (ROOT / "examples" / "sample-feature" / "feature-request.md").read_text()

    workflow = FeatureWorkflow(
        tech_spec_agent=TechSpecAgent(client),
        implementation_agent=ImplementationAgent(client),
        evaluator=EvaluationAgent(CodeReviewAgent(client)),
        qc_gate=QCGate(),
    )
    return workflow.run(
        feature_id="FEAT-001",
        feature_request=feature_request,
        product="sample-product",
        domain="payment-service",
        governance_rules=rules,
        approved=approved,
        approver="engineering-lead",
        max_remediation_attempts=max_attempts,
    )


def test_end_to_end_story_matches_the_documented_demo():
    result = _run(approved=True)

    assert result.attempts[0].report.fail_count == 1
    failed_rule = next(
        r for r in result.attempts[0].report.results if r.status.value == "FAIL"
    )
    assert failed_rule.rule_id == "DOMAIN-PAYMENT-SERVICE-001"

    assert len(result.attempts) == 2
    assert result.final_attempt.report.fail_count == 0
    assert result.qc_decision is QCDecision.PASS
    assert result.approval_status is ApprovalStatus.APPROVED


def test_traceability_report_names_every_governance_rule_and_the_outcome():
    result = _run(approved=True)
    report = result.render_traceability_markdown()

    for rule in result.governance_rules:
        assert rule.id in report
    assert "QC decision: **PASS**" in report
    assert "Approval status: **APPROVED**" in report


def test_without_approval_the_workflow_halts_pending_not_blocked():
    result = _run(approved=False)
    assert result.qc_decision is QCDecision.PASS
    assert result.approval_status is ApprovalStatus.PENDING
