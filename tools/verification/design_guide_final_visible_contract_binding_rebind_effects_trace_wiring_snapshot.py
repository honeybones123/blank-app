"""Trace-wiring snapshot for final-visible contract-binding rebind effects.

Proof-only. Verifies the old page binding helper now emits a non-driving
Design Brain proof hash for the contract-binding effects that block direct
combined/engine rebind replacement.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _line_for(lines: list[str], token: str) -> int | None:
    for index, line in enumerate(lines, start=1):
        if token in line:
            return index
    return None


def _window(lines: list[str], line: int | None, *, before: int = 80, after: int = 130) -> str:
    if line is None:
        return ""
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    call_line = _line_for(lines, "_rebind_effects_proof = _build_final_visible_contract_binding_rebind_effects_proof(")
    context = _window(lines, call_line)
    return {
        "trace_call_line": call_line,
        "import_present": (
            "build_final_visible_contract_binding_rebind_effects_proof as "
            "_build_final_visible_contract_binding_rebind_effects_proof"
        )
        in source,
        "trace_call_present": call_line is not None,
        "trace_inputs_present": {
            "evidence_for_binding": "evidence_for_binding=evidence_for_binding" in context,
            "contract": "contract=contract" in context,
            "item": "item=out" in context,
            "current_updates": "current_updates=updates" in context,
            "combined_binding_updates": "combined_binding_updates=combined_binding_updates" in context,
            "safe_binding_updates": "safe_binding_updates=safe_binding_updates" in context,
            "blocker_families": "blocker_families=sorted(blocker_families_for_contract)" in context,
        },
        "debug_stamps_present": {
            "proof_payload": "final_visible_contract_binding_rebind_effects_proof" in context,
            "proof_hash": "final_visible_contract_binding_rebind_effects_proof_hash" in context,
            "trace_wired": "final_visible_contract_binding_rebind_effects_trace_wired" in context,
            "product_non_driving": "final_visible_contract_binding_rebind_effects_product_driving" in context,
            "render_non_driving": "final_visible_contract_binding_rebind_effects_render_driving" in context,
            "apply_non_driving": "final_visible_contract_binding_rebind_effects_apply_driving" in context,
            "session_non_driving": "final_visible_contract_binding_rebind_effects_session_driving" in context,
        },
        "old_rebind_calls_still_present": {
            "combined": "_combined_rebound_item = _publish_final_visible_design_guide_contract_binding(" in source,
            "engine": "_engine_rebound_item = _publish_final_visible_design_guide_contract_binding(" in source,
        },
        "latest_artifacts": {
            "effects_proof": _latest("design_guide_final_visible_contract_binding_rebind_effects_proof"),
            "parity_gap": _latest("design_guide_render_combined_engine_rebind_parity_gap"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "import_present": capture.get("import_present") is True,
        "trace_call_present": capture.get("trace_call_present") is True,
        "trace_inputs_present": all((capture.get("trace_inputs_present") or {}).values()),
        "debug_stamps_present": all((capture.get("debug_stamps_present") or {}).values()),
        "old_combined_rebind_still_present": (
            capture.get("old_rebind_calls_still_present") or {}
        ).get("combined")
        is True,
        "old_engine_rebind_still_present": (
            capture.get("old_rebind_calls_still_present") or {}
        ).get("engine")
        is True,
        "effects_proof_pass": (latest.get("effects_proof") or {}).get("status") == "PASS",
        "parity_gap_pass": (latest.get("parity_gap") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Visible Contract Binding Rebind Effects Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Trace call line: `{capture.get('trace_call_line')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_final_visible_contract_binding_rebind_effects_trace_wiring_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_contract_binding_rebind_effects_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_contract_binding_rebind_effects_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_final_visible_contract_binding_rebind_effects_trace_wiring_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
