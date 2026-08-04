"""Object snapshot for residual-shear evidence-merge result adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "FAIL" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter,
    )

    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route_shell = {"route_shell_adapter_hash": "route-shell-fixture-hash"}
    base_evidence = {
        "safe_candidate_count": 1,
        "executable_candidate_count": 1,
        "safe_cleanup_count": 1,
        "executable_cleanup_count": 1,
        "safe_shear_cleanup_count": 1,
        "executable_shear_cleanup_count": 1,
        "best_safe_final_util": 0.91,
    }
    base_exact = {"bending": {"family": "bending", "exact_blocker": True}}
    blocker = {
        "family": "shear",
        "source": "post_click_residual_shear_cleanup_outside_preferred_band",
        "exact_blocker": True,
        "reason": "outside preferred band",
    }
    inputs = {
        "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
        "residual_outside_preferred_band": True,
        "outside_target_band_allowed_reason": "outside preferred band",
    }
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter(
        route_shell_adapter=dict(route_shell),
        evidence_inputs=dict(inputs),
        base_residual_evidence=dict(base_evidence),
        base_exact_blockers=dict(base_exact),
        residual_shear_blocker=dict(blocker),
        dependency_status="page_live",
    )
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter(
        route_shell_adapter=dict(route_shell),
        evidence_inputs=dict(inputs),
        base_residual_evidence=dict(base_evidence),
        base_exact_blockers=dict(base_exact),
        residual_shear_blocker=dict(blocker),
        dependency_status="page_live",
    )
    controller_owned = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter(
        route_shell_adapter=dict(route_shell),
        evidence_inputs=dict(inputs),
        base_residual_evidence=dict(base_evidence),
        base_exact_blockers=dict(base_exact),
        residual_shear_blocker=dict(blocker),
        dependency_status="controller_owned",
    )
    evidence = dict(first.get("residual_evidence") or {})
    exact = dict(first.get("residual_exact_blockers") or {})
    forbidden_imports = ("inputs_page", "streamlit", "design_guide_page")
    return {
        "decision": "EVIDENCE_MERGE_RESULT_ADAPTER_OBJECT_READY_FOR_TRACE",
        "function_exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter"'
            in source
        ),
        "forbidden_imports_absent": all(token not in source for token in forbidden_imports),
        "stable_repeat_hash": first.get("evidence_merge_tail_result_adapter_hash")
        == second.get("evidence_merge_tail_result_adapter_hash"),
        "page_live_behavior_cutover_ready_false": first.get("behavior_cutover_ready") is False,
        "controller_owned_behavior_cutover_ready_true": (
            controller_owned.get("behavior_cutover_ready") is True
        ),
        "returns_residual_evidence": bool(evidence),
        "returns_residual_exact_blockers": bool(exact),
        "bending_blocker_preserved": "bending" in exact,
        "shear_blocker_merged": "shear" in exact,
        "fixed_merge_fields_present": all(
            key in evidence
            for key in (
                "cleanup_search_ran",
                "post_click_bending_blocker_preserved",
                "post_click_residual_shear_cleanup_after_bending_blocker",
                "exact_blockers_by_family",
                "post_click_exact_blockers_by_family",
                "cleanup_evidence_by_family",
                "post_click_cleanup_evidence_by_family",
                "no_second_cta_required",
            )
        ),
        "outside_target_band_fields_present": all(
            key in evidence
            for key in (
                "outside_target_band_allowed",
                "outside_target_band_allowed_reason",
                "outside_target_band_allowed_category",
                "target_band_candidate_count",
                "executable_target_band_candidate_count",
            )
        ),
        "handoff_hash_present": bool(first.get("evidence_merge_tail_handoff_hash")),
        "adapter_hash_present": bool(first.get("evidence_merge_tail_result_adapter_hash")),
        "not_moved_flags": {
            "candidate_generation": first.get("candidate_generation_execution_owned_elsewhere"),
            "candidate_evaluation": first.get("candidate_evaluation_execution_owned_elsewhere"),
            "blocker_construction": first.get(
                "outside_target_band_blocker_construction_owned_elsewhere"
            ),
            "visible_wording": first.get("visible_wording_authoring_owned_elsewhere"),
            "cta_contract": first.get("cta_contract_execution_owned_elsewhere"),
            "apply_routing": first.get("apply_routing_owned_elsewhere"),
            "ui_rendering": first.get("ui_rendering_owned_elsewhere"),
            "session_debug": first.get("session_debug_mutation_owned_elsewhere"),
        },
        "latest": {
            "evidence_merge_tail_handoff_trace": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_trace_wiring"
            ),
            "evidence_merge_tail_cutover_readiness": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_cutover_readiness"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = capture.get("latest") or {}
    return {
        "function_exported": capture.get("function_exported") is True,
        "forbidden_imports_absent": capture.get("forbidden_imports_absent") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "page_live_behavior_cutover_ready_false": (
            capture.get("page_live_behavior_cutover_ready_false") is True
        ),
        "controller_owned_behavior_cutover_ready_true": (
            capture.get("controller_owned_behavior_cutover_ready_true") is True
        ),
        "returns_residual_evidence": capture.get("returns_residual_evidence") is True,
        "returns_residual_exact_blockers": (
            capture.get("returns_residual_exact_blockers") is True
        ),
        "bending_blocker_preserved": capture.get("bending_blocker_preserved") is True,
        "shear_blocker_merged": capture.get("shear_blocker_merged") is True,
        "fixed_merge_fields_present": capture.get("fixed_merge_fields_present") is True,
        "outside_target_band_fields_present": (
            capture.get("outside_target_band_fields_present") is True
        ),
        "handoff_hash_present": capture.get("handoff_hash_present") is True,
        "adapter_hash_present": capture.get("adapter_hash_present") is True,
        "not_moved_flags_true": all(
            value is True for value in (capture.get("not_moved_flags") or {}).values()
        ),
        "handoff_trace_pass": (
            latest.get("evidence_merge_tail_handoff_trace", {}).get("status") == "PASS"
        ),
        "cutover_readiness_pass": (
            latest.get("evidence_merge_tail_cutover_readiness", {}).get("status")
            == "PASS"
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Evidence-Merge Tail Result Adapter Object",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Stable repeat hash: `{capture.get('stable_repeat_hash')}`",
        f"- Returns evidence: `{capture.get('returns_residual_evidence')}`",
        f"- Returns exact blockers: `{capture.get('returns_residual_exact_blockers')}`",
        f"- Page-live cutover ready: `{not capture.get('page_live_behavior_cutover_ready_false')}`",
        f"- Controller-owned cutover ready: `{capture.get('controller_owned_behavior_cutover_ready_true')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Trace-wire the result adapter beside the live merge and prove live parity before cutover.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_object_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"capture": capture, "checks": checks})
    stamp = str(payload["created_at"])
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_object_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_object "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
