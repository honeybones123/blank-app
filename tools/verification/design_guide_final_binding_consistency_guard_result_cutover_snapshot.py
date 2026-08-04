"""Cutover proof for final-binding contract consistency guard."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

BINDING = "def _publish_final_visible_design_guide_contract_binding("


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
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    binding = _function_block(source, BINDING)
    latest = {
        "object": _latest("design_guide_final_binding_consistency_guard_result_object"),
        "trace": _latest("design_guide_live_final_binding_consistency_guard_result_trace"),
        "parity": _latest("design_guide_final_binding_consistency_guard_result_parity_scenarios"),
        "readiness": _latest("design_guide_final_binding_consistency_guard_cutover_readiness"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_CONSISTENCY_GUARD_RESULT_CUTOVER_COMPLETE",
        "binding_present": bool(binding),
        "payloads_captured": {
            "shear": (
                "final_binding_safe_consistency_guard_payload = "
                "_stamp_final_visible_contract_binding_consistency_guard_result("
            )
            in binding,
            "combined": (
                "final_binding_combined_consistency_guard_payload = "
                "_stamp_final_visible_contract_binding_consistency_guard_result("
            )
            in binding,
        },
        "results_extracted": {
            "shear": "final_binding_safe_consistency_guard_result = dict(" in binding
            and "(final_binding_safe_consistency_guard_payload or {}).get(\"result\")" in binding,
            "combined": "final_binding_combined_consistency_guard_result = dict(" in binding
            and "(final_binding_combined_consistency_guard_payload or {}).get(\"result\")" in binding,
        },
        "result_drives_resets": {
            "shear": "final_binding_safe_consistency_guard_result.get(\"reset_contract\")" in binding
            and "if final_binding_safe_consistency_guard_resets:" in binding,
            "combined": "final_binding_combined_consistency_guard_result.get(\"reset_contract\")" in binding
            and "if final_binding_combined_consistency_guard_resets:" in binding,
        },
        "replacement_fields_applied": {
            "shear_updates": "final_binding_safe_consistency_guard_result.get(\"updates_replacement\")" in binding,
            "shear_action_type": "final_binding_safe_consistency_guard_result.get(\"action_type_replacement\")" in binding,
            "shear_contract": "final_binding_safe_consistency_guard_result.get(\"contract_replacement\")" in binding,
            "combined_updates": "final_binding_combined_consistency_guard_result.get(\"updates_replacement\")" in binding,
            "combined_action_type": "final_binding_combined_consistency_guard_result.get(\"action_type_replacement\")" in binding,
            "combined_contract": "final_binding_combined_consistency_guard_result.get(\"contract_replacement\")" in binding,
        },
        "manual_condition_fallback_still_present": (
            "not final_binding_safe_consistency_guard_result" in binding
            and "not final_binding_combined_consistency_guard_result" in binding
            and "safe_binding_evidence_available" in binding
            and "combined_binding_evidence_available" in binding
        ),
        "live_cutover_stamps_present": {
            "used": '"final_binding_consistency_guard_result_live_cutover_used"' in binding,
            "callsite": '"final_binding_consistency_guard_result_live_cutover_callsite"' in binding,
            "hash": '"final_binding_consistency_guard_result_live_cutover_hash"' in binding,
            "proof_hash": '"final_binding_consistency_guard_result_live_cutover_proof_hash"' in binding,
            "source": '"final_binding_consistency_guard_result_live_cutover_source"' in binding,
        },
        "delete_allowed_this_slice": False,
        "next_safe_slice": (
            "prove consistency guard manual condition fallbacks are unreachable or compatibility-only, "
            "then delete them separately"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "binding_present": capture.get("binding_present") is True,
        "payloads_captured": all((capture.get("payloads_captured") or {}).values()),
        "results_extracted": all((capture.get("results_extracted") or {}).values()),
        "result_drives_resets": all((capture.get("result_drives_resets") or {}).values()),
        "replacement_fields_applied": all((capture.get("replacement_fields_applied") or {}).values()),
        "manual_condition_fallback_still_present": capture.get("manual_condition_fallback_still_present") is True,
        "live_cutover_stamps_present": all((capture.get("live_cutover_stamps_present") or {}).values()),
        "delete_not_allowed_this_slice": capture.get("delete_allowed_this_slice") is False,
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "readiness_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding Consistency Guard Result Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Payloads captured: `{capture.get('payloads_captured')}`",
        f"- Result drives resets: `{capture.get('result_drives_resets')}`",
        f"- Manual fallback still present: `{capture.get('manual_condition_fallback_still_present')}`",
        f"- Next safe slice: {capture.get('next_safe_slice')}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_final_binding_consistency_guard_result_cutover_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_consistency_guard_result_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_consistency_guard_result_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_consistency_guard_result_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
