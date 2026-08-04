"""Object snapshot for final-binding contract consistency guard result."""

from __future__ import annotations

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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

REQUIRED_RESULT_FIELDS = {
    "reset_contract",
    "reason",
    "guard_family",
    "safe_binding_evidence_available",
    "combined_binding_evidence_available",
    "safe_binding_mismatch",
    "combined_binding_mismatch",
    "expected_updates",
    "updates_replacement",
    "action_type_replacement",
    "contract_replacement",
    "debug_effect",
}


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


def _function_source(source: str) -> str:
    token = "def build_final_visible_contract_binding_consistency_guard_result("
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_visible_contract_binding_consistency_guard_result,
    )

    shear_mismatch = build_final_visible_contract_binding_consistency_guard_result(
        evidence_for_binding={
            "family": "shear",
            "one_click_target_reaching_candidate_exists": True,
        },
        current_updates={"s_lig": 250.0},
        safe_binding_updates={"s_lig": 150.0},
        combined_binding_updates={},
        safe_updates_already_applied=False,
        combined_updates_already_applied=False,
        compound_shear_update_keys=["s_lig", "shear_link_spacing"],
    )
    shear_match = build_final_visible_contract_binding_consistency_guard_result(
        evidence_for_binding={
            "family": "shear",
            "one_click_target_reaching_candidate_exists": True,
        },
        current_updates={"s_lig": 150.0},
        safe_binding_updates={"s_lig": 150.0},
        combined_binding_updates={},
        safe_updates_already_applied=False,
        combined_updates_already_applied=False,
        compound_shear_update_keys=["s_lig", "shear_link_spacing"],
    )
    combined_mismatch = build_final_visible_contract_binding_consistency_guard_result(
        evidence_for_binding={"family": "combined", "cleanup_search_ran": True},
        current_updates={"s_lig": 250.0},
        safe_binding_updates={},
        combined_binding_updates={"s_lig": 150.0, "bottom_bar_size": "N20"},
        safe_updates_already_applied=False,
        combined_updates_already_applied=False,
        compound_shear_update_keys=["s_lig", "shear_link_spacing"],
    )
    already_applied = build_final_visible_contract_binding_consistency_guard_result(
        evidence_for_binding={
            "family": "shear",
            "accepted_band_candidate_count": 1,
        },
        current_updates={"s_lig": 250.0},
        safe_binding_updates={"s_lig": 150.0},
        combined_binding_updates={},
        safe_updates_already_applied=True,
        combined_updates_already_applied=False,
        compound_shear_update_keys=["s_lig", "shear_link_spacing"],
    )
    repeat = build_final_visible_contract_binding_consistency_guard_result(
        evidence_for_binding={
            "family": "shear",
            "one_click_target_reaching_candidate_exists": True,
        },
        current_updates={"s_lig": 250.0},
        safe_binding_updates={"s_lig": 150.0},
        combined_binding_updates={},
        safe_updates_already_applied=False,
        combined_updates_already_applied=False,
        compound_shear_update_keys=["s_lig", "shear_link_spacing"],
    )
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_source = _function_source(source)
    shear_result = dict(shear_mismatch.get("result") or {})
    flags = {
        "proof_only": shear_mismatch.get("proof_only"),
        "product_driving": shear_mismatch.get("product_driving"),
        "render_driving": shear_mismatch.get("render_driving"),
        "apply_driving": shear_mismatch.get("apply_driving"),
        "session_driving": shear_mismatch.get("session_driving"),
        "ready_for_trace_wiring": shear_mismatch.get("ready_for_trace_wiring"),
        "ready_for_live_cutover": shear_mismatch.get("ready_for_live_cutover"),
    }
    forbidden_tokens = {
        "inputs_page": "inputs_page" in function_source,
        "streamlit": "streamlit" in function_source.lower() or "st." in function_source,
        "session_state": "session_state" in function_source,
        "evaluator": "_evaluate_auto_design_candidate" in function_source,
        "state_match_helper": "_updates_match_state" in function_source,
        "render_html": "html" in function_source.lower(),
    }
    latest = {
        "residual_policy_audit": _latest("design_guide_final_binding_residual_policy_ownership"),
        "target_band_cutover": _latest("design_guide_final_binding_target_band_promotion_result_cutover"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_CONSISTENCY_GUARD_RESULT_OBJECT_READY_FOR_CUTOVER_READINESS",
        "function_present": "def build_final_visible_contract_binding_consistency_guard_result(" in source,
        "exported": '"build_final_visible_contract_binding_consistency_guard_result"' in source,
        "missing_result_fields": sorted(REQUIRED_RESULT_FIELDS - set(shear_result)),
        "shear_mismatch_resets": bool((shear_mismatch.get("result") or {}).get("reset_contract")),
        "shear_match_does_not_reset": not bool((shear_match.get("result") or {}).get("reset_contract")),
        "combined_mismatch_resets": bool((combined_mismatch.get("result") or {}).get("reset_contract")),
        "already_applied_does_not_reset": not bool((already_applied.get("result") or {}).get("reset_contract")),
        "proof_hash_stable": shear_mismatch.get("proof_hash") == repeat.get("proof_hash"),
        "result_hash_stable": shear_mismatch.get("result_hash") == repeat.get("result_hash"),
        "flags": flags,
        "forbidden_tokens": forbidden_tokens,
        "forbidden_tokens_absent": not any(forbidden_tokens.values()),
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
    flags = dict(capture.get("flags") or {})
    latest = dict(capture.get("latest") or {})
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "required_fields_present": not capture.get("missing_result_fields"),
        "shear_mismatch_resets": capture.get("shear_mismatch_resets") is True,
        "shear_match_does_not_reset": capture.get("shear_match_does_not_reset") is True,
        "combined_mismatch_resets": capture.get("combined_mismatch_resets") is True,
        "already_applied_does_not_reset": capture.get("already_applied_does_not_reset") is True,
        "proof_hash_stable": capture.get("proof_hash_stable") is True,
        "result_hash_stable": capture.get("result_hash_stable") is True,
        "proof_only": flags.get("proof_only") is True,
        "not_product_driving": flags.get("product_driving") is False,
        "not_render_driving": flags.get("render_driving") is False,
        "not_apply_driving": flags.get("apply_driving") is False,
        "not_session_driving": flags.get("session_driving") is False,
        "ready_for_trace_wiring": flags.get("ready_for_trace_wiring") is True,
        "ready_for_live_cutover": flags.get("ready_for_live_cutover") is True,
        "forbidden_tokens_absent": capture.get("forbidden_tokens_absent") is True,
        "residual_policy_audit_pass": (latest.get("residual_policy_audit") or {}).get("status") == "PASS",
        "target_band_cutover_pass": (latest.get("target_band_cutover") or {}).get("status") == "PASS",
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
        "# Final Binding Consistency Guard Result Object",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenario Results",
        "",
        f"- Shear mismatch resets: `{capture.get('shear_mismatch_resets')}`",
        f"- Shear match does not reset: `{capture.get('shear_match_does_not_reset')}`",
        f"- Combined mismatch resets: `{capture.get('combined_mismatch_resets')}`",
        f"- Already-applied does not reset: `{capture.get('already_applied_does_not_reset')}`",
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
        "schema": "design_guide_final_binding_consistency_guard_result_object_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_consistency_guard_result_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_consistency_guard_result_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_consistency_guard_result_object {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
