from __future__ import annotations

import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app.py"
PERMANENT_PAGE = ROOT / "inputs_page.py"
STAGING_SHELL_PAGE = ROOT / "inputs_page_shell.py"
ROUTE_BRIDGE = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"


def _source(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _route_target() -> str:
    source = _source(APP)
    if not source:
        return ""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "PAGES" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key, value in zip(node.value.keys, node.value.values):
            if not (isinstance(key, ast.Constant) and key.value == "inputs"):
                continue
            if (
                isinstance(value, ast.Tuple)
                and len(value.elts) >= 2
                and isinstance(value.elts[1], ast.Attribute)
                and isinstance(value.elts[1].value, ast.Name)
            ):
                return f"{value.elts[1].value.id}.{value.elts[1].attr}"
    return ""


def _imports_inputs_page(source: str) -> bool:
    return bool(re.search(r"(?:^|\n)\s*(?:import\s+inputs_page\b|from\s+inputs_page\b)", source))


def _imports_shell_page(source: str) -> bool:
    return bool(re.search(r"(?:^|\n)\s*(?:import\s+inputs_page_shell\b|from\s+inputs_page_shell\b)", source))


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    app_source = _source(APP)
    permanent_source = _source(PERMANENT_PAGE)
    route_bridge_source = _source(ROUTE_BRIDGE)
    app_contract_bridge_source = _source(APP_CONTRACT_BRIDGE)
    route_target = _route_target()

    checks = {
        "permanent_inputs_page_exists": PERMANENT_PAGE.exists(),
        "staging_shell_removed": not STAGING_SHELL_PAGE.exists(),
        "app_does_not_import_staging_shell_page": not _imports_shell_page(app_source),
        "inputs_route_points_to_permanent_page": route_target in {
            "inputs_page.render_inputs",
            "inputs_page.render_inputs_page",
        },
        "permanent_page_has_no_temporary_legacy_coordinators": "TEMPORARY_LEGACY_COORDINATOR" not in permanent_source,
        "permanent_page_does_not_delegate_to_old_render_inputs": "render_legacy_inputs_page" not in permanent_source,
        "permanent_page_has_render_entrypoint": "render_inputs" in permanent_source,
        "permanent_page_has_no_old_render_inputs_function": "def render_inputs(" not in permanent_source,
        "permanent_page_has_no_design_guide_monolith": "def _render_fast_design_guidance_panel(" not in permanent_source,
        "route_bridge_absent_or_does_not_import_old_inputs_page": not ROUTE_BRIDGE.exists()
        or not _imports_inputs_page(route_bridge_source),
        "app_contract_bridge_absent_or_does_not_import_old_inputs_page": not APP_CONTRACT_BRIDGE.exists()
        or not _imports_inputs_page(app_contract_bridge_source),
    }
    failures = [name for name, passed in checks.items() if not passed]
    decision = "INPUTS_PAGE_FINAL_SHELL_DELETION_LOCKED" if not failures else "INPUTS_PAGE_FINAL_SHELL_DELETION_BLOCKED"

    payload = {
        "audit": "inputs_page_final_shell_deletion_lock",
        "timestamp": timestamp,
        "decision": decision,
        "status": "PASS" if not failures else "FAIL",
        "route_target": route_target,
        "checks": checks,
        "failures": failures,
        "scope": "Strict final-phase gate for replacing inputs_page.py with the shell.",
        "required_before_delete": [
            "route points to permanent inputs_page shell",
            "staging shell removed",
            "permanent inputs_page has no old monolith markers",
            "permanent inputs_page has no temporary legacy coordinators",
            "route/app contract bridges no longer import old inputs_page",
        ],
    }

    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_page_final_shell_deletion_lock_{timestamp}.json"
    report_path = audit_dir / f"inputs_page_final_shell_deletion_lock_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Final Shell Deletion Lock",
                "",
                f"Decision: `{decision}`",
                f"Route target: `{route_target}`",
                "",
                "## Checks",
                "",
                *[f"- `{name}`: `{passed}`" for name, passed in checks.items()],
                "",
                "## Failures",
                "",
                *[f"- `{name}`" for name in failures],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(decision)
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ",".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
