"""Prove the legacy no-active primary page assembler is ready for deletion or gone."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

FUNCTION_NAME = "_assemble_final_visible_no_active_primary_result"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_span(source: str, function_name: str) -> dict[str, Any] | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return {
                "start_line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "line_count": (getattr(node, "end_lineno", node.lineno) - node.lineno + 1),
            }
    return None


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    span = _function_span(source, FUNCTION_NAME)
    token_count = source.count(f"{FUNCTION_NAME}(")
    deleted = span is None and token_count == 0
    deletion_ready = span is not None and token_count == 1
    return {
        "function": FUNCTION_NAME,
        "span": span,
        "token_count": token_count,
        "deletion_ready": deletion_ready,
        "deleted": deleted,
        "decision": "DELETED" if deleted else "DELETION_READY" if deletion_ready else "NOT_READY",
        "cutover_boundary_present": (
            "_build_design_guide_controller_no_active_primary_result(" in source
            or "build_design_guide_controller_no_active_primary_result as "
            "_build_design_guide_controller_no_active_primary_result" in source
        ),
        "remaining_scope": "no-active primary branch is controller-backed; seven legacy resolver routes remain",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "dead_or_deleted": capture.get("deletion_ready") is True
        or capture.get("deleted") is True,
        "no_live_callers": int(capture.get("token_count") or 0) <= 1,
        "cutover_boundary_present": capture.get("cutover_boundary_present") is True,
        "decision_is_explicit": capture.get("decision") in {"DELETION_READY", "DELETED"},
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Primary Legacy Assembler Deletion Proof",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Function",
            "",
            f"- Name: `{capture.get('function')}`",
            f"- Token count: `{capture.get('token_count')}`",
            f"- Span: `{capture.get('span')}`",
            f"- Deletion ready: `{capture.get('deletion_ready')}`",
            f"- Deleted: `{capture.get('deleted')}`",
            "",
            str(capture.get("remaining_scope") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_no_active_primary_legacy_assembler_deletion_proof_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_no_active_primary_legacy_assembler_deletion_proof_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_primary_legacy_assembler_deletion_proof {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
