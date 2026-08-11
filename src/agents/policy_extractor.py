"""Turns free-form policy prose into structured, machine-checkable rules."""

from __future__ import annotations

import json

from pydantic import ValidationError

from src.llm.client import LLMClient
from src.models.policy import PolicyRule, PolicyRuleSet

SYSTEM_PROMPT = """\
[TASK:POLICY_EXTRACTION]
You are a policy extraction assistant for a software engineering team.

You will be given a JSON object with one field, "policy_text", containing an
engineering policy document written in plain English or markdown.

Extract every distinct rule as a JSON object with this exact shape:
{
  "rules": [
    {
      "id": "POL-001",
      "description": "<one sentence, imperative, restating the rule>",
      "category": "<short snake_case tag, e.g. secrets, sql_injection, \
authorization, input_validation, error_handling, or a new tag if none fit>",
      "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
      "detection_hint": "<same value as category, or null>"
    }
  ]
}

Number rule ids sequentially starting at POL-001 in the order rules appear.
Return ONLY the JSON object, no surrounding text.
"""


class PolicyExtractorAgent:
    """Reads unstructured engineering policy text and produces PolicyRule objects."""

    def __init__(self, client: LLMClient):
        self._client = client

    def extract(self, policy_text: str, source: str = "<policy>") -> PolicyRuleSet:
        user_payload = json.dumps({"policy_text": policy_text})
        raw = self._client.complete(SYSTEM_PROMPT, user_payload)

        try:
            data = json.loads(raw)
            rules = [PolicyRule.model_validate(r) for r in data["rules"]]
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise ValueError(
                f"Policy extractor returned a response that could not be parsed "
                f"into rules: {raw[:200]!r}"
            ) from exc

        if not rules:
            raise ValueError("Policy extractor found no rules in the given text.")

        return PolicyRuleSet(source=source, rules=rules)
