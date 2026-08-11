"""Produces the final PASS/FAIL/WARNING report for a piece of code.

EvaluationAgent doesn't duplicate CodeReviewAgent's checking logic -- it
runs the same review and packages the results into an EvaluationReport.
Keeping it as its own agent (rather than folding it into CodeReviewAgent)
matches how the workflow actually uses it: once to evaluate the code you
handed in, and again to confirm a corrected version now satisfies the
policy (see Orchestrator).
"""

from __future__ import annotations

from src.agents.code_reviewer import CodeReviewAgent
from src.models.policy import EvaluationReport, PolicyRule


class EvaluationAgent:
    def __init__(self, reviewer: CodeReviewAgent):
        self._reviewer = reviewer

    def evaluate(
        self, code: str, rules: list[PolicyRule], policy_source: str, code_source: str
    ) -> EvaluationReport:
        results = self._reviewer.review(code, rules)
        return EvaluationReport(
            policy_source=policy_source,
            code_source=code_source,
            results=results,
        )
