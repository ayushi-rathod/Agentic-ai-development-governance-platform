"""Proposes a compliant fix for each FAIL result.

For the categories this project ships checkers for, fixes come from small
regex-driven templates applied to the evidence text a checker already
found -- illustrative, targeted suggestions (matching the CLI's
"Recommendation: ..." output), not a guaranteed-compilable whole-file
rewrite. For any other category we fall back to the LLM. See README for why
that split exists.
"""

from __future__ import annotations

import json
import re

from src.llm.client import LLMClient
from src.models.policy import EvaluationResult, FixSuggestion, PolicyRule, Status

SYSTEM_PROMPT = """\
[TASK:FIX_SUGGESTION]
You are a code fix assistant. You will receive a JSON object:
{
  "rule": {"id": ..., "description": ..., "category": ..., "severity": ...},
  "evidence": "<the violating snippet>",
  "code": "<full source file>"
}

Propose a corrected version of the violating snippet only (not the whole
file) that would satisfy the rule, plus a one-sentence rationale.

Reply with ONLY a JSON object of this exact shape:
{"suggested_snippet": "...", "rationale": "..."}
"""


def _fix_secret(evidence: str, rule_description: str) -> FixSuggestion | None:
    match = re.match(r"(\w+)\s*=", evidence)
    if not match:
        return None
    name = match.group(1)
    return FixSuggestion(
        rule_id="",
        rationale=f"{rule_description} Load the value from an environment variable instead.",
        original_snippet=evidence,
        suggested_snippet=f'{name} = os.environ["{name}"]',
    )


def _fix_sql(evidence: str, rule_description: str) -> FixSuggestion | None:
    match = re.match(r"(\w+)\s*=\s*f([\"'])(.*)\2\s*$", evidence, re.DOTALL)
    if not match:
        return None
    var_name, _, sql_text = match.groups()
    params = re.findall(r"\{(\w+)\}", sql_text)
    parameterized_sql = re.sub(r"\{\w+\}", "?", sql_text)
    param_tuple = ", ".join(params) + ("," if len(params) == 1 else "")
    suggested = (
        f'{var_name} = "{parameterized_sql}"\n'
        f"# execute with: cursor.execute({var_name}, ({param_tuple}))"
    )
    return FixSuggestion(
        rule_id="",
        rationale=f"{rule_description} Bind the value as a query parameter instead of formatting it into the SQL string.",
        original_snippet=evidence,
        suggested_snippet=suggested,
    )


def _fix_authorization(evidence: str, rule_description: str) -> FixSuggestion | None:
    match = re.search(r"def (\w+)", evidence)
    if not match:
        return None
    name = match.group(1)
    return FixSuggestion(
        rule_id="",
        rationale=f"{rule_description} Check the caller's permissions before performing the action.",
        original_snippet=evidence,
        suggested_snippet=(
            f"def {name}(request):\n"
            f"    require_authorization(request)\n"
            f"    ..."
        ),
    )


def _fix_input_validation(evidence: str, rule_description: str) -> FixSuggestion | None:
    match = re.search(r"reads (\w+)\['(\w+)'\]", evidence)
    if not match:
        return None
    container, key = match.groups()
    return FixSuggestion(
        rule_id="",
        rationale=f"{rule_description} Reject the request early if the required field is missing.",
        original_snippet=evidence,
        suggested_snippet=(
            f'if "{key}" not in {container}:\n'
            f'    raise ValueError("{key} is required")\n'
            f'{key} = {container}["{key}"]'
        ),
    )


def _fix_error_handling(evidence: str, rule_description: str) -> FixSuggestion | None:
    match = re.search(r"def (\w+)", evidence)
    if not match:
        return None
    name = match.group(1)
    return FixSuggestion(
        rule_id="",
        rationale=f"{rule_description} Handle the expected failure explicitly instead of letting it propagate.",
        original_snippet=evidence,
        suggested_snippet=(
            f"# inside {name}\n"
            f"try:\n"
            f"    ...\n"
            f"except OSError as exc:\n"
            f'    raise ValueError(f"operation failed: {{exc}}") from exc'
        ),
    )


def _fix_audit_logging(evidence: str, rule_description: str) -> FixSuggestion | None:
    match = re.search(r"def (\w+)", evidence)
    if not match:
        return None
    name = match.group(1)
    return FixSuggestion(
        rule_id="",
        rationale=f"{rule_description} Record an audit log entry before the privileged action completes.",
        original_snippet=evidence,
        suggested_snippet=(
            f"def {name}(request):\n"
            f'    audit_log("{name}", request)\n'
            f"    ..."
        ),
    )


_TEMPLATES = {
    "secrets": _fix_secret,
    "sql_injection": _fix_sql,
    "authorization": _fix_authorization,
    "input_validation": _fix_input_validation,
    "error_handling": _fix_error_handling,
    "audit_logging": _fix_audit_logging,
}


class FixAgent:
    """Generates a suggested fix for each FAIL result in a review."""

    def __init__(self, client: LLMClient):
        self._client = client

    def propose_fixes(
        self, code: str, results: list[EvaluationResult], rules: list[PolicyRule]
    ) -> list[FixSuggestion]:
        category_by_rule_id = {rule.id: rule.category for rule in rules}
        suggestions = []
        for result in results:
            if result.status is not Status.FAIL:
                continue
            category = category_by_rule_id.get(result.rule_id, "")
            suggestions.append(self._propose_one(code, result, category))
        return suggestions

    def _propose_one(
        self, code: str, result: EvaluationResult, category: str
    ) -> FixSuggestion:
        template_fn = _TEMPLATES.get(category)
        if template_fn is not None:
            suggestion = template_fn(result.evidence, result.description)
            if suggestion is not None:
                return suggestion.model_copy(update={"rule_id": result.rule_id})

        return self._propose_via_llm(code, result, category)

    def _propose_via_llm(
        self, code: str, result: EvaluationResult, category: str
    ) -> FixSuggestion:
        payload = json.dumps(
            {
                "rule": {
                    "id": result.rule_id,
                    "description": result.description,
                    "category": category or "general",
                    "severity": result.severity.value,
                },
                "evidence": result.evidence,
                "code": code,
            }
        )
        raw = self._client.complete(SYSTEM_PROMPT, payload)
        data = json.loads(raw)
        return FixSuggestion(
            rule_id=result.rule_id,
            rationale=data["rationale"],
            original_snippet=result.evidence,
            suggested_snippet=data["suggested_snippet"],
        )
