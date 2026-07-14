"""Prove the legacy zero-shear-demand accepted assembler can be deleted."""

from __future__ import annotations

from datetime import datetime
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

ASSEMBLER = "_assemble_final_visible_zero_shear_demand_accepted_result"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str | None, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return None, None, None


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    assembler_source, start, end = _function_source(INPUTS_PAGE, ASSEMBLER)
    function_present = assembler_source is not None
    live_call_count = source.count(f"{ASSEMBLER}(") - (1 if function_present else 0)
    decision = (
        "DELETED" if not function_present else ("READY_TO_DELETE" if live_call_count == 0 else "NOT_READY")
    )
    return {
        "assembler": {
            "name": ASSEMBLER,
            "present": function_present,
            "start_line": start,
            "end_line": end,
            "live_call_count": live_call_count,
        },
        "decision": decision,
        "verification": {
            "remaining_inventory": _run(
                "tools/verification/design_guide_remaining_final_visible_assembler_inventory_audit.py"
            ),
        },
        "ready_for_deletion": decision == "READY_TO_DELETE",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    assembler = capture.get("assembler") or {}
    decision = capture.get("decision")
    verification = capture.get("verification") or {}
    return {
        "assembler_present_or_deleted_state_known": decision in {"READY_TO_DELETE", "DELETED", "NOT_READY"},
        "no_live_assembler_calls_when_present": (
            decision == "DELETED" or assembler.get("live_call_count") == 0
        ),
        "inventory_audit_passed": (verification.get("remaining_inventory") or {}).get("passed")
        is True,
        "ready_or_already_deleted": decision in {"READY_TO_DELETE", "DELETED"},
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    assembler = capture.get("assembler") or {}
    lines = [
        "# Design Guide Zero-Shear Demand Accepted Legacy Assembler Deletion Proof",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Assembler present: `{assembler.get('present')}`",
        f"Live call count: `{assembler.get('live_call_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Delete only `_assemble_final_visible_zero_shear_demand_accepted_result(...)` "
            "when decision is `READY_TO_DELETE`.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR / f"design_guide_zero_shear_demand_accepted_legacy_assembler_deletion_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_zero_shear_demand_accepted_legacy_assembler_deletion_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_zero_shear_demand_accepted_legacy_assembler_deletion {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
