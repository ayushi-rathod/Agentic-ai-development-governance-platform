from pathlib import Path

import pytest

from src.agents.knowledge_extractor import KnowledgeExtractionAgent
from src.llm.client import FakeLLMClient


def _write(root: Path, rel_path: str, content: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


ROUTE_DECORATOR = (
    "def route(method, path):\n"
    "    def decorator(fn):\n"
    "        return fn\n"
    "    return decorator\n"
)


@pytest.fixture
def synthetic_repo(tmp_path) -> Path:
    _write(tmp_path, "api/__init__.py", f'"""API layer."""\n\n{ROUTE_DECORATOR}')
    _write(
        tmp_path,
        "api/thing.py",
        '"""Thing endpoint."""\n\n'
        "from api import route\n"
        "from auth.check import require_auth\n\n\n"
        '@route("POST", "/things")\n'
        "def create_thing(request):\n"
        '    """Create a thing."""\n'
        "    require_auth(request)\n"
        '    if "name" not in request:\n'
        '        raise ValueError("name is required")\n'
        "    return {}\n",
    )
    _write(tmp_path, "auth/__init__.py", "")
    _write(
        tmp_path,
        "auth/check.py",
        '"""Auth check."""\n\n'
        "def require_auth(request):\n"
        '    """Raise if the caller is not authorized."""\n'
        "    pass\n",
    )
    _write(tmp_path, "tests/__init__.py", "")
    _write(
        tmp_path,
        "tests/test_thing.py",
        '"""Tests."""\n\nfrom api.thing import create_thing\n',
    )
    return tmp_path


def _agent() -> KnowledgeExtractionAgent:
    return KnowledgeExtractionAgent(FakeLLMClient())


def test_feature_is_built_from_route_import_and_test_chain(synthetic_repo):
    report = _agent().extract(synthetic_repo)

    assert len(report.features) == 1
    feature = report.features[0]
    assert feature.id == "create-thing"
    assert feature.entry_points == ["api/thing.py"]
    assert "auth/check.py" in feature.dependencies
    assert feature.tests == ["tests/test_thing.py"]


def test_no_dependency_is_invented_for_something_never_imported(synthetic_repo):
    report = _agent().extract(synthetic_repo)
    assert "redis" not in {d.lower() for d in report.external_dependencies}
    assert report.external_dependencies == []


def test_authorization_finding_is_grounded_with_confidence(synthetic_repo):
    report = _agent().extract(synthetic_repo)
    auth_findings = [f for f in report.findings if f.category == "authorization_pattern"]
    assert len(auth_findings) == 1
    finding = auth_findings[0]
    assert finding.confidence > 0.9
    assert not finding.uncertain
    assert all(":" in e or e for e in finding.evidence)


def test_glossary_only_includes_grounded_terms(synthetic_repo):
    # No classes are defined in this synthetic repo, so glossary must be empty
    # rather than the model inventing a term.
    report = _agent().extract(synthetic_repo)
    assert report.glossary == []


def test_ungrounded_finding_is_marked_uncertain_and_evidence_stripped():
    """Directly exercises the grounding check with a fabricated citation,
    independent of what any particular repo happens to produce."""
    agent = _agent()
    evidence, confidence, uncertain = agent._ground(
        ["nonexistent/file.py:99"], known_paths={"real/file.py"}
    )
    assert evidence == []
    assert uncertain is True
    assert confidence < 0.5


def test_partially_grounded_finding_keeps_only_valid_evidence():
    agent = _agent()
    evidence, _confidence, uncertain = agent._ground(
        ["real/file.py:1", "fake/file.py:2"], known_paths={"real/file.py"}
    )
    assert evidence == ["real/file.py:1"]
    assert uncertain is True
