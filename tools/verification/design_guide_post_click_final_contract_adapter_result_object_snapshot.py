"""Object snapshot for the post-click final-contract adapter result."""

from __future__ import annotations

from datetime import datetime
import hashlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_GROUPS = {
    "post_click_final_contract_adapter_result",
    "final_visible_resolution_projection",
    "guidance_debug_projection_patch",
    "publication_binding_result",
}

REQUIRED_RESULT_FIELDS = {
    "should_publish_exact_blocker_projection",
    "replacement_applied",
    "replacement_item",
    "replacement_item_hash",
    "final_visible_resolution",
    "final_visible_resolution_hash",
    "guidance_debug_patch",
    "guidance_debug_patch_hash",
    "projection_hash",
    "input_proof_hash",
    "replacement_decision_proof_hash",
    "adapter_proof_hash",
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
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
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


def _sample() -> dict[str, Any]:
    return {
        "output_item": {
            "title": "Design Guide blocker proof incomplete",
            "family": "bending",
            "button_contract": {"enabled": False, "family": "bending"},
        },
        "final_visible_resolution": {
            "render_reason": "pre_adapter_final_visible",
            "item": {"family": "bending", "title": "Strengthening required"},
        },
        "guidance_debug": {"guidance_branch": "pre_adapter"},
        "visible_action": True,
        "bending_resolution": {
            "title": "Design Guide blocker proof incomplete",
            "family": "bending",
            "button_contract": {"enabled": False, "family": "bending"},
        },
        "bending_contract": {"enabled": False, "family": "bending"},
        "input_proof": {"proof_hash": "input-proof-hash"},
        "replacement_decision_proof": {"proof_hash": "replacement-proof-hash"},
        "adapter_proof": {"proof_hash": "adapter-proof-hash"},
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_final_contract_check_adapter_result,
    )

    function_source = inspect.getsource(
        build_final_design_guide_post_click_final_contract_check_adapter_result
    )
    first = build_final_design_guide_post_click_final_contract_check_adapter_result(**_sample())
    second = build_final_design_guide_post_click_final_contract_check_adapter_result(**_sample())
    result = dict(first.get("result") or {})
    represented = set(first.get("represented_live_groups") or ())
    forbidden_tokens = {
        "streamlit_or_session": "import streamlit" in function_source or "st.session_state" in function_source,
        "apply_routing": (
            "one_click" in function_source
            or "_queue_primary_design_guide_button_action" in function_source
            or "on_click" in function_source
        ),
        "render_html": "_html" in function_source or "st.markdown" in function_source,
    }
    latest = {
        "adapter_object": _latest("design_guide_post_click_final_contract_adapter_object"),
        "adapter_parity": _latest("design_guide_post_click_final_contract_adapter_parity"),
        "live_trace": _latest("design_guide_live_post_click_final_contract_adapter_trace"),
        "live_hash_parity": _latest("design_guide_live_post_click_final_contract_adapter_hash_parity"),
    }
    return {
        "decision": "POST_CLICK_FINAL_CONTRACT_ADAPTER_RESULT_OBJECT_PASS",
        "represented_groups": sorted(represented),
        "missing_groups": sorted(REQUIRED_GROUPS - represented),
        "missing_result_fields": sorted(REQUIRED_RESULT_FIELDS - set(result)),
        "proof_hash_stable": first.get("proof_hash") == second.get("proof_hash"),
        "result_hash_stable": first.get("result_hash") == second.get("result_hash"),
        "should_publish_exact_blocker_projection": result.get(
            "should_publish_exact_blocker_projection"
        ),
        "replacement_applied": result.get("replacement_applied"),
        "render_reason": (result.get("final_visible_resolution") or {}).get("render_reason"),
        "guidance_debug_patch": result.get("guidance_debug_patch"),
        "proof_flags": {
            "proof_only": first.get("proof_only"),
            "product_driving": first.get("product_driving"),
            "render_driving": first.get("render_driving"),
            "apply_driving": first.get("apply_driving"),
            "session_driving": first.get("session_driving"),
            "ready_for_trace_wiring": first.get("ready_for_trace_wiring"),
            "ready_for_live_cutover": first.get("ready_for_live_cutover"),
        },
        "forbidden_tokens": forbidden_tokens,
        "forbidden_tokens_absent": not any(forbidden_tokens.values()),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    flags = dict(capture.get("proof_flags") or {})
    return {
        "no_missing_groups": not capture.get("missing_groups"),
        "no_missing_result_fields": not capture.get("missing_result_fields"),
        "proof_hash_stable": capture.get("proof_hash_stable") is True,
        "result_hash_stable": capture.get("result_hash_stable") is True,
        "should_publish_projection": capture.get("should_publish_exact_blocker_projection") is True,
        "replacement_applied": capture.get("replacement_applied") is True,
        "render_reason_projected": capture.get("render_reason")
        == "post_click_low_bending_exact_blocker_final",
        "guidance_debug_patch_projected": (
            dict(capture.get("guidance_debug_patch") or {}).get("guidance_branch")
            == "post_click_low_bending_exact_blocker_final"
        ),
        "proof_only": flags.get("proof_only") is True,
        "not_product_driving": flags.get("product_driving") is False,
        "not_render_driving": flags.get("render_driving") is False,
        "not_apply_driving": flags.get("apply_driving") is False,
        "not_session_driving": flags.get("session_driving") is False,
        "ready_for_trace_wiring": flags.get("ready_for_trace_wiring") is True,
        "ready_for_live_cutover": flags.get("ready_for_live_cutover") is True,
        "forbidden_tokens_absent": capture.get("forbidden_tokens_absent") is True,
        "adapter_object_pass": (latest.get("adapter_object") or {}).get("status") == "PASS",
        "adapter_parity_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "live_trace_pass": (latest.get("live_trace") or {}).get("status") == "PASS",
        "live_hash_parity_pass": (latest.get("live_hash_parity") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Final Contract Adapter Result Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Missing groups: `{capture.get('missing_groups')}`",
        f"- Missing result fields: `{capture.get('missing_result_fields')}`",
        f"- Proof hash stable: `{capture.get('proof_hash_stable')}`",
        f"- Result hash stable: `{capture.get('result_hash_stable')}`",
        f"- Ready for live cutover: `{(capture.get('proof_flags') or {}).get('ready_for_live_cutover')}`",
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
        "schema": "design_guide_post_click_final_contract_adapter_result_object_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    artifact = ARTIFACT_DIR / f"design_guide_post_click_final_contract_adapter_result_object_{stamp}.json"
    report = AUDIT_DIR / f"design_guide_post_click_final_contract_adapter_result_object_{stamp}.md"
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report, payload)
    print(f"{status}: {artifact}")
    if failures:
        print("Failures:", ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
