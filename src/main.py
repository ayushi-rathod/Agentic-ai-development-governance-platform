"""CLI entry point. Three subcommands:

  review             Ad-hoc policy review of one file against one policy
                      document, optionally also against knowledge
                      extracted from the repo it lives in:

                        python -m src.main review \\
                            --policy policies/sample_engineering_policy.md \\
                            --code examples/violating_code.py \\
                            --reference examples/compliant_code.py

                        python -m src.main review \\
                            --policy policies/sample_engineering_policy.md \\
                            --knowledge knowledge/ \\
                            --code examples/sample-product/api/keys.py

  feature             The governed feature-development workflow: tech
                      spec -> implement -> review -> QC gate -> human
                      approval, driven by layered governance (global ->
                      product -> domain) and
                      workflows/feature-development.yaml:

                        python -m src.main feature --approve

  knowledge-extract   Analyzes an existing repository and writes
                      KNOWLEDGE.md, FEATURES.yaml, GLOSSARY.md,
                      architecture.md, and knowledge.json:

                        python -m src.main knowledge-extract \\
                            --repo examples/sample-product

All three are offline by default (no API key needed). Add --provider
anthropic (with ANTHROPIC_API_KEY set) to use a real model instead of the
offline demo client.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from src.agents.code_reviewer import CodeReviewAgent
from src.agents.evaluator import EvaluationAgent
from src.agents.fixer import FixAgent
from src.agents.implementation import ImplementationAgent
from src.agents.knowledge_extractor import KnowledgeExtractionAgent
from src.agents.policy_extractor import PolicyExtractorAgent
from src.agents.tech_spec import TechSpecAgent
from src.governance.loader import load_layers
from src.governance.resolver import GovernanceResolver, GovernanceViolationError
from src.knowledge.artifacts import write_artifacts
from src.llm.client import build_client
from src.models.knowledge import (
    ConventionObservation,
    ConventionStatus,
    KnowledgeReport,
)
from src.models.policy import EvaluationReport, FixSuggestion, PolicyRule, Status
from src.models.workflow import ApprovalStatus, QCDecision
from src.orchestration.feature_workflow import FeatureWorkflow
from src.orchestration.qc_gate import QCGate
from src.orchestration.workflow import Orchestrator, WorkflowResult

_STATUS_LABEL = {Status.PASS: "PASS", Status.FAIL: "FAIL", Status.WARNING: "WARN"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="Ad-hoc review of one file against one policy document.")
    review.add_argument("--policy", required=True, help="Path to a policy markdown/text file.")
    review.add_argument("--code", required=True, help="Path to the Python file to review.")
    review.add_argument(
        "--reference",
        default=None,
        help="Optional path to an already-compliant version of the code, "
        "evaluated too so you can see the pass path.",
    )
    review.add_argument(
        "--knowledge",
        default=None,
        help="Optional path to a knowledge/ directory (from knowledge-extract) "
        "to also check code against established repository conventions.",
    )
    review.add_argument("--provider", choices=["fake", "anthropic"], default="fake")

    feature = subparsers.add_parser("feature", help="Governed feature-development workflow.")
    feature.add_argument(
        "--feature-request",
        default="examples/sample-feature/feature-request.md",
        help="Path to a feature request file.",
    )
    feature.add_argument("--feature-id", default="FEAT-001")
    feature.add_argument("--product", default="sample-product")
    feature.add_argument(
        "--domain",
        default="payment-service",
        help="Domain within --product, or '' to skip the domain governance layer.",
    )
    feature.add_argument("--provider", choices=["fake", "anthropic"], default="fake")
    feature.add_argument(
        "--approve", action="store_true", help="Grant human approval if the QC gate passes."
    )
    feature.add_argument(
        "--approver", default=None, help="Overrides the product's default_approver."
    )
    feature.add_argument(
        "--max-remediation-attempts",
        type=int,
        default=None,
        help="Overrides workflows/feature-development.yaml.",
    )
    feature.add_argument(
        "--save-artifacts",
        default=None,
        help="Directory to write generated-tech-spec.md, source/, and a "
        "traceability report into.",
    )

    knowledge_extract = subparsers.add_parser(
        "knowledge-extract", help="Extract reusable knowledge from an existing repository."
    )
    knowledge_extract.add_argument("--repo", required=True, help="Path to the repository to analyze.")
    knowledge_extract.add_argument(
        "--output", default="knowledge", help="Directory to write the knowledge artifacts into."
    )
    knowledge_extract.add_argument("--provider", choices=["fake", "anthropic"], default="fake")

    return parser.parse_args(argv)


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _print_rules(rules: list[PolicyRule]) -> None:
    print(f"Governance rules resolved ({len(rules)}):")
    for rule in rules:
        layer = f" [{rule.layer}]" if rule.layer else ""
        print(f"  [{rule.id}]{layer} ({rule.severity.value}) {rule.description}")
    print()


def _print_report(title: str, report: EvaluationReport, fixes: list[FixSuggestion]) -> None:
    fixes_by_rule = {fix.rule_id: fix for fix in fixes}
    header = f"{title}  ({report.code_source})"
    print(header)
    print("-" * len(header))
    for result in report.results:
        print(f"[{result.rule_id}] {result.description}")
        print(f"  Status: {_STATUS_LABEL[result.status]}")
        print(f"  File: {report.code_source}")
        print(f"  Evidence: {result.evidence}")
        print(f"  Explanation: {result.explanation}")
        print(f"  Confidence: {result.confidence:.2f}  Method: {result.method.value}")
        fix = fixes_by_rule.get(result.rule_id)
        if fix is not None:
            print(f"  Recommendation: {fix.rationale}")
            print("  Suggested fix:\n      " + fix.suggested_snippet.replace("\n", "\n      "))
        print()
    print(
        f"Summary: {report.pass_count} passed, {report.fail_count} failed, "
        f"{report.warning_count} warnings -> "
        f"{'PASS' if report.passed else 'FAIL'}"
    )
    print()


def _print_conventions(observations: list[ConventionObservation]) -> None:
    print("Repository convention notes (informational -- not policy failures)")
    print("-" * 68)
    if not observations:
        print("(no established convention available to check against, or none applicable)")
        print()
        return
    for obs in observations:
        print(f"[{obs.status.value}] {obs.convention}")
        print(f"  {obs.description}")
        print(f"  Evidence: {obs.evidence}")
        print(f"  {obs.note}")
        print()
    deviations = sum(1 for o in observations if o.status is ConventionStatus.DEVIATION)
    print(f"Convention summary: {len(observations) - deviations} followed, {deviations} deviation(s)")
    print()


def run_review(args: argparse.Namespace) -> int:
    try:
        policy_text = _read(args.policy)
        code_text = _read(args.code)
        reference_text = _read(args.reference) if args.reference else None
    except OSError as exc:
        print(f"error: could not read input file: {exc}", file=sys.stderr)
        return 1

    knowledge: KnowledgeReport | None = None
    if args.knowledge:
        knowledge_json = Path(args.knowledge) / "knowledge.json"
        try:
            knowledge = KnowledgeReport.model_validate_json(knowledge_json.read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"error: could not read knowledge from {args.knowledge}: {exc}", file=sys.stderr)
            return 1

    try:
        client = build_client(args.provider)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    orchestrator = Orchestrator(client)

    try:
        result: WorkflowResult = orchestrator.run(
            policy_text=policy_text,
            policy_source=args.policy,
            code_text=code_text,
            code_source=args.code,
            reference_code=reference_text,
            reference_source=args.reference or "<reference>",
        )
    except (ValueError, SyntaxError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _print_rules(result.rules)
    _print_report("Evaluation", result.initial_report, result.fixes)
    if result.reference_report is not None:
        _print_report("Reference evaluation", result.reference_report, [])

    if knowledge is not None:
        reviewer = CodeReviewAgent(client)
        _print_conventions(reviewer.check_conventions(code_text, knowledge))

    return 0 if result.initial_report.passed else 1


def run_knowledge_extract(args: argparse.Namespace) -> int:
    try:
        client = build_client(args.provider)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        report = KnowledgeExtractionAgent(client).extract(args.repo)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"error: could not extract knowledge from {args.repo}: {exc}", file=sys.stderr)
        return 1

    print(f"Components discovered ({len(report.components)}):")
    for component in report.components:
        print(f"  {component.name}/ -- {component.description} ({len(component.files)} files)")
    print()

    print(f"Features discovered ({len(report.features)}):")
    for feature in report.features:
        print(f"  {feature.id}: {feature.description}")
        print(f"    entry points: {', '.join(feature.entry_points)}")
        print(f"    dependencies: {', '.join(feature.dependencies) or '(none)'}")
        print(f"    tests: {', '.join(feature.tests) or '(none found)'}")
    print()

    external = report.external_dependencies
    print(f"External dependencies: {', '.join(external) if external else '(none found)'}")
    print()

    print("Architecture observations:")
    print(f"  {report.architecture_overview or '(none generated)'}")
    print()

    print(f"Evidence-backed findings: {report.evidence_backed_count} / {len(report.findings)}")
    uncertain = report.uncertain_findings
    if uncertain:
        print(f"Uncertain findings requiring human review ({len(uncertain)}):")
        for finding in uncertain:
            print(f"  [{finding.id}] {finding.category}: {finding.statement}")
    else:
        print("Uncertain findings requiring human review: none")
    print()

    paths = write_artifacts(report, Path(args.output))
    print("Generated artifacts:")
    for name, path in paths.items():
        print(f"  {name}: {path}")

    return 0


def run_feature(args: argparse.Namespace) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    domain = args.domain or None

    try:
        feature_request = _read(args.feature_request)
    except OSError as exc:
        print(f"error: could not read feature request: {exc}", file=sys.stderr)
        return 1

    governance_root = repo_root / "governance"
    layers = load_layers(governance_root, args.product, domain)
    if not layers:
        print(
            f"error: no governance layers found under {governance_root} for "
            f"product={args.product!r} domain={domain!r}",
            file=sys.stderr,
        )
        return 1

    workflow_config = _load_yaml(repo_root / "workflows" / "feature-development.yaml")
    gates = workflow_config.get("gates", {})
    max_attempts = args.max_remediation_attempts
    if max_attempts is None:
        max_attempts = gates.get("qc", {}).get("max_remediation_attempts", 1)
    approval_required = gates.get("human_approval", {}).get("required", True)
    approved = args.approve or not approval_required

    approver = args.approver
    if approver is None:
        product_config = _load_yaml(governance_root / "products" / args.product / "product.yaml")
        approver = product_config.get("default_approver", "engineering-lead")

    fixtures: dict[str, str] = {}
    if args.provider == "fake":
        fixture_dir = repo_root / "examples" / "sample-feature" / "fixtures"
        try:
            fixtures = {
                "initial_implementation": (fixture_dir / "draft_implementation.py").read_text(
                    encoding="utf-8"
                ),
                "remediated_implementation": (
                    fixture_dir / "remediated_implementation.py"
                ).read_text(encoding="utf-8"),
            }
        except OSError as exc:
            print(f"error: could not read offline demo fixtures: {exc}", file=sys.stderr)
            return 1

    try:
        client = build_client(args.provider, fixtures=fixtures)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    extractor = PolicyExtractorAgent(client)
    resolver = GovernanceResolver(extractor)
    try:
        rule_set = resolver.resolve(layers)
    except GovernanceViolationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    reviewer = CodeReviewAgent(client)
    fixer = FixAgent(client)
    workflow = FeatureWorkflow(
        tech_spec_agent=TechSpecAgent(client),
        implementation_agent=ImplementationAgent(client),
        evaluator=EvaluationAgent(reviewer),
        qc_gate=QCGate(),
    )

    try:
        result = workflow.run(
            feature_id=args.feature_id,
            feature_request=feature_request,
            product=args.product,
            domain=domain,
            governance_rules=rule_set.rules,
            approved=approved,
            approver=approver,
            max_remediation_attempts=max_attempts,
        )
    except (ValueError, SyntaxError, NotImplementedError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _print_rules(result.governance_rules)
    print(result.tech_spec.render_markdown())

    for attempt in result.attempts:
        fixes = (
            fixer.propose_fixes(attempt.code, attempt.report.results, result.governance_rules)
            if attempt.report.fail_count
            else []
        )
        _print_report(f"Attempt {attempt.attempt}", attempt.report, fixes)

    print(f"QC decision: {result.qc_decision.value}")
    approval_line = f"Approval status: {result.approval_status.value}"
    if result.approver:
        approval_line += f" (by {result.approver})"
    print(approval_line)
    if result.approval_status is ApprovalStatus.PENDING:
        print("Awaiting human approval -- re-run with --approve to confirm.")
    print()
    print(result.render_traceability_markdown())

    if args.save_artifacts:
        out_dir = Path(args.save_artifacts)
        source_dir = out_dir / "source"
        out_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "generated-tech-spec.md").write_text(
            result.tech_spec.render_markdown(), encoding="utf-8"
        )
        (source_dir / "rotate_api_key.py").write_text(result.final_attempt.code, encoding="utf-8")
        (out_dir / "traceability-report.md").write_text(
            result.render_traceability_markdown(), encoding="utf-8"
        )

    if result.qc_decision is QCDecision.BLOCK:
        return 1
    if result.approval_status is ApprovalStatus.PENDING:
        return 2
    return 0


def main() -> None:
    args = parse_args()
    if args.command == "review":
        sys.exit(run_review(args))
    elif args.command == "feature":
        sys.exit(run_feature(args))
    else:
        sys.exit(run_knowledge_extract(args))


if __name__ == "__main__":
    main()
