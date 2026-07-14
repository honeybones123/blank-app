"""Final boundary smoke for diagram modularisation.

This verifier checks that product page/root files no longer own figure
construction. Rendering calls may remain in pages; backup/sandbox files and
core non-page section engines are intentionally out of this page-ownership
boundary.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CONSTRUCTION_PATTERNS = {
    "go_figure": re.compile(r"\bgo\.Figure\s*\("),
    "make_subplots": re.compile(r"\bmake_subplots\s*\("),
    "fig_add_shape": re.compile(r"\bfig(?:_[A-Za-z0-9]+)?\.add_shape\s*\("),
    "fig_add_trace": re.compile(r"\bfig(?:_[A-Za-z0-9]+)?\.add_trace\s*\("),
    "plt_subplots": re.compile(r"\bplt\.subplots\s*\("),
}

SKIP_DIR_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "apps",
    "artifacts",
    "section_props",
    "tools",
    "ui",
}

SKIP_FILE_MARKERS = (
    "Elli",
    "99_UI_sandbox.py",
)


def _is_skipped(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIR_PARTS for part in rel.parts[:-1]):
        return True
    return any(marker in path.name for marker in SKIP_FILE_MARKERS)


def _scan_file(path: Path) -> list[str]:
    failures: list[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for idx, line in enumerate(text.splitlines(), start=1):
        for name, pattern in CONSTRUCTION_PATTERNS.items():
            if pattern.search(line):
                failures.append(f"{path.relative_to(ROOT)}:{idx}:{name}")
    return failures


def main() -> int:
    failures: list[str] = []
    scanned = 0
    for path in sorted(ROOT.glob("*.py")):
        if _is_skipped(path):
            continue
        scanned += 1
        failures.extend(_scan_file(path))

    if failures:
        print("DIAGRAM_REMAINING_HITS_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_REMAINING_HITS_SMOKE PASS")
    print(f"- root product python files scanned: {scanned}")
    print("- no page/root figure-construction tokens remain outside ui/diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
