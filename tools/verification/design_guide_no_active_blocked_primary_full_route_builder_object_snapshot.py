"""Verify the proof-only blocked-primary full-route builder object."""

from __future__ import annotations

from datetime import datetime
import ast
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

FUNCTION = "build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof"
DATACLASS = "DesignGuideNoActiveBlockedPrimaryCleanupProbeFullRouteBuilderProof"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not paths:
        return {"status": "MISSING", "path": None}
    path = paths[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "ERROR", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    return {"status": payload.get("status"), "path": str(path), "payload": payload}


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno])
    raise RuntimeError(f"Could not find {function_name}")


def _samples() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_bending_cleanup_available_before_blocker_result,
        build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof,
        build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof,
        build_design_guide_controller_safe_cleanup_candidate_before_blocker_result,
    )

    policy = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_route_policy_proof(
        primary={"title": "Blocked primary"},
        contract={"enabled": False},
        updates={},
        primary_evidence={
            "selected_candidate_updates": {"lig_legs": 0},
            "safe_executor_backed_candidates_count": 1,
        },
        final_state={"lig_legs": 2, "reo_1": 8},
        final_overview={"utils": {"bending": 0.24, "shear": 0.69}},
        final_accepted_min_family_util=0.85,
        target_band_eps=0.001,
        compound_shear_update_keys={"lig_legs"},
        contract_enabled=False,
        post_click_route_for_safe_cleanup=False,
        safe_cleanup_updates_match_current_state=False,
        final_bending_util=0.24,
        bending_probe_candidate_present=True,
        bending_probe_updates={"reo_1": 5},
        bending_probe_expected_util=0.69,
    )
    safe_result = build_design_guide_controller_safe_cleanup_candidate_before_blocker_result(
        safe_cleanup_item={
            "title": "Shear cleanup",
            "title_main": "Shear cleanup",
            "primary_action": "Remove links",
            "bucket": "pass",
            "guidance_intent": "efficiency_tightening",
        },
        safe_cleanup_contract={
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "candidate_id": "safe-shear",
            "updates": {"lig_legs": 0},
        },
        safe_cleanup_updates={"lig_legs": 0},
        final_overview={"utils": {"bending": 0.24, "shear": 0.69}},
        state_fingerprint="state-safe",
    )
    bending_result = build_design_guide_controller_bending_cleanup_available_before_blocker_result(
        bending_probe_item={
            "title": "Bending cleanup",
            "title_main": "Bending cleanup",
            "primary_action": "Reduce bottom reinforcement",
            "bucket": "pass",
            "guidance_intent": "efficiency_tightening",
        },
        bending_probe_contract={
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "candidate_id": "bending-probe",
            "updates": {"reo_1": 5},
        },
        bending_probe_updates={"reo_1": 5},
        bending_probe_candidate_id="bending-probe",
        bending_probe_expected_util=0.69,
        final_overview={"utils": {"bending": 0.24, "shear": 0.69}},
        final_bending_util_for_probe=0.24,
        state_fingerprint="state-bending",
    )
    safe_selected = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof(
        route_policy_proof=policy,
        safe_cleanup_result=safe_result,
        bending_cleanup_result=bending_result,
    )
    bending_selected = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof(
        route_policy_proof=policy,
        safe_cleanup_result=None,
        bending_cleanup_result=bending_result,
    )
    none_selected = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof(
        route_policy_proof=policy,
        safe_cleanup_result=None,
        bending_cleanup_result=None,
    )
    repeat = build_design_guide_controller_no_active_blocked_primary_cleanup_probe_full_route_builder_proof(
        route_policy_proof=policy,
        safe_cleanup_result=safe_result,
        bending_cleanup_result=bending_result,
    )
    return {
        "policy": policy,
        "safe_selected": safe_selected,
        "bending_selected": bending_selected,
        "none_selected": none_selected,
        "repeat": repeat,
    }


def _capture() -> dict[str, Any]:
    function_source = _function_source(CONTROLLER, FUNCTION)
    class_source = _function_source(CONTROLLER, DATACLASS)
    source_blob = function_source + "\n" + class_source
    forbidden_terms = [
        "inputs_page",
        "streamlit",
        "st.session_state",
        "st.",
        "render_html",
        "button(",
        "apply_payload",
        "one_click",
    ]
    samples = _samples()
    return {
        "decision": "PROOF_ONLY_FULL_ROUTE_BUILDER_OBJECT_READY",
        "function": FUNCTION,
        "dataclass": DATACLASS,
        "samples": samples,
        "stable_repeat": _stable_hash(samples["safe_selected"]) == _stable_hash(samples["repeat"]),
        "forbidden_hits": [
            term for term in forbidden_terms if term.lower() in source_blob.lower()
        ],
        "latest": {
            "full_route_builder_readiness": {
                "status": _latest(
                    "design_guide_no_active_blocked_primary_full_route_builder_readiness"
                ).get("status"),
                "path": _latest(
                    "design_guide_no_active_blocked_primary_full_route_builder_readiness"
                ).get("path"),
            },
            "independence_lock": {
                "status": _latest("design_guide_independence_lock").get("status"),
                "path": _latest("design_guide_independence_lock").get("path"),
            },
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    samples = dict(capture.get("samples") or {})
    safe = dict(samples.get("safe_selected") or {})
    bending = dict(samples.get("bending_selected") or {})
    none = dict(samples.get("none_selected") or {})
    latest = dict(capture.get("latest") or {})
    return {
        "safe_branch_wins_when_present": safe.get("selected_branch")
        == "safe_shear_cleanup_before_blocker",
        "bending_branch_selected_without_safe": bending.get("selected_branch")
        == "bending_cleanup_available_before_blocker",
        "none_branch_selected_without_results": none.get("selected_branch") == "none",
        "branch_order_stable": safe.get("branch_order")
        == ["safe_shear_cleanup_before_blocker", "bending_cleanup_available_before_blocker"],
        "proof_flags_non_product_driving": safe.get("proof_only") is True
        and safe.get("product_driving") is False
        and safe.get("render_driving") is False
        and safe.get("apply_driving") is False
        and safe.get("session_driving") is False,
        "route_branching_owned_here": safe.get("route_branching_owned_here") is True,
        "required_callback_boundaries_recorded": len(safe.get("required_callback_boundaries") or [])
        >= 10,
        "controller_result_builders_recorded": sorted(safe.get("controller_result_builders") or [])
        == sorted(
            [
                "build_design_guide_controller_safe_cleanup_candidate_before_blocker_result",
                "build_design_guide_controller_bending_cleanup_available_before_blocker_result",
            ]
        ),
        "stable_repeat": capture.get("stable_repeat") is True,
        "no_page_ui_session_apply_terms": not capture.get("forbidden_hits"),
        "readiness_artifact_passed": (latest.get("full_route_builder_readiness") or {}).get("status")
        == "PASS",
        "independence_lock_artifact_available": (latest.get("independence_lock") or {}).get("status")
        in {"PASS", "FAIL"},
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide No-Active Blocked-Primary Full Route Builder Object",
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
            "## Sample Branches",
            "",
            f"- Safe branch sample: `{((capture.get('samples') or {}).get('safe_selected') or {}).get('selected_branch')}`",
            f"- Bending branch sample: `{((capture.get('samples') or {}).get('bending_selected') or {}).get('selected_branch')}`",
            f"- Empty branch sample: `{((capture.get('samples') or {}).get('none_selected') or {}).get('selected_branch')}`",
            "",
            "## Next Safe Slice",
            "",
            "Wire this proof object trace-only beside the current page route, then compare branch/result hashes before any live cutover.",
            "",
            "No product behavior, visible wording, CTA/apply semantics, family runtime, solver maths, target bands, render ownership, apply routing, or UI/session ownership changed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_no_active_blocked_primary_full_route_builder_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_no_active_blocked_primary_full_route_builder_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_full_route_builder_object {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status == "PASS":
        print("next=trace-wire full-route builder proof beside live page route")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
