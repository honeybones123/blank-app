from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

FORBIDDEN_IMPORT_ROOTS = {
    "inputs_page",
    "streamlit",
    "design_guide_page",
    "app",
}

REQUIRED_SYMBOLS = {
    "build_design_guide_controller_presentation_request",
    "run_design_guide_controller_presentation_adapter",
    "stable_design_guide_controller_request_hash",
    "design_guide_controller_request_memo_payload",
    "run_design_guide_controller_compute_selection_trace_only",
    "run_design_guide_controller_compute_publication_handoff_trace_only",
}

FOCUSED_COMMANDS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("controller_input_snapshot_lock", ("tools/verification/design_brain_shared_controller_input_snapshot_lock.py",), 90),
    ("controller_trace_only_parity", ("tools/verification/design_guide_controller_trace_only_parity_snapshot.py",), 90),
    ("controller_publication_authority_cutover", ("tools/verification/design_guide_controller_publication_authority_cutover.py",), 120),
    ("controller_compute_handoff_object", ("tools/verification/design_guide_controller_compute_handoff_object_snapshot.py",), 90),
    ("controller_compute_selector_object", ("tools/verification/design_guide_controller_compute_selector_object_snapshot.py",), 90),
)


def _run(name: str, args: tuple[str, ...], timeout: int) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "name": name,
        "command": " ".join(["python", *args]),
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": proc.stdout.strip().splitlines()[-14:],
        "stderr_tail": proc.stderr.strip().splitlines()[-14:],
    }


def _imports_and_symbols() -> tuple[list[str], set[str]]:
    source = CONTROLLER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            symbols.add(node.name)
    return sorted(set(imports)), symbols


def _forbidden_imports(imports: list[str]) -> list[str]:
    out: list[str] = []
    for name in imports:
        for forbidden in FORBIDDEN_IMPORT_ROOTS:
            if name == forbidden or name.startswith(forbidden + "."):
                out.append(name)
    return sorted(set(out))


def _latest(prefix: str) -> str | None:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    return str(paths[-1]) if paths else None


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Shared Controller Orchestration Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Static Boundary Checks",
        "",
    ]
    for key, value in snapshot.get("static_checks", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Focused Gates", "", "| Gate | Status | Command |", "| --- | --- | --- |"])
    for result in snapshot.get("focused_results") or []:
        lines.append(f"| {result['name']} | `{result['status']}` | `{result['command']}` |")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {item}" for item in snapshot.get("blockers") or ["none"])
    lines.extend(["", "## Latest Artifacts", ""])
    for key, value in (snapshot.get("latest_artifacts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.append(f"\nJSON: `{snapshot['artifact']}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_result = _run(
        "py_compile_controller_orchestration_lock",
        (
            "-m",
            "py_compile",
            "design_brain/design_guide_controller.py",
            "tools/verification/design_brain_shared_controller_orchestration_lock.py",
        ),
        90,
    )
    imports, symbols = _imports_and_symbols()
    forbidden_imports = _forbidden_imports(imports)
    missing_symbols = sorted(REQUIRED_SYMBOLS - symbols)
    static_checks = {
        "no_page_ui_or_session_imports": not forbidden_imports,
        "required_controller_boundary_symbols_present": not missing_symbols,
        "controller_has_request_hash_boundary": "stable_design_guide_controller_request_hash" in symbols,
        "controller_has_presentation_adapter_boundary": "run_design_guide_controller_presentation_adapter" in symbols,
    }
    focused_results = [compile_result]
    focused_results.extend(_run(name, args, timeout) for name, args, timeout in FOCUSED_COMMANDS)
    blockers: list[str] = []
    if forbidden_imports:
        blockers.append("forbidden controller imports: " + ", ".join(forbidden_imports))
    if missing_symbols:
        blockers.append("missing controller orchestration symbols: " + ", ".join(missing_symbols))
    failed = [result["name"] for result in focused_results if result.get("status") != "PASS"]
    if failed:
        blockers.append("focused controller gates not PASS: " + ", ".join(failed))
    status = "LOCKED" if not blockers and all(static_checks.values()) else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_shared_controller_orchestration_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_controller_orchestration_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_controller_orchestration_lock.v1",
        "status": status,
        "static_checks": static_checks,
        "forbidden_imports": forbidden_imports,
        "missing_symbols": missing_symbols,
        "focused_results": focused_results,
        "blockers": blockers,
        "latest_artifacts": {
            "controller_input_snapshot_lock": _latest("design_brain_shared_controller_input_snapshot_lock"),
            "controller_trace_only_parity": _latest("design_guide_controller_trace_only_parity"),
            "controller_publication_authority_cutover": _latest("design_guide_controller_publication_authority_cutover"),
            "controller_compute_handoff_object": _latest("design_guide_controller_compute_handoff_object"),
            "controller_compute_selector_object": _latest("design_guide_controller_compute_selector_object"),
        },
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
