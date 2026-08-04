"""Deadness audit for manual target-band promotion fallback rows.

Audit-only. The live target-band promotion effect has been cut over to the
Design Brain result maps, but old literal fallback rows remain as safety if the
result payload is unavailable. This verifier decides whether those fallback
rows are deletion-ready.
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
HELPER = "def _stamp_final_visible_contract_binding_target_band_promotion_result("


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
    helper = _function_block(source, HELPER)
    latest = {
        "cutover": _latest("design_guide_final_binding_target_band_promotion_result_cutover"),
        "trace": _latest("design_guide_live_final_binding_target_band_promotion_result_trace"),
        "parity": _latest("design_guide_final_binding_target_band_promotion_result_parity_scenarios"),
        "object": _latest("design_guide_final_binding_target_band_promotion_result_object"),
        "readiness": _latest("design_guide_final_binding_target_band_promotion_cutover_readiness"),
        "typed_fallback": _latest("design_guide_final_binding_typed_fallback_payload"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    fallback_rows = {
        "evidence": "if final_binding_evidence_effect:" in binding
        and "else:\n            evidence_for_binding.update(" in binding,
        "contract": "if final_binding_contract_effect:" in binding
        and "else:\n            contract.update(" in binding,
        "item": "if final_binding_item_effect:" in binding
        and "else:\n            out.update(" in binding,
        "display": "if final_binding_display_truth_effect:" in binding
        and "elif target_binding_util is not None:" in binding,
        "action_payload": "if final_binding_action_payload_effect:" in binding
        and "else:\n            payload.update(" in binding,
        "resolved_candidate": "if final_binding_resolved_candidate_effect:" in binding
        and "else:\n            resolved.update(" in binding,
        "debug": "if final_binding_debug_effect:" in binding
        and "else:\n                debug_sink.update(" in binding,
    }
    helper_has_exception_path = (
        "except Exception as exc:" in helper
        and "return {}" in helper
        and '"final_binding_target_band_promotion_result_error"' in helper
    )
    helper_has_typed_fallback = (
        "except Exception as exc:" in helper
        and "_build_final_visible_contract_binding_typed_fallback_payload(" in helper
        and '"final_binding_target_band_promotion_result_error"' in helper
        and '"contract_effect": fallback_contract_effect' in helper
        and '"item_effect": fallback_item_effect' in helper
        and '"evidence_effect": fallback_evidence_effect' in helper
        and '"display_truth_effect": fallback_display_truth_effect' in helper
        and '"action_payload_effect": fallback_action_payload_effect' in helper
        and '"resolved_candidate_effect": fallback_resolved_candidate_effect' in helper
        and '"debug_effect": fallback_debug_effect' in helper
    )
    result_effects_are_primary = (
        "final_binding_target_band_promotion_result.get(\"applies\")" in binding
        and "contract.update(final_binding_contract_effect)" in binding
        and "out.update(final_binding_item_effect)" in binding
        and "evidence_for_binding.update(final_binding_evidence_effect)" in binding
        and "payload.update(final_binding_action_payload_effect)" in binding
        and "resolved.update(final_binding_resolved_candidate_effect)" in binding
    )
    typed_fallback_pass = (latest.get("typed_fallback") or {}).get("status") == "PASS"
    manual_fallback_rows_all_present = all(fallback_rows.values())
    manual_fallback_rows_deleted = not any(fallback_rows.values())
    deletion_ready = bool(
        result_effects_are_primary
        and (manual_fallback_rows_all_present or manual_fallback_rows_deleted)
        and not helper_has_exception_path
        and helper_has_typed_fallback
        and typed_fallback_pass
    )
    classification = (
        "A. deleted after proof"
        if manual_fallback_rows_deleted and deletion_ready
        else "D. deletion candidate"
        if deletion_ready
        else "B. fallback/safety keep until helper exception path is retired or separately guarded"
    )
    return {
        "decision": (
            "FINAL_BINDING_TARGET_BAND_PROMOTION_MANUAL_FALLBACK_DELETION_READY"
            if deletion_ready
            else "FINAL_BINDING_TARGET_BAND_PROMOTION_MANUAL_FALLBACK_NOT_DELETION_READY"
        ),
        "binding_present": bool(binding),
        "helper_present": bool(helper),
        "result_effects_are_primary": result_effects_are_primary,
        "manual_fallback_rows_present": fallback_rows,
        "manual_fallback_rows_deleted": manual_fallback_rows_deleted,
        "helper_has_exception_path_returning_empty_payload": helper_has_exception_path,
        "helper_has_typed_fallback_payload": helper_has_typed_fallback,
        "classification": classification,
        "deletion_ready": deletion_ready,
        "delete_allowed_this_slice": False,
        "next_safe_slice": (
            "target-band promotion manual fallback rows are already deleted; move to the next proven fallback group"
            if manual_fallback_rows_deleted and deletion_ready
            else "delete only the target-band promotion manual fallback rows in a separate focused deletion slice"
            if deletion_ready
            else (
                "either retire the helper empty-payload exception path with a safe typed fallback object, "
                "or move to another final-binding policy extraction target"
            )
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
        "helper_present": capture.get("helper_present") is True,
        "result_effects_are_primary": capture.get("result_effects_are_primary") is True,
        "manual_fallback_rows_present_or_deleted": (
            all((capture.get("manual_fallback_rows_present") or {}).values())
            or capture.get("manual_fallback_rows_deleted") is True
        ),
        "helper_exception_path_retired": (
            capture.get("helper_has_exception_path_returning_empty_payload") is False
        ),
        "helper_typed_fallback_present": capture.get("helper_has_typed_fallback_payload") is True,
        "deletion_ready": capture.get("deletion_ready") is True,
        "delete_not_allowed_this_slice": capture.get("delete_allowed_this_slice") is False,
        "cutover_pass": (latest.get("cutover") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "readiness_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "typed_fallback_pass": (latest.get("typed_fallback") or {}).get("status") == "PASS",
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
        "# Final Binding Target-Band Promotion Manual Fallback Deadness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Result effects are primary: `{capture.get('result_effects_are_primary')}`",
        f"- Helper exception path returns empty payload: `{capture.get('helper_has_exception_path_returning_empty_payload')}`",
        f"- Classification: `{capture.get('classification')}`",
        f"- Deletion ready: `{capture.get('deletion_ready')}`",
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
        "schema": "design_guide_final_binding_target_band_promotion_manual_fallback_deadness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_target_band_promotion_manual_fallback_deadness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_target_band_promotion_manual_fallback_deadness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_target_band_promotion_manual_fallback_deadness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"classification={capture.get('classification')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
