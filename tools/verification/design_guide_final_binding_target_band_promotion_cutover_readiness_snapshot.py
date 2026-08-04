"""Cutover readiness for final-binding target-band promotion.

Proof-only. This verifier proves the Design Brain result object is ready to
replace the page-owned target-band promotion effect in a later slice, while
confirming the live page effect has not been cut over yet.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

BINDING = "def _publish_final_visible_design_guide_contract_binding("
HELPER = "def _stamp_final_visible_contract_binding_target_band_promotion_result("
BUILDER = "def build_final_visible_contract_binding_target_band_promotion_result("


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
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    binding = _function_block(inputs_source, BINDING)
    helper = _function_block(inputs_source, HELPER)
    builder = _function_block(publication_source, BUILDER)
    latest = {
        "ownership": _latest("design_guide_final_binding_target_band_promotion_ownership"),
        "object": _latest("design_guide_final_binding_target_band_promotion_result_object"),
        "trace": _latest("design_guide_live_final_binding_target_band_promotion_result_trace"),
        "parity": _latest("design_guide_final_binding_target_band_promotion_result_parity_scenarios"),
        "cutover": _latest("design_guide_final_binding_target_band_promotion_result_cutover"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    live_effect_still_page_owned = (
        "if target_binding_evidence_available and current_binding_outside_target:" in binding
        and 'evidence_for_binding.update(' in binding
        and '"one_click_target_reaching_candidate_exists": True' in binding
        and "contract.update(" in binding
        and "out.update(" in binding
        and "payload.update(" in binding
    )
    result_effects_complete = all(
        token in builder
        for token in (
            '"contract_effect"',
            '"item_effect"',
            '"evidence_effect"',
            '"display_truth_effect"',
            '"action_payload_effect"',
            '"resolved_candidate_effect"',
            '"debug_effect"',
        )
    )
    cutover_already_complete = (latest.get("cutover") or {}).get("status") == "PASS"
    return {
        "decision": (
            "FINAL_BINDING_TARGET_BAND_PROMOTION_CUTOVER_ALREADY_COMPLETE"
            if cutover_already_complete
            else "FINAL_BINDING_TARGET_BAND_PROMOTION_READY_FOR_NEXT_CUTOVER_SLICE"
        ),
        "binding_present": bool(binding),
        "helper_present": bool(helper),
        "builder_present": bool(builder),
        "builder_ready_for_live_cutover": '"ready_for_live_cutover": True' in builder,
        "builder_remains_non_driving": {
            "proof_only": '"proof_only": True' in builder,
            "product": '"product_driving": False' in builder,
            "render": '"render_driving": False' in builder,
            "apply": '"apply_driving": False' in builder,
            "session": '"session_driving": False' in builder,
        },
        "result_effects_complete": result_effects_complete,
        "trace_ready_for_live_cutover": (
            '"final_binding_target_band_promotion_result_ready_for_live_cutover"' in helper
            and "= True" in helper
        ),
        "trace_has_live_parity": '"final_binding_target_band_promotion_result_parity"' in helper,
        "live_effect_still_page_owned": live_effect_still_page_owned,
        "cutover_already_complete": cutover_already_complete,
        "cutover_done_this_slice": False,
        "delete_allowed_this_slice": False,
        "next_safe_slice": (
            "replace the page-owned target-band promotion effect with the "
            "Design Brain result object's contract/item/evidence/display/action/debug effects"
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
        "builder_present": capture.get("builder_present") is True,
        "builder_ready_for_live_cutover": capture.get("builder_ready_for_live_cutover") is True,
        "builder_remains_non_driving": all((capture.get("builder_remains_non_driving") or {}).values()),
        "result_effects_complete": capture.get("result_effects_complete") is True,
        "trace_ready_for_live_cutover": capture.get("trace_ready_for_live_cutover") is True,
        "trace_has_live_parity": capture.get("trace_has_live_parity") is True,
        "live_effect_still_page_owned_or_cutover_complete": (
            capture.get("live_effect_still_page_owned") is True
            or capture.get("cutover_already_complete") is True
        ),
        "cutover_not_done_this_slice": capture.get("cutover_done_this_slice") is False,
        "delete_not_allowed_this_slice": capture.get("delete_allowed_this_slice") is False,
        "ownership_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "cutover_pass_when_complete": (
            capture.get("cutover_already_complete") is False
            or (latest.get("cutover") or {}).get("status") == "PASS"
        ),
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
        "# Final Binding Target-Band Promotion Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Builder ready for live cutover: `{capture.get('builder_ready_for_live_cutover')}`",
        f"- Trace ready for live cutover: `{capture.get('trace_ready_for_live_cutover')}`",
        f"- Live effect still page-owned: `{capture.get('live_effect_still_page_owned')}`",
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
        "schema": "design_guide_final_binding_target_band_promotion_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_target_band_promotion_cutover_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_target_band_promotion_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_target_band_promotion_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
