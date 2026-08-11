"""Knowledge-extraction evals, run against the real bundled
examples/sample-product -- the four scenarios named in the brief this
feature was built from: known fact extraction, cross-file dependency,
unsupported claim, and domain glossary.
"""

from pathlib import Path

from src.agents.knowledge_extractor import KnowledgeExtractionAgent
from src.llm.client import FakeLLMClient

ROOT = Path(__file__).resolve().parent.parent.parent
REPO = ROOT / "examples" / "sample-product"


def _report():
    return KnowledgeExtractionAgent(FakeLLMClient()).extract(REPO)


def test_known_fact_authorization_is_wired_through_one_module():
    """The sample repository clearly wires authorization through
    auth/authorization.py's require_authorization(). Expected: the
    finding is extracted, citing that file."""
    report = _report()
    auth_findings = [f for f in report.findings if f.category == "authorization_pattern"]

    assert len(auth_findings) == 1
    finding = auth_findings[0]
    assert not finding.uncertain
    assert finding.confidence >= 0.9
    assert any(e.startswith("auth/authorization.py") for e in finding.evidence)
    assert "require_authorization" in finding.statement


def test_cross_file_dependency_rotate_key_feature_spans_route_service_auth_tests():
    """The API-key-rotation feature requires route + service +
    authorization + tests. Expected: the extractor identifies those
    relationships in one Feature record."""
    report = _report()
    feature = next(f for f in report.features if f.id == "rotate-api-key")

    assert feature.entry_points == ["api/keys.py"]
    assert "auth/authorization.py" in feature.dependencies
    assert "services/key_service.py" in feature.dependencies
    assert feature.tests == ["tests/test_keys.py"]


def test_unsupported_claim_redis_is_never_reported_as_a_dependency():
    """There is no evidence the sample application uses Redis. Expected:
    the extractor must not claim Redis is part of the architecture.
    Dependency extraction has no model in the loop at all (see
    KnowledgeExtractionAgent._build_dependencies), so this is a
    structural guarantee, not a hope that the model behaves."""
    report = _report()
    all_targets = {d.target.lower() for d in report.dependencies}
    assert "redis" not in all_targets
    assert report.external_dependencies == ["bcrypt"]


def test_domain_glossary_term_is_extracted_with_evidence():
    """ApiKey is a domain-specific concept clearly represented in code
    (models/key.py, with a docstring). Expected: the term is included
    with evidence pointing at its real definition site."""
    report = _report()
    term = next((t for t in report.glossary if t.term == "ApiKey"), None)

    assert term is not None
    assert term.evidence == ["models/key.py:9"]
    assert "credential" in term.definition.lower() or "key" in term.definition.lower()


def test_every_finding_and_glossary_term_cites_a_real_file():
    """Blanket check: nothing in the published report can cite a file
    that doesn't exist in the repository."""
    report = _report()
    known_paths = {
        "api/__init__.py",
        "api/keys.py",
        "api/users.py",
        "auth/__init__.py",
        "auth/authorization.py",
        "models/__init__.py",
        "models/account.py",
        "models/key.py",
        "services/__init__.py",
        "services/account_service.py",
        "services/audit.py",
        "services/key_service.py",
        "tests/__init__.py",
        "tests/test_keys.py",
        "tests/test_users.py",
    }
    for finding in report.findings:
        for citation in finding.evidence:
            assert citation.split(":")[0] in known_paths, citation
    for term in report.glossary:
        for citation in term.evidence:
            assert citation.split(":")[0] in known_paths, citation
