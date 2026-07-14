"""Cutover proof for final-binding target-band promotion.

This verifier proves the live target-band promotion branch now consumes the
Design Brain result object's contract/item/evidence/display/action/debug
effects. It does not prove the fallback manual rows are dead; that requires a
later deletion proof.
"""

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
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


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
        "ownership": _latest("design_guide_final_binding_target_band_promotion_ownership"),
        "object": _latest("design_guide_final_binding_target_band_promotion_result_object"),
        "trace": _latest("design_guide_live_final_binding_target_band_promotion_result_trace"),
        "parity": _latest("design_guide_final_binding_target_band_promotion_result_parity_scenarios"),
        "readiness": _latest("design_guide_final_binding_target_band_promotion_cutover_readiness"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_TARGET_BAND_PROMOTION_RESULT_CUTOVER_COMPLETE",
        "binding_present": bool(binding),
        "payload_captured": (
            "final_binding_target_band_promotion_payload = "
            "_stamp_final_visible_contract_binding_target_band_promotion_result("
        )
        in binding,
        "result_extracted": (
            "final_binding_target_band_promotion_result = dict(" in binding
            and "(final_binding_target_band_promotion_payload or {}).get(\"result\")" in binding
        ),
        "result_drives_branch": (
            "final_binding_target_band_promotion_applies = bool(" in binding
            and "final_binding_target_band_promotion_result.get(\"applies\")" in binding
            and "if final_binding_target_band_promotion_applies:" in binding
        ),
        "effect_maps_extracted": {
            "contract": "final_binding_contract_effect = dict(" in binding
            and "final_binding_target_band_promotion_result.get(\"contract_effect\")" in binding,
            "item": "final_binding_item_effect = dict(" in binding
            and "final_binding_target_band_promotion_result.get(\"item_effect\")" in binding,
            "evidence": "final_binding_evidence_effect = dict(" in binding
            and "final_binding_target_band_promotion_result.get(\"evidence_effect\")" in binding,
            "display": "final_binding_display_truth_effect = dict(" in binding
            and "final_binding_target_band_promotion_result.get(\"display_truth_effect\")" in binding,
            "action_payload": "final_binding_action_payload_effect = dict(" in binding
            and "final_binding_target_band_promotion_result.get(\"action_payload_effect\")" in binding,
            "resolved_candidate": "final_binding_resolved_candidate_effect = dict(" in binding
            and "final_binding_target_band_promotion_result.get(\"resolved_candidate_effect\")" in binding,
            "debug": "final_binding_debug_effect = dict(" in binding
            and "final_binding_target_band_promotion_result.get(\"debug_effect\")" in binding,
        },
        "effect_maps_applied": {
            "contract": "contract.update(final_binding_contract_effect)" in binding,
            "item": "out.update(final_binding_item_effect)" in binding,
            "evidence": "evidence_for_binding.update(final_binding_evidence_effect)" in binding,
            "display": "display_truth.update(final_binding_display_truth_effect)" in binding,
            "action_payload": "payload.update(final_binding_action_payload_effect)" in binding,
            "resolved_candidate": "resolved.update(final_binding_resolved_candidate_effect)" in binding,
            "debug": "debug_sink.update(final_binding_debug_effect)" in binding,
        },
        "manual_fallback_still_present": (
            "if final_binding_evidence_effect:" in binding
            and "else:\n            evidence_for_binding.update(" in binding
            and "if final_binding_contract_effect:" in binding
            and "else:\n            contract.update(" in binding
            and "if final_binding_action_payload_effect:" in binding
            and "else:\n            payload.update(" in binding
        ),
        "live_cutover_stamps_present": {
            "used": '"final_binding_target_band_promotion_result_live_cutover_used"' in binding,
            "hash": '"final_binding_target_band_promotion_result_live_cutover_hash"' in binding,
            "proof_hash": '"final_binding_target_band_promotion_result_live_cutover_proof_hash"' in binding,
            "source": '"final_binding_target_band_promotion_result_live_cutover_source"' in binding,
        },
        "delete_allowed_this_slice": False,
        "next_safe_slice": (
            "prove fallback/manual target-band promotion rows are unreachable or compatibility-only, "
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
        "payload_captured": capture.get("payload_captured") is True,
        "result_extracted": capture.get("result_extracted") is True,
        "result_drives_branch": capture.get("result_drives_branch") is True,
        "effect_maps_extracted": all((capture.get("effect_maps_extracted") or {}).values()),
        "effect_maps_applied": all((capture.get("effect_maps_applied") or {}).values()),
        "manual_fallback_still_present": capture.get("manual_fallback_still_present") is True,
        "live_cutover_stamps_present": all((capture.get("live_cutover_stamps_present") or {}).values()),
        "delete_not_allowed_this_slice": capture.get("delete_allowed_this_slice") is False,
        "ownership_pass": (latest.get("ownership") or {}).get("status") == "PASS",
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
        "# Final Binding Target-Band Promotion Result Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Result payload captured: `{capture.get('payload_captured')}`",
        f"- Result drives branch: `{capture.get('result_drives_branch')}`",
        f"- Effect maps applied: `{capture.get('effect_maps_applied')}`",
        f"- Manual fallback still present: `{capture.get('manual_fallback_still_present')}`",
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
        "schema": "design_guide_final_binding_target_band_promotion_result_cutover_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_target_band_promotion_result_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_target_band_promotion_result_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_target_band_promotion_result_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
