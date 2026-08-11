"""LLM provider abstraction.

Every agent talks to an ``LLMClient`` -- never to a provider SDK directly.
That keeps provider choice a one-file decision (see ``AnthropicClient``) and
makes agents testable without network access or an API key (see
``FakeLLMClient``).

Both implementations exchange the same message shape: a system prompt whose
first line is a ``[TASK:NAME]`` marker, and a user message that is a single
JSON object. Real models read the JSON as context and are instructed (via
the rest of the system prompt) to reply with JSON matching a documented
schema. ``FakeLLMClient`` reads the same JSON directly and answers with
small, explicit heuristics instead of a model call -- it is a scripted
stand-in for demos and tests, not a general-purpose fake LLM.
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return a raw text completion for the given system/user prompt."""
        ...


TASK_TAG_RE = re.compile(r"^\[TASK:([A-Z_]+)\]")

# Matches "1. **Title** — description" or "1. **Title** - description".
POLICY_ITEM_RE = re.compile(
    r"^\s*\d+\.\s*\*\*(?P<title>[^*]+)\*\*\s*[—-]\s*(?P<description>.+)$",
    re.MULTILINE,
)

_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("secret", "secrets"),
    ("credential", "secrets"),
    ("token", "secrets"),
    ("sql", "sql_injection"),
    ("quer", "sql_injection"),
    ("database", "sql_injection"),
    ("audit", "audit_logging"),
    ("authoriz", "authorization"),
    ("permission", "authorization"),
    ("valid", "input_validation"),
    ("sanitiz", "input_validation"),
    ("error", "error_handling"),
    ("exception", "error_handling"),
    ("fail", "error_handling"),
    ("rate limit", "rate_limiting"),
]

_CATEGORY_SEVERITY: dict[str, str] = {
    "secrets": "CRITICAL",
    "sql_injection": "CRITICAL",
    "audit_logging": "CRITICAL",
    "authorization": "HIGH",
    "input_validation": "HIGH",
    "error_handling": "MEDIUM",
    "rate_limiting": "MEDIUM",
}


def _guess_category(text: str) -> str:
    lowered = text.lower()
    for keyword, category in _CATEGORY_KEYWORDS:
        if keyword in lowered:
            return category
    return "general"


class FakeLLMClient:
    """Deterministic, offline stand-in for a real LLM.

    Used as the default provider so the CLI and the test suite both run
    with no API key and no network access. It is intentionally simple: a
    small markdown parser for rule extraction, template-based judgments for
    review/fix/tech-spec tasks, and -- for IMPLEMENTATION/REMEDIATION,
    where "write working code from a spec" is well beyond what a
    heuristic can honestly do -- pre-written fixtures supplied by the
    caller. Without a fixture for those two tasks it raises rather than
    pretending to generate code; use --provider anthropic for real
    generation.
    """

    def __init__(self, fixtures: dict[str, str] | None = None):
        self._fixtures = fixtures or {}

    def complete(self, system: str, user: str) -> str:
        match = TASK_TAG_RE.match(system)
        if not match:
            raise NotImplementedError(
                "FakeLLMClient requires a '[TASK:NAME]' marker as the first "
                "line of the system prompt; got: " + system[:60]
            )
        task = match.group(1)
        payload = json.loads(user)

        if task == "POLICY_EXTRACTION":
            return self._extract_policy(payload)
        if task == "VIOLATION_REVIEW":
            return self._review_violation(payload)
        if task == "FIX_SUGGESTION":
            return self._suggest_fix(payload)
        if task == "TECH_SPEC_CREATION":
            return self._create_tech_spec(payload)
        if task == "IMPLEMENTATION":
            return self._from_fixture("initial_implementation")
        if task == "REMEDIATION":
            return self._from_fixture("remediated_implementation")
        if task == "KNOWLEDGE_SYNTHESIS":
            return self._synthesize_knowledge(payload)
        raise NotImplementedError(f"FakeLLMClient has no handler for task {task!r}")

    def _from_fixture(self, name: str) -> str:
        code = self._fixtures.get(name)
        if code is None:
            raise NotImplementedError(
                f"FakeLLMClient has no {name!r} fixture configured. Pass one via "
                "FakeLLMClient(fixtures={...}), or use --provider anthropic for "
                "real code generation."
            )
        return json.dumps({"code": code})

    @staticmethod
    def _synthesize_knowledge(payload: dict) -> str:
        """Derives findings/glossary/overview from the same structured,
        pre-selected context (see selection.py) a real model would
        reason over -- small heuristics standing in for genuine NLU, not
        a shortcut that reads different input than --provider anthropic
        would. It never invents a fact: everything it says traces back to
        a specific file/line already present in the payload.
        """
        files = payload.get("files") or []
        import_graph = payload.get("local_import_graph") or {}
        by_path = {f["path"]: f for f in files}
        components = payload.get("components") or []

        findings = []

        auth_marker = FakeLLMClient._find_auth_marker(files)
        if auth_marker:
            findings.append(
                {
                    "category": "authorization_pattern",
                    "statement": (
                        f"Privileged actions are authorized by calling "
                        f"{auth_marker['name']}() before performing the action."
                    ),
                    "evidence": [auth_marker["evidence"]],
                }
            )

        validation_examples = FakeLLMClient._find_validation_examples(files)
        if validation_examples:
            findings.append(
                {
                    "category": "validation_pattern",
                    "statement": (
                        "Handlers validate required fields with an explicit "
                        "guard that raises ValueError before using them."
                    ),
                    "evidence": validation_examples,
                }
            )

        test_mapping = FakeLLMClient._find_test_mapping(files, import_graph, by_path)
        if test_mapping:
            pairs = "; ".join(f"{t['source']} <- {', '.join(t['tests'])}" for t in test_mapping)
            evidence = list(
                dict.fromkeys(
                    [t["source"] for t in test_mapping]
                    + [test for t in test_mapping for test in t["tests"]]
                )
            )
            findings.append(
                {
                    "category": "test_organization",
                    "statement": f"Tests are organized one-to-one with the source file they cover: {pairs}.",
                    "evidence": evidence,
                }
            )

        feature_chains = FakeLLMClient._find_feature_chains(files, import_graph, by_path)
        if feature_chains:
            chain = feature_chains[0]
            findings.append(
                {
                    "category": "files_change_together",
                    "statement": (
                        f"Adding or changing a feature like {chain['entry_point']} "
                        f"typically touches its whole dependency chain: "
                        f"{' -> '.join(chain['chain'])}."
                    ),
                    "evidence": chain["chain"],
                }
            )
            findings.append(
                {
                    "category": "adding_an_endpoint",
                    "statement": (
                        f"A new endpoint follows the same shape as {chain['entry_point']}: "
                        "a thin api/ handler that validates input, calls the "
                        "authorization check if the action is privileged, and "
                        "delegates to a services/ function."
                    ),
                    "evidence": chain["chain"],
                }
            )

        glossary = [
            {
                "term": cls["name"],
                "definition": (cls["docstring"] or f"{cls['name']} is a type defined in this codebase.").splitlines()[0],
                "evidence": [f"{f['path']}:{cls['line']}"],
            }
            for f in files
            for cls in f["classes"]
        ]

        return json.dumps(
            {
                "findings": findings,
                "glossary": glossary,
                "architecture_overview": FakeLLMClient._architecture_overview(components, feature_chains),
            }
        )

    @staticmethod
    def _find_auth_marker(files: list[dict]) -> dict | None:
        for f in files:
            if f["component"] == "tests":
                continue
            for fn in f["functions"]:
                if "auth" in fn["name"].lower():
                    return {"name": fn["name"], "evidence": f"{f['path']}:{fn['line']}"}
        return None

    @staticmethod
    def _find_validation_examples(files: list[dict], limit: int = 3) -> list[str]:
        evidence = []
        for f in files:
            if f["component"] == "tests":
                continue
            for fn in f["functions"]:
                if "ValueError" in fn.get("raises", []):
                    evidence.append(f"{f['path']}:{fn['line']}")
        return evidence[:limit]

    @staticmethod
    def _find_test_mapping(
        files: list[dict], import_graph: dict, by_path: dict[str, dict]
    ) -> list[dict]:
        mapping = []
        for f in files:
            if f["component"] == "tests":
                continue
            tests = sorted(
                test_path
                for test_path, targets in import_graph.items()
                if f["path"] in targets and by_path.get(test_path, {}).get("component") == "tests"
            )
            if tests:
                mapping.append({"source": f["path"], "tests": tests})
        return mapping

    @staticmethod
    def _find_feature_chains(
        files: list[dict], import_graph: dict, by_path: dict[str, dict]
    ) -> list[dict]:
        chains = []
        for f in files:
            if not f["routes"]:
                continue
            chain = [f["path"]]
            seen = {f["path"]}
            frontier = [f["path"]]
            while frontier:
                next_frontier = []
                for node in frontier:
                    for dep in import_graph.get(node, []):
                        if dep in seen or by_path.get(dep, {}).get("component") == "tests":
                            continue
                        seen.add(dep)
                        chain.append(dep)
                        next_frontier.append(dep)
                frontier = next_frontier
            chains.append({"entry_point": f["path"], "chain": chain})
        return chains

    @staticmethod
    def _architecture_overview(components: list[str], feature_chains: list[dict]) -> str:
        component_list = ", ".join(sorted(components))
        if not feature_chains:
            return f"The system is organized into: {component_list}."
        chain = feature_chains[0]
        return (
            f"The system is organized into {component_list}. A request enters "
            f"through {chain['chain'][0]} and flows through "
            f"{' -> '.join(chain['chain'][1:])}."
        )

    @staticmethod
    def _extract_policy(payload: dict) -> str:
        policy_text = payload["policy_text"]
        rules = []
        for index, m in enumerate(POLICY_ITEM_RE.finditer(policy_text), start=1):
            title = m.group("title").strip()
            description = m.group("description").strip()
            # Classify off the title first: descriptions often contain
            # incidental substring collisions (e.g. "invalid input" contains
            # "valid", which would wrongly tag an error-handling rule as
            # input-validation). Only fall back to the description if the
            # title itself doesn't signal a known category.
            category = _guess_category(title)
            if category == "general":
                category = _guess_category(description)
            severity = _CATEGORY_SEVERITY.get(category, "MEDIUM")
            rules.append(
                {
                    "id": f"POL-{index:03d}",
                    "description": description,
                    "category": category,
                    "severity": severity,
                    "detection_hint": category,
                }
            )
        return json.dumps({"rules": rules})

    @staticmethod
    def _review_violation(payload: dict) -> str:
        evidence = payload.get("deterministic_evidence")
        rule = payload["rule"]
        if evidence:
            return json.dumps(
                {
                    "status": "FAIL",
                    "confidence": 1.0,
                    "explanation": (
                        f"Rule {rule['id']} ({rule['description']}) is violated: "
                        f"{evidence}"
                    ),
                }
            )
        return json.dumps(
            {
                "status": "PASS",
                "confidence": 0.7,
                "explanation": (
                    f"No evidence of a violation of rule {rule['id']} was found "
                    "by the offline demo checker for this rule category."
                ),
            }
        )

    @staticmethod
    def _create_tech_spec(payload: dict) -> str:
        feature_request = payload["feature_request"].strip()
        rules = payload["rules"]

        # Drop markdown heading lines (e.g. a generic "# Feature Request")
        # so the overview reads as prose, not a heading followed by prose.
        request_body = " ".join(
            line.strip()
            for line in feature_request.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ) or feature_request

        overview = (
            f"Implement the following request under the governance rules listed "
            f"below: {request_body}"
        )
        requirements = [
            f"Satisfy {r['id']} ({r['category']}): {r['description']}" for r in rules
        ]
        security_categories = {"secrets", "authorization", "sql_injection", "audit_logging"}
        security_considerations = [
            f"{r['id']}: {r['description']}" for r in rules if r["category"] in security_categories
        ] or ["No category-specific security rules were extracted for this feature."]
        test_plan = [
            f"Add a test verifying compliance with {r['id']} ({r['category']})." for r in rules
        ]
        return json.dumps(
            {
                "overview": overview,
                "requirements": requirements,
                "security_considerations": security_considerations,
                "test_plan": test_plan,
            }
        )

    @staticmethod
    def _suggest_fix(payload: dict) -> str:
        rule = payload["rule"]
        return json.dumps(
            {
                "suggested_snippet": payload["code"],
                "rationale": (
                    f"No offline fix template is available for category "
                    f"'{rule['category']}'; re-run with --provider anthropic "
                    "for an LLM-generated fix."
                ),
            }
        )


class AnthropicClient:
    """Thin wrapper around the Anthropic Messages API."""

    def __init__(self, model: str = "claude-sonnet-4-5", api_key: str | None = None):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without the dep
            raise RuntimeError(
                "The 'anthropic' package is required for --provider anthropic. "
                "Install it with: pip install anthropic"
            ) from exc

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and "
                "add your key, or use --provider fake for the offline demo."
            )
        self._client = anthropic.Anthropic(api_key=key)
        self._model = model

    def complete(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )


def build_client(provider: str, fixtures: dict[str, str] | None = None) -> LLMClient:
    if provider == "fake":
        return FakeLLMClient(fixtures=fixtures)
    if provider == "anthropic":
        return AnthropicClient()
    raise ValueError(f"Unknown provider: {provider!r} (expected 'fake' or 'anthropic')")
