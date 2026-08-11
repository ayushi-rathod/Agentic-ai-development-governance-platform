"""Coordinates the governed feature-development workflow: feature request
-> tech spec -> implementation -> review/evaluation -> QC gate (with a
bounded remediation loop) -> human approval.

Like the review Orchestrator, this is a plain class calling plain agent
methods -- see that module's docstring for why. The one piece of real
control flow here is the remediation loop, and it's bounded
(max_remediation_attempts) so a persistently-failing implementation
BLOCKs rather than looping forever -- a generic, unglamorous safeguard,
not a novel idea, but one worth actually having.
"""

from __future__ import annotations

from src.agents.evaluator import EvaluationAgent
from src.agents.implementation import ImplementationAgent
from src.agents.tech_spec import TechSpecAgent
from src.models.policy import PolicyRule, Status
from src.models.workflow import (
    ApprovalStatus,
    FeatureWorkflowResult,
    QCDecision,
    RemediationAttempt,
)
from src.orchestration.qc_gate import QCGate


class FeatureWorkflow:
    def __init__(
        self,
        tech_spec_agent: TechSpecAgent,
        implementation_agent: ImplementationAgent,
        evaluator: EvaluationAgent,
        qc_gate: QCGate,
    ):
        self._tech_spec_agent = tech_spec_agent
        self._implementation_agent = implementation_agent
        self._evaluator = evaluator
        self._qc_gate = qc_gate

    def run(
        self,
        feature_id: str,
        feature_request: str,
        product: str,
        domain: str | None,
        governance_rules: list[PolicyRule],
        approved: bool,
        approver: str,
        max_remediation_attempts: int = 1,
    ) -> FeatureWorkflowResult:
        spec = self._tech_spec_agent.create(feature_id, feature_request, governance_rules)
        code = self._implementation_agent.implement(spec)

        attempts: list[RemediationAttempt] = []
        attempt_number = 0
        decision = QCDecision.FAIL

        while True:
            report = self._evaluator.evaluate(
                code,
                governance_rules,
                policy_source="layered-governance",
                code_source=f"{feature_id} (attempt {attempt_number})",
            )
            attempts.append(
                RemediationAttempt(attempt=attempt_number, code=code, report=report)
            )
            decision = self._qc_gate.decide(report)

            if decision is QCDecision.PASS:
                break
            if attempt_number >= max_remediation_attempts:
                decision = QCDecision.BLOCK
                break

            violations = [r for r in report.results if r.status is Status.FAIL]
            code = self._implementation_agent.remediate(code, violations)
            attempt_number += 1

        approval_status = ApprovalStatus.NOT_REACHED
        approver_recorded = None
        if decision is QCDecision.PASS:
            approval_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.PENDING
            approver_recorded = approver if approved else None

        return FeatureWorkflowResult(
            feature_id=feature_id,
            feature_request=feature_request,
            product=product,
            domain=domain,
            governance_rules=governance_rules,
            tech_spec=spec,
            attempts=attempts,
            qc_decision=decision,
            approval_status=approval_status,
            approver=approver_recorded,
        )
