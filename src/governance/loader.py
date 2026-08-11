"""Reads governance/ off disk into an ordered list of layers, highest
authority (global) first. Kept separate from GovernanceResolver so the
merge/enforcement logic in resolver.py has no filesystem dependency and is
trivially testable with in-memory text.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_EXCLUDED_GLOBAL_FILES = {"agent-governance.md"}  # documentation, not rules


@dataclass
class GovernanceSource:
    label: str
    text: str
    files: list[Path]


def load_layers(
    governance_root: Path, product: str, domain: str | None
) -> list[GovernanceSource]:
    layers: list[GovernanceSource] = []

    global_dir = governance_root / "global"
    global_files = sorted(
        p for p in global_dir.glob("*.md") if p.name not in _EXCLUDED_GLOBAL_FILES
    )
    if global_files:
        global_text = "\n\n".join(p.read_text(encoding="utf-8") for p in global_files)
        layers.append(GovernanceSource("global", global_text, global_files))

    product_file = governance_root / "products" / product / "policies.md"
    if product_file.exists():
        layers.append(
            GovernanceSource(
                f"product:{product}", product_file.read_text(encoding="utf-8"), [product_file]
            )
        )

    if domain:
        domain_file = (
            governance_root / "products" / product / "domains" / domain / "policies.md"
        )
        if domain_file.exists():
            layers.append(
                GovernanceSource(
                    f"domain:{domain}",
                    domain_file.read_text(encoding="utf-8"),
                    [domain_file],
                )
            )

    return layers
