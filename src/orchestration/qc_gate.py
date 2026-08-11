"""The QC gate: turns an EvaluationReport into a PASS/FAIL decision.

Deliberately trivial -- one rule (any FAIL blocks) -- because the
interesting behavior lives in what FeatureWorkflow does with a FAIL
(bounded remediation, then BLOCK), not in the gate itself.
"""

from __future__ import annotations

from src.models.policy import EvaluationReport
from src.models.workflow import QCDecision


class QCGate:
    def decide(self, report: EvaluationReport) -> QCDecision:
        return QCDecision.PASS if report.fail_count == 0 else QCDecision.FAIL
