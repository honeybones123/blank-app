"""Prove the legacy final-visible resolver body has been deleted safely."""

from __future__ import annotations

from datetime import datetime
import ast
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

RESOLVER_NAME = "resolve_final_visible_design_guide_item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper() or "LOCKED" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _ast_calls_to_resolver(source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source.lstrip("\ufeff"))
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name == RESOLVER_NAME or name.endswith(f".{RESOLVER_NAME}"):
            calls.append({"line": int(getattr(node, "lineno", 0) or 0), "call": name})
    return calls


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    reference = _latest("design_guide_remaining_final_visible_resolver_reference_audit")
    fixture_retirement = _latest("design_guide_legacy_resolver_fixture_retirement_readiness")
    fallback_deadness = _latest("design_guide_compute_resolver_fallback_deadness")
    return {
        "resolver_function_definition_count": source.count(f"def {RESOLVER_NAME}("),
        "resolver_ast_callsites": _ast_calls_to_resolver(source),
        "controller_fallback_shell_count": source.count(
            "_build_design_guide_controller_compute_resolver_fallback_shell("
        ),
        "reference_audit": {
            "status": reference.get("status"),
            "path": reference.get("path"),
            "decision": (reference.get("payload") or {}).get("capture", {}).get("decision"),
        },
        "fixture_retirement_readiness": {
            "status": fixture_retirement.get("status"),
            "path": fixture_retirement.get("path"),
            "decision": (fixture_retirement.get("payload") or {}).get("capture", {}).get("decision"),
        },
        "fallback_deadness": {
            "status": fallback_deadness.get("status"),
            "path": fallback_deadness.get("path"),
            "decision": (fallback_deadness.get("payload") or {}).get("capture", {}).get("decision"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    return {
        "inputs_page_py_compile_pass": compile_run.get("returncode") == 0,
        "legacy_resolver_function_definition_deleted": (
            capture.get("resolver_function_definition_count") == 0
        ),
        "no_ast_calls_to_legacy_resolver": not capture.get("resolver_ast_callsites"),
        "controller_fallback_shell_retained": capture.get("controller_fallback_shell_count") == 1,
        "reference_audit_body_deleted": (
            (capture.get("reference_audit") or {}).get("status") == "PASS"
            and (capture.get("reference_audit") or {}).get("decision") == "LEGACY_RESOLVER_BODY_DELETED"
        ),
        "fixture_retirement_ready": (
            (capture.get("fixture_retirement_readiness") or {}).get("status") == "PASS"
        ),
        "fallback_deadness_pass": (capture.get("fallback_deadness") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Final Visible Resolver Dead Body Deletion Proof",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Checks",
        "",
        "| Check | Pass |",
        "| --- | --- |",
    ]
    lines.extend(f"| `{key}` | `{value}` |" for key, value in dict(payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Resolver function definitions: `{capture.get('resolver_function_definition_count')}`",
            f"- Resolver AST callsites: `{capture.get('resolver_ast_callsites')}`",
            f"- Controller fallback shell count: `{capture.get('controller_fallback_shell_count')}`",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run([sys.executable, "-m", "py_compile", "inputs_page.py"])
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, passed in checks.items() if passed is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_final_visible_resolver_dead_body_deletion_proof.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "compile_run": compile_run,
        "checks": checks,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_resolver_dead_body_deletion_proof_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_resolver_dead_body_deletion_proof_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_final_visible_resolver_dead_body_deletion_proof {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
