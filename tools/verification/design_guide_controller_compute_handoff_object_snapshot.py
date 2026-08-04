"""Verify the proof-only controller compute handoff object.

This snapshot proves the DesignGuideController can represent the compute-stage
publication handoff/rebound surface as a stable Design Brain object without
importing page/UI/session/render/apply ownership.
"""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _sample_request() -> dict[str, Any]:
    selected_item = {
        "title_main": "Strengthening required",
        "status": "ACTION",
        "bucket": "fail",
        "family": "BENDING_FAIL_GOVERNS",
        "action_type": "increase_depth",
        "guidance_intent": "repair",
        "candidate_id": "sample_candidate_1",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "increase_depth",
            "family": "BENDING_FAIL_GOVERNS",
            "candidate_id": "sample_candidate_1",
            "updates": {"D": 650},
            "executor_backed": True,
        },
        "candidate_search_evidence": {
            "safe_executor_backed_candidates_count": 1,
            "executor_backed": True,
        },
    }
    return {
        "current_state": {"b": 300, "D": 600, "Mu": 300},
        "overview": {"worst_util": 1.22, "any_fail": True},
        "collapsed_guidance_items": [dict(selected_item)],
        "publication_context": {"source": "sample_context"},
        "publication_dependencies": {"source": "sample_dependencies"},
        "final_compute_resolution": {
            "item": dict(selected_item),
            "render_reason": "compute_publication_resolution",
            "state_fingerprint": "sample_state_fingerprint",
        },
        "blocker_evidence_surface": {
            "candidate_search_evidence": dict(selected_item["candidate_search_evidence"]),
            "exact_blockers_by_family": {},
            "source": "object_snapshot_sample",
            "proof_only": True,
            "product_driving": False,
        },
        "late_evidence_acceptance": {"accepted": True, "reason": "sample"},
        "rebound_contract": dict(selected_item["button_contract"]),
        "rebound_update_payload": {"D": 650},
        "post_core_evidence_mismatch": {"accepted": False, "reason": "not_needed"},
        "pre_resolver_collapsed_item_mutation": {
            "before_identity": {"candidate_id": "sample_candidate_1"},
            "after_identity": {"candidate_id": "sample_candidate_1"},
            "mutation_reason": "compute_publication_resolution",
        },
        "debug": {"design_brain_result": {"selected_family": "BENDING_FAIL_GOVERNS"}},
        "verifier_payload": {"source": "sample_verifier_payload"},
        "publication_reason": "compute_publication_resolution",
        "source": "object_snapshot_sample",
    }


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerComputePublicationHandoffRequest,
        DesignGuideControllerComputePublicationHandoffResponse,
        run_design_guide_controller_compute_publication_handoff_trace_only,
    )

    source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    request_payload = _sample_request()
    request = DesignGuideControllerComputePublicationHandoffRequest(**request_payload)
    first = run_design_guide_controller_compute_publication_handoff_trace_only(request)
    second = run_design_guide_controller_compute_publication_handoff_trace_only(request)
    first_d = first.to_dict()
    second_d = second.to_dict()
    proof = dict(first.compute_handoff_rebound_decision_proof or {})
    required_response_fields = {
        "selected_item": bool(first.selected_item),
        "selected_item_hash": bool(first.selected_item_hash),
        "final_visible_resolution": bool(first.final_visible_resolution),
        "final_visible_resolution_hash": bool(first.final_visible_resolution_hash),
        "publication": bool(first.publication),
        "publication_hash": bool(first.publication_hash),
        "compute_handoff_rebound_decision_proof": bool(first.compute_handoff_rebound_decision_proof),
        "compute_handoff_rebound_decision_hash": bool(first.compute_handoff_rebound_decision_hash),
        "parity_payload": bool(first.parity_payload),
        "controller_hash": bool(first.controller_hash),
    }
    forbidden_source_tokens = {
        "inputs_page_import": "inputs_page" in source,
        "streamlit_import": "streamlit" in source,
        "session_state": "st.session_state" in source,
        "render_panel": "render_final_panel" in source,
        "apply_routing_function": "_record_rendered_design_guide_primary_apply_payload" in source,
    }
    return {
        "request_class": DesignGuideControllerComputePublicationHandoffRequest.__name__,
        "response_class": DesignGuideControllerComputePublicationHandoffResponse.__name__,
        "stable_controller_hash": first.controller_hash == second.controller_hash,
        "stable_request_hash": first.request_hash == second.request_hash,
        "stable_publication_hash": first.publication_hash == second.publication_hash,
        "stable_decision_hash": (
            first.compute_handoff_rebound_decision_hash
            == second.compute_handoff_rebound_decision_hash
        ),
        "response_hash": _stable_hash(first_d),
        "repeat_response_hash": _stable_hash(second_d),
        "required_response_fields": required_response_fields,
        "blocker_evidence_surface_present": bool(proof.get("blocker_evidence_surface")),
        "blocker_evidence_surface_hash": _stable_hash(proof.get("blocker_evidence_surface") or {}),
        "covered_blocking_fields": list(proof.get("covered_blocking_fields") or []),
        "missing_blocking_fields": list(proof.get("missing_blocking_fields") or []),
        "product_flags": {
            "trace_only": first.trace_only,
            "product_driving": first.product_driving,
            "render_driving": first.render_driving,
            "apply_driving": first.apply_driving,
            "session_driving": first.session_driving,
        },
        "forbidden_source_tokens_present": forbidden_source_tokens,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    flags = dict(capture.get("product_flags") or {})
    return {
        "request_response_classes_exist": bool(capture.get("request_class"))
        and bool(capture.get("response_class")),
        "stable_hashes": (
            capture.get("stable_controller_hash") is True
            and capture.get("stable_request_hash") is True
            and capture.get("stable_publication_hash") is True
            and capture.get("stable_decision_hash") is True
            and capture.get("response_hash") == capture.get("repeat_response_hash")
        ),
        "required_response_fields_present": all(
            (capture.get("required_response_fields") or {}).values()
        ),
        "blocker_evidence_surface_present": capture.get("blocker_evidence_surface_present") is True,
        "all_blocking_fields_covered": len(capture.get("covered_blocking_fields") or []) == 9
        and not capture.get("missing_blocking_fields"),
        "trace_only_not_product_driving": (
            flags.get("trace_only") is True
            and flags.get("product_driving") is False
            and flags.get("render_driving") is False
            and flags.get("apply_driving") is False
            and flags.get("session_driving") is False
        ),
        "no_page_ui_session_apply_imports": not any(
            (capture.get("forbidden_source_tokens_present") or {}).values()
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Controller Compute Handoff Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- Covered blocking fields: `{len(capture.get('covered_blocking_fields') or [])}`",
            f"- Missing blocking fields: `{capture.get('missing_blocking_fields')}`",
            f"- Stable controller hash: `{capture.get('stable_controller_hash')}`",
            f"- Stable response hash: `{capture.get('response_hash') == capture.get('repeat_response_hash')}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_controller_compute_handoff_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_controller_compute_handoff_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_controller_compute_handoff_object_snapshot {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
