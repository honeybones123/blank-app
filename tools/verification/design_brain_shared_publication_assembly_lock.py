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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
PUBLICATION = ROOT / "design_brain" / "publication.py"


FOCUSED_COMMANDS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("final_publication_object", ("tools/verification/design_guide_final_publication_object_snapshot.py",), 90),
    ("final_publication_boundary", ("tools/verification/design_guide_final_publication_boundary_snapshot.py",), 90),
    (
        "final_publication_cta_source_precedence",
        ("tools/verification/design_brain_shared_final_publication_cta_source_precedence_lock.py",),
        180,
    ),
    ("independence_lock", ("tools/verification/design_guide_independence_lock_verifier.py",), 180),
    (
        "publication_recovery_enforcement_contract",
        ("tools/verification/design_brain_shared_publication_recovery_enforcement_contract_lock.py",),
        300,
    ),
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


def _function_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sorted(node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))


def _latest(prefix: str) -> str | None:
    paths = sorted((ROOT / "artifacts" / "verification").glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    return str(paths[-1]) if paths else None


def _latest_status(prefix: str) -> str:
    paths = sorted((ROOT / "artifacts" / "verification").glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return "MISSING"
    try:
        payload = json.loads(paths[-1].read_text(encoding="utf-8"))
    except Exception:
        return "UNREADABLE"
    value = str(payload.get("status") or payload.get("lock_status") or payload.get("result") or "").upper()
    if "LOCKED" in value or "PASS" in value or "COMPLETE" in value:
        return "PASS"
    if "DEFERRED" in value or "PARTIAL" in value:
        return "PARTIAL"
    if "FAIL" in value or "BLOCKED" in value:
        return "FAIL"
    return value or "UNKNOWN"


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Shared Publication Assembly Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Focused Gates",
        "",
        "| Gate | Status | Command |",
        "| --- | --- | --- |",
    ]
    for result in snapshot.get("focused_results") or []:
        lines.append(f"| {result['name']} | `{result['status']}` | `{result['command']}` |")
    lines.extend(["", "## Broader Publication Surface", ""])
    lines.append(f"- recovery/enforcement helpers found: `{len(snapshot['broader_publication_helpers'])}`")
    for name in snapshot.get("broader_publication_helpers") or []:
        lines.append(f"  - `{name}`")
    lines.extend(["", "## Blockers", ""])
    if snapshot.get("blockers"):
        lines.extend(f"- {item}" for item in snapshot["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Latest Artifacts", ""])
    for key, value in (snapshot.get("latest_artifacts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.append(f"\nJSON: `{snapshot['artifact']}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_result = _run(
        "py_compile_publication_assembly_lock",
        (
            "-m",
            "py_compile",
            "design_brain/final_publication.py",
            "design_brain/publication.py",
            "tools/verification/design_brain_shared_publication_assembly_lock.py",
        ),
        90,
    )
    focused_results = [compile_result]
    focused_results.extend(_run(name, args, timeout) for name, args, timeout in FOCUSED_COMMANDS)
    publication_functions = _function_names(PUBLICATION)
    broader_helpers = [
        name
        for name in publication_functions
        if (
            "enforce_" in name
            or "recover" in name
            or "route_" in name
            or "publication_contract" in name
            or "publication_item" in name
        )
    ]
    blockers: list[str] = []
    failed = [result["name"] for result in focused_results if result.get("status") != "PASS"]
    if failed:
        blockers.append("focused publication gates not PASS: " + ", ".join(failed))
    recovery_lock_status = _latest_status("design_brain_shared_publication_recovery_enforcement_contract_lock")
    if broader_helpers and recovery_lock_status != "PASS":
        blockers.append(
            "broader design_brain/publication.py recovery/enforcement helpers need a dedicated shared contract lock before full publication assembly can be marked LOCKED"
        )
    status = "LOCKED" if not blockers else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_shared_publication_assembly_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_publication_assembly_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_publication_assembly_lock.v1",
        "status": status,
        "focused_results": focused_results,
        "broader_publication_helpers": broader_helpers,
        "blockers": blockers,
        "latest_artifacts": {
            "final_publication_object": _latest("design_guide_final_publication_object"),
            "final_publication_boundary": _latest("design_guide_final_publication_boundary"),
            "final_publication_cta_source_precedence": _latest(
                "design_brain_shared_final_publication_cta_source_precedence_lock"
            ),
            "publication_recovery_enforcement_contract": _latest(
                "design_brain_shared_publication_recovery_enforcement_contract_lock"
            ),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "publication_recovery_enforcement_contract_status": recovery_lock_status,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
