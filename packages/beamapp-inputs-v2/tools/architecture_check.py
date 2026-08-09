"""Repository-owned architecture guard for the standalone Inputs V2 lab."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "inputs_v2"
FORBIDDEN_RUNTIME = ("complete-app - Runtime", "state_and_helpers", "inputs_page_modules")
FORBIDDEN_IN_DOMAIN = ("streamlit", "inputs_v2.presentation", "inputs_v2.infrastructure")
FORBIDDEN_IN_ENGINEERING = ("streamlit", "inputs_v2.presentation", "inputs_v2.infrastructure")
FORBIDDEN_SUMMARY_TABLE = ("summarytable", "summary_table", "summary table")
LAYER_FORBIDDEN = {
    "domain": ("inputs_v2.application", "inputs_v2.engineering_port", "inputs_v2.infrastructure", "inputs_v2.presentation"),
    "engineering_port": ("inputs_v2.application", "inputs_v2.infrastructure", "inputs_v2.presentation"),
    "application": ("inputs_v2.presentation",),
    "infrastructure": ("inputs_v2.presentation",),
}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def fail(message: str) -> None:
    print(f"ARCHITECTURE CHECK FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    files = tuple(SRC.rglob("*.py"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        layer = next((part for part in LAYER_FORBIDDEN if part in path.parts), None)
        if layer:
            imported = imports(path)
            if any(name == token or name.startswith(token + ".") for token in LAYER_FORBIDDEN[layer] for name in imported):
                fail(f"reverse layer import in {path.relative_to(ROOT)}")
        if any(token in text for token in FORBIDDEN_RUNTIME):
            fail(f"Runtime reference in {path.relative_to(ROOT)}")
        if "domain" in path.parts and any(
            any(name == token or name.startswith(token + ".") for name in imports(path))
            for token in FORBIDDEN_IN_DOMAIN
        ):
            fail(f"forbidden domain import in {path.relative_to(ROOT)}")
        if "engineering_port" in path.parts and any(
            any(name == token or name.startswith(token + ".") for name in imports(path))
            for token in FORBIDDEN_IN_ENGINEERING
        ):
            fail(f"forbidden engineering import in {path.relative_to(ROOT)}")
        if "components" in path.parts and "session_state" in text:
            fail(f"component accesses raw session state in {path.relative_to(ROOT)}")
        if "components" in path.parts and "private" in text.lower():
            fail(f"component references private implementation in {path.relative_to(ROOT)}")
        if path == SRC / "app.py" and (
            "FixtureCalculator().calculate" in text
            or "from inputs_v2.engineering_port.fixture_calculator import" in text
            or "from inputs_v2.infrastructure" in text
        ):
            fail("presentation entry point bypasses the application calculation boundary")
        if any(token in text.lower() for token in FORBIDDEN_SUMMARY_TABLE):
            fail(f"summary tables are forbidden for V1 parity in {path.relative_to(ROOT)}")

    css = (SRC / "presentation" / "foundations.py").read_text(encoding="utf-8")
    selectors = re.findall(r"(?m)^\s*(\.[A-Za-z0-9_-]+(?:\s+\.[A-Za-z0-9_-]+)*)\s*\{", css)
    for selector in selectors:
        selector = selector.strip()
        if selector != ".stApp" and not selector.startswith(".inputs-v2-root"):
            fail(f"unscoped CSS selector {selector}")

    application_files = tuple((SRC / "application").rglob("*.py"))
    classifier_consumers = tuple(
        path
        for path in application_files
        if path.name != "design_brain_families.py"
        and "classify_design_family(" in path.read_text(encoding="utf-8")
    )
    if classifier_consumers != (SRC / "application" / "design_guide_orchestrator.py",):
        fail("the family classifier must have exactly one orchestrator consumer")

    apply_owners = tuple(
        path
        for path in files
        if "apply_allowed=" in path.read_text(encoding="utf-8")
    )
    if apply_owners != (SRC / "application" / "design_brain" / "family_owners.py",):
        fail("Apply intent must have exactly one family-decision owner")

    service = (SRC / "application" / "design_brain_service.py").read_text(
        encoding="utf-8"
    )
    if service.count("evaluate_candidate(current, candidate") != 1:
        fail("candidate evaluation must enter through one shared gateway")
    if "def publish_preview(" not in service:
        fail("selected proxy evidence is not separated from the publishable result")
    if "self.search_profile.max_consecutive_infeasible" not in service:
        fail("the configured monotonic infeasible-search limit is not bound")

    apply_boundary = (
        SRC / "application" / "design_brain_apply.py"
    ).read_text(encoding="utf-8")
    for required in (
        "width_locked=current.width_locked",
        "depth_locked=current.depth_locked",
        'ApplyOutcome(False, "width_locked", current)',
        'ApplyOutcome(False, "depth_locked", current)',
        'ApplyOutcome(False, "lock_state_mutation_forbidden", current)',
    ):
        if required not in apply_boundary:
            fail("the universal candidate boundary does not preserve geometry locks")

    bending_overdesign = (
        SRC / "application" / "design_brain" / "bending_overdesign_pipeline.py"
    ).read_text(encoding="utf-8")
    if "monotonic_bending_capacity_ceiling_proven" not in bending_overdesign:
        fail("bounded bending cleanup lacks a proved monotonic stop")

    pipeline_root = SRC / "application" / "design_brain"
    for path in pipeline_root.glob("*pipeline.py"):
        source = path.read_text(encoding="utf-8")
        if any(
            token in source
            for token in (
                "self._calculate(updated_inputs)",
                "self._calculate(candidate.proposal)",
                "self._calculate(proposal)",
            )
        ):
            fail(f"proposal recalculated outside gateway in {path.relative_to(ROOT)}")
        for match in re.finditer(r"self\._evaluate\((.*?)\)", source, re.DOTALL):
            if "stage_id=" not in match.group(0):
                fail(f"candidate lacks family-owned stage in {path.relative_to(ROOT)}")

    print(f"Architecture check passed ({len(files)} Python files).")


if __name__ == "__main__":
    main()
