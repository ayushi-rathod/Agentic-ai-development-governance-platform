"""Models for the governed feature-development workflow (tech spec through
human approval). Kept separate from models/policy.py, which models a single
review, not a multi-stage workflow.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from src.models.policy import EvaluationReport, PolicyRule


class QCDecision(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCK = "BLOCK"  # FAIL with no remediation attempts left


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    NOT_REACHED = "NOT_REACHED"  # workflow blocked before reaching approval


class TechSpec(BaseModel):
    feature_id: str
    title: str
    overview: str
    requirements: list[str]
    security_considerations: list[str]
    test_plan: list[str]
    governance_rule_ids: list[str]

    def render_markdown(self) -> str:
        lines = [
            f"# Technical Spec: {self.title}",
            "",
            f"Feature ID: {self.feature_id}",
            "",
            "## Overview",
            "",
            self.overview,
            "",
            "## Requirements",
            "",
        ]
        lines += [f"- {item}" for item in self.requirements]
        lines += ["", "## Security Considerations", ""]
        lines += [f"- {item}" for item in self.security_considerations]
        lines += ["", "## Test Plan", ""]
        lines += [f"- {item}" for item in self.test_plan]
        lines += ["", "## Governance Rules Applied", ""]
        lines += [f"- {rule_id}" for rule_id in self.governance_rule_ids]
        return "\n".join(lines) + "\n"


class RemediationAttempt(BaseModel):
    attempt: int  # 0 = first draft, 1+ = remediation passes
    code: str
    report: EvaluationReport


class FeatureWorkflowResult(BaseModel):
    feature_id: str
    feature_request: str
    product: str
    domain: str | None
    governance_rules: list[PolicyRule]
    tech_spec: TechSpec
    attempts: list[RemediationAttempt]
    qc_decision: QCDecision
    approval_status: ApprovalStatus
    approver: str | None

    @property
    def final_attempt(self) -> RemediationAttempt:
        return self.attempts[-1]

    def render_traceability_markdown(self) -> str:
        lines = [
            f"# Traceability Report: {self.feature_id}",
            "",
            f"**Feature request:** {self.feature_request.strip()}",
            f"**Product / domain:** {self.product} / {self.domain or '(none)'}",
            "",
            "## Governance rules applied",
            "",
        ]
        for rule in self.governance_rules:
            lines.append(f"- `{rule.id}` [{rule.layer}] ({rule.severity.value}) {rule.description}")

        lines += ["", "## Tech spec", "", f"See requirements traced to: {', '.join(self.tech_spec.governance_rule_ids)}"]

        lines += ["", "## Remediation history", ""]
        for attempt in self.attempts:
            lines.append(
                f"- Attempt {attempt.attempt}: {attempt.report.pass_count} passed, "
                f"{attempt.report.fail_count} failed, {attempt.report.warning_count} warnings"
            )

        lines += [
            "",
            "## Outcome",
            "",
            f"- QC decision: **{self.qc_decision.value}**",
            f"- Approval status: **{self.approval_status.value}**"
            + (f" (by {self.approver})" if self.approver else ""),
        ]
        return "\n".join(lines) + "\n"
