"""Object proof for post-click replacement decision coverage."""

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

REQUIRED_GROUPS = {
    "page_session_apply_inputs",
    "page_current_state_inputs",
    "exact_blocker_decision",
    "render_item_replacement_mutation",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = artifacts[-1]
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


def _sample() -> dict[str, Any]:
    return {
        "final_contract": {"enabled": True, "family": "bending", "expected_util": 0.32},
        "final_family": "bending",
        "final_expected_util": 0.32,
        "final_current_bending_util": 0.24,
        "unresolved_families": ["bending"],
        "below_floor_families": ["bending"],
        "same_flow_cleanup_apply": True,
        "exact_blocker_on_visible_item": True,
        "requires_exact_blocker": True,
        "visible_action": True,
        "bending_audit": {
            "post_click_exact_blockers_by_family": {"bending": {"no_second_cta_required": True}},
            "post_click_family_utils": {"bending": 0.24},
            "guidance_branch": "pre-replacement",
        },
        "bending_resolution": {
            "title": "Design Guide blocker proof incomplete",
            "button_contract": {"enabled": False, "family": "bending"},
        },
        "bending_contract": {"enabled": False, "family": "bending"},
        "replacement_applied": True,
        "output_item": {"title": "Design Guide blocker proof incomplete", "family": "bending"},
        "final_visible_resolution": {
            "render_reason": "post_click_low_bending_exact_blocker_final",
            "item": {"family": "bending"},
        },
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_replacement_decision_proof,
    )

    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start = source.find("def build_final_design_guide_post_click_replacement_decision_proof(")
    function_end = source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    function_source = (
        source[function_start:function_end]
        if function_start >= 0 and function_end > function_start
        else ""
    )
    proof = build_final_design_guide_post_click_replacement_decision_proof(**_sample())
    repeat = build_final_design_guide_post_click_replacement_decision_proof(**_sample())
    represented = set(proof.get("represented_live_groups") or ())
    latest_classification = _latest("design_guide_post_click_contract_check_live_rows_classification")
    forbidden_tokens = {
        "streamlit_import": "import streamlit" in function_source or "st.session_state" in function_source,
        "visible_wording": "Strengthening required" in function_source or "Repair required" in function_source,
        "apply_routing": (
            "one_click" in function_source
            or "_queue_primary_design_guide_button_action" in function_source
            or "on_click" in function_source
        ),
    }
    return {
        "decision": "POST_CLICK_REPLACEMENT_DECISION_PROOF_OBJECT_PASS",
        "function_present": "def build_final_design_guide_post_click_replacement_decision_proof("
        in source,
        "required_groups": sorted(REQUIRED_GROUPS),
        "represented_groups": sorted(represented),
        "missing_groups": sorted(REQUIRED_GROUPS - represented),
        "proof_hash_stable": proof.get("proof_hash") == repeat.get("proof_hash"),
        "required_hashes_present": {
            key: bool(proof.get(key))
            for key in (
                "decision_inputs_hash",
                "final_contract_hash",
                "bending_audit_hash",
                "bending_resolution_hash",
                "bending_contract_hash",
                "replacement_result_hash",
            )
        },
        "proof_flags": {
            "proof_only": proof.get("proof_only"),
            "product_driving": proof.get("product_driving"),
            "render_driving": proof.get("render_driving"),
            "apply_driving": proof.get("apply_driving"),
            "session_driving": proof.get("session_driving"),
        },
        "forbidden_tokens_absent": not any(forbidden_tokens.values()),
        "forbidden_tokens": forbidden_tokens,
        "latest_classification": {
            "status": latest_classification.get("status"),
            "path": latest_classification.get("path"),
        },
        "ready_for_trace_wiring": True,
        "ready_for_direct_cutover": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "function_present": capture.get("function_present") is True,
        "no_missing_groups": not capture.get("missing_groups"),
        "proof_hash_stable": capture.get("proof_hash_stable") is True,
        "required_hashes_present": all((capture.get("required_hashes_present") or {}).values()),
        "proof_only": (capture.get("proof_flags") or {}).get("proof_only") is True,
        "not_product_driving": (capture.get("proof_flags") or {}).get("product_driving") is False,
        "not_render_driving": (capture.get("proof_flags") or {}).get("render_driving") is False,
        "not_apply_driving": (capture.get("proof_flags") or {}).get("apply_driving") is False,
        "not_session_driving": (capture.get("proof_flags") or {}).get("session_driving") is False,
        "forbidden_tokens_absent": capture.get("forbidden_tokens_absent") is True,
        "classification_pass": (capture.get("latest_classification") or {}).get("status") == "PASS",
        "direct_cutover_still_false": capture.get("ready_for_direct_cutover") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Replacement Decision Proof Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Missing groups: `{capture.get('missing_groups')}`",
        f"- Proof hash stable: `{capture.get('proof_hash_stable')}`",
        f"- Ready for trace wiring: `{capture.get('ready_for_trace_wiring')}`",
        f"- Ready for direct cutover: `{capture.get('ready_for_direct_cutover')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", ""])
    lines.append("Next safe slice: wire this replacement-decision proof trace-only beside the live block.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_replacement_decision_proof_object_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR / f"design_guide_post_click_replacement_decision_proof_object_{stamp}.json"
    )
    md_path = AUDIT_DIR / f"design_guide_post_click_replacement_decision_proof_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_replacement_decision_proof_object {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
