"""Merges governance layers into one PolicyRuleSet and enforces
"extend, never relax": a non-global layer may only add rules, never
weaken or waive one it inherits.

This is a deliberately small, explicit check -- not a general policy
diff/verification engine -- see README for what a production version
would need instead (e.g. semantic diffing of rule text across versions).
"""

from __future__ import annotations

from src.agents.policy_extractor import PolicyExtractorAgent
from src.governance.loader import GovernanceSource
from src.models.policy import PolicyRule, PolicyRuleSet

RELAXATION_MARKERS = (
    "does not apply",
    "is exempt",
    "is waived",
    "no longer required",
    "override:",
    "relax:",
)


class GovernanceViolationError(Exception):
    """A lower governance layer attempted to weaken an inherited rule."""


def _layer_prefix(label: str) -> str:
    return label.upper().replace(":", "-").replace(" ", "-")


class GovernanceResolver:
    def __init__(self, extractor: PolicyExtractorAgent):
        self._extractor = extractor

    def resolve(self, layers: list[GovernanceSource]) -> PolicyRuleSet:
        all_rules: list[PolicyRule] = []
        for layer in layers:
            self._check_no_relaxation(layer)
            rule_set = self._extractor.extract(layer.text, source=layer.label)
            prefix = _layer_prefix(layer.label)
            for rule in rule_set.rules:
                number = rule.id.rsplit("-", 1)[-1]
                all_rules.append(
                    rule.model_copy(
                        update={"id": f"{prefix}-{number}", "layer": layer.label}
                    )
                )
        return PolicyRuleSet(source="layered-governance", rules=all_rules)

    @staticmethod
    def _check_no_relaxation(layer: GovernanceSource) -> None:
        if layer.label == "global":
            return  # nothing above it to relax
        lowered = layer.text.lower()
        for marker in RELAXATION_MARKERS:
            if marker in lowered:
                sources = ", ".join(str(f) for f in layer.files)
                raise GovernanceViolationError(
                    f"Layer '{layer.label}' ({sources}) appears to weaken an "
                    f"inherited rule (found {marker!r}). Lower layers may only "
                    "add stricter requirements, never relax inherited ones."
                )
