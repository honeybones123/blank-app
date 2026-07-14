from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PUBLICATION = ROOT / "design_brain" / "publication.py"
INPUTS_PAGE = ROOT / "inputs_page.py"


HELPERS: tuple[str, ...] = (
    "publication_item_family",
    "_recover_cleanup_action_publication_item",
    "_target_band_reached_publication_item",
    "_bending_fail_no_valid_repair_publication_item",
    "_serviceability_governs_terminal_publication_item",
    "_route_shear_fail_family_publication",
    "_route_combined_fail_family_publication",
    "enforce_family_selection_publication_contract",
    "enforce_underdesign_repair_publication_boundary",
    "enforce_design_brain_publication_contract",
)

FOCUSED_COMMANDS: tuple[tuple[str, str, int], ...] = (
    (
        "final_publication_boundary",
        "tools/verification/design_guide_final_publication_boundary_snapshot.py",
        90,
    ),
    (
        "cta_source_precedence",
        "tools/verification/design_brain_shared_final_publication_cta_source_precedence_lock.py",
        120,
    ),
    (
        "contract_violation_tone_wording",
        "tools/verification/design_guide_contract_violation_tone_and_wording_snapshot.py",
        90,
    ),
    (
        "stale_active_failure_publication_guard",
        "tools/verification/design_guide_stale_active_failure_publication_guard_snapshot.py",
        90,
    ),
    (
        "bending_fail_final_override_family_first",
        "tools/verification/design_guide_bending_fail_final_override_family_first_regression.py",
        90,
    ),
    (
        "combined_zero_shear_cleanup_publication",
        "tools/verification/design_guide_combined_zero_shear_cleanup_publication_snapshot.py",
        90,
    ),
    (
        "serviceability_publication_bridge",
        "tools/verification/families/serviceability_governs_publication_bridge_snapshot.py",
        90,
    ),
    (
        "combined_fail_publication_regression",
        "tools/verification/families/combined_bending_shear_fail_publication_regression.py",
        90,
    ),
    (
        "bending_overdesign_publication_regression",
        "tools/verification/families/bending_overdesign_governs_publication_regression.py",
        90,
    ),
    (
        "bending_fail_shear_overdesign_publication_regression",
        "tools/verification/families/bending_fail_shear_overdesign_governs_publication_regression.py",
        90,
    ),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _run(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "name": name,
        "command": " ".join(command),
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _function_bodies(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    rows: dict[str, str] = {}
    lines = source.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name not in HELPERS:
            continue
        start = max(1, int(getattr(node, "lineno", 1)))
        end = int(getattr(node, "end_lineno", start))
        rows[node.name] = "\n".join(lines[start - 1 : end])
    return rows


def _line_no(source: str, needle: str) -> int | None:
    index = source.find(needle)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def _build_source_checks() -> dict[str, Any]:
    publication_source = _read(PUBLICATION)
    inputs_source = _read(INPUTS_PAGE)
    bodies = _function_bodies(publication_source)
    helper_rows = {}
    for name in HELPERS:
        body = bodies.get(name, "")
        helper_rows[name] = {
            "present": bool(body),
            "line": _line_no(publication_source, f"def {name}("),
            "no_streamlit": "streamlit" not in body and "st." not in body,
            "no_inputs_page_import": "inputs_page" not in body,
            "no_session_state": "session_state" not in body,
            "no_apply_execution": "handle_apply_buttons" not in body
            and "_queue_primary_design_guide_button_action" not in body,
            "no_render_execution": "st.markdown" not in body and "render_final_panel" not in body,
        }
    private_helper_names = [name for name in HELPERS if name.startswith("_")]
    return {
        "helpers": helper_rows,
        "publication_module_no_streamlit_import": "import streamlit" not in publication_source.lower()
        and "from streamlit" not in publication_source.lower(),
        "publication_module_no_inputs_page_import": "inputs_page" not in publication_source,
        "public_enforcers_imported_by_inputs_page_only": all(
            name in inputs_source
            for name in (
                "enforce_design_brain_publication_contract",
                "enforce_family_selection_publication_contract",
                "enforce_underdesign_repair_publication_boundary",
            )
        ),
        "private_helpers_not_called_from_inputs_page": all(name not in inputs_source for name in private_helper_names),
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Shared Publication Recovery / Enforcement Contract Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Ownership Boundary",
        "",
        "These helpers are pure publication recovery/enforcement helpers. They may normalize or reject publication payloads, but must not render UI, execute Apply, read Streamlit/session state, or run solver/family runtime logic.",
        "",
        "## Helpers",
        "",
        "| Helper | Present | Line |",
        "| --- | --- | --- |",
    ]
    for name, row in (snapshot.get("source_checks", {}).get("helpers") or {}).items():
        lines.append(f"| `{name}` | `{row.get('present')}` | `{row.get('line')}` |")
    lines.extend(["", "## Focused Regressions", "", "| Gate | Status |", "| --- | --- |"])
    for row in snapshot.get("focused_results") or []:
        lines.append(f"| `{row['name']}` | `{row['status']}` |")
    lines.extend(["", "## Blockers", ""])
    if snapshot.get("blockers"):
        lines.extend(f"- {blocker}" for blocker in snapshot["blockers"])
    else:
        lines.append("- none")
    lines.append(f"\nJSON: `{snapshot['artifact']}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    focused_results = [
        _run(
            "py_compile_publication_recovery_lock",
            [
                sys.executable,
                "-m",
                "py_compile",
                "design_brain/publication.py",
                "tools/verification/design_brain_shared_publication_recovery_enforcement_contract_lock.py",
            ],
            90,
        )
    ]
    for name, script, timeout in FOCUSED_COMMANDS:
        focused_results.append(_run(name, [sys.executable, script], timeout))

    source_checks = _build_source_checks()
    blockers: list[str] = []
    for name, row in (source_checks.get("helpers") or {}).items():
        for key, value in row.items():
            if key == "line":
                continue
            if value is not True:
                blockers.append(f"{name}:{key}")
    for key, value in source_checks.items():
        if key == "helpers":
            continue
        if value is not True:
            blockers.append(f"source:{key}")
    for row in focused_results:
        if row.get("status") != "PASS":
            blockers.append(f"focused gate failed: {row['name']}")

    status = "LOCKED" if not blockers else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_shared_publication_recovery_enforcement_contract_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_publication_recovery_enforcement_contract_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_publication_recovery_enforcement_contract_lock.v1",
        "status": status,
        "lock_status": status,
        "component": "publication recovery/enforcement helpers",
        "source_checks": source_checks,
        "focused_results": focused_results,
        "blockers": list(dict.fromkeys(blockers)),
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_shared_publication_recovery_enforcement_contract_lock {status}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    if blockers:
        print("blockers=" + "; ".join(snapshot["blockers"]))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
