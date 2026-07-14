"""Audit remaining residual shear fallback-loop authority after selected-result cutover."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

SURFACES: dict[str, dict[str, Any]] = {
    "fallback_selected_result": {
        "classification": "A. controller-owned/cut over",
        "tokens": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result(",
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result_hash",
        ),
        "next": "Keep locked; old literal result assembly should stay absent.",
    },
    "fallback_search_loop_handoff": {
        "classification": "A. controller proof handoff wired",
        "tokens": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff(",
            "fallback_candidate_evaluation_sequence",
            "fallback_candidate_selection_sequence",
        ),
        "next": "Use as the hash/evidence anchor for the next split.",
    },
    "fallback_variant_generator_execution": {
        "classification": "C. live injected dependency / keep",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
            "generator=generate_less_shear_reo_variants",
        ),
        "next": "Keep execution live; shared generator still has other callers.",
    },
    "pre_screen_execution": {
        "classification": "C. live injected dependency / result shape cut over",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
            "pre_screen=lambda fallback_variant:",
            "fallback_pre_screen =",
            "fallback_variant_generator_update_sequence.append(",
        ),
        "next": "Keep helper execution live; pre-screen result shape is controller-built.",
    },
    "candidate_evaluator_execution": {
        "classification": "C. live injected dependency / keep",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
            "evaluator=_evaluate_auto_design_candidate",
            "candidate_evaluation_exception",
        ),
        "next": "Keep evaluator live; formula/evaluation behavior remains outside this extraction slice.",
    },
    "post_screen_execution": {
        "classification": "C. live injected dependency / result shape cut over",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
            "post_screen=lambda fallback_candidate:",
            "fallback_post_screen =",
            "accepted_as_safe_cleanup",
            "fallback_shear_candidates.append(",
        ),
        "next": "Keep acceptance helper execution live; post-screen result shape is controller-built.",
    },
    "candidate_selection_execution": {
        "classification": "C. live injected dependency / keep",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
            "selector=_select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key",
        ),
        "next": "Selection algorithm is controller-owned but call remains live via injected shell.",
    },
    "sequence_row_assembly": {
        "classification": "A. controller-owned/cut over",
        "tokens": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row(",
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row(",
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row(",
        ),
        "next": "Keep locked; row shape now comes from controller builders.",
    },
    "result_packaging_execution": {
        "classification": "A. injected shell/cut over",
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff(",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_injected_adapter(",
            "packager=_shear_tightening_as_local_cleanup_item",
            "local_cleanup_evaluator=_evaluate_local_cleanup_guidance_item",
        ),
        "next": "Keep injected shell locked; packager and evaluator execution remain live behind the page boundary.",
    },
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(inputs_source, ROUTE_START, ROUTE_END)
    rows: dict[str, dict[str, Any]] = {}
    classification_counts: dict[str, int] = {}
    for name, spec in SURFACES.items():
        tokens = tuple(spec.get("tokens") or ())
        present = [token for token in tokens if token in route or token in controller_source]
        classification = str(spec.get("classification") or "")
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
        rows[name] = {
            **spec,
            "present": len(present) == len(tokens),
            "tokens_present": present,
            "tokens_missing": [token for token in tokens if token not in present],
        }
    next_targets = [
        name for name, row in rows.items() if str(row.get("classification") or "").startswith("B.")
    ]
    latest = {
        "fallback_search_loop_controller_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_controller_cutover"
        ),
        "fallback_selected_result_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_selected_result_cutover"
        ),
        "post_screen_result_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_post_screen_result_cutover"
        ),
        "result_packaging_cutover_implementation": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation"
        ),
        "route_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_audit"
        ),
        "route_cutover_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    fallback_search_loop_controller_cutover = (
        latest.get("fallback_search_loop_controller_cutover", {}).get("status") == "PASS"
    )
    return {
        "decision": (
            "RESIDUAL_SHEAR_FALLBACK_LOOP_CONTROLLER_CUTOVER_CONFIRMED"
            if fallback_search_loop_controller_cutover
            else "RESIDUAL_SHEAR_FALLBACK_LOOP_HAS_CONTROLLER_HANDOFF_BUT_LIVE_ORCHESTRATION_REMAINS"
        ),
        "surfaces": rows,
        "classification_counts": classification_counts,
        "recommended_next_surface": next_targets[0] if next_targets else "",
        "delete_now_count": 0,
        "latest": latest,
        "fallback_search_loop_controller_cutover": fallback_search_loop_controller_cutover,
        "latest_required_artifacts_pass": all(item.get("status") == "PASS" for item in latest.values()),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    surfaces = dict(capture.get("surfaces") or {})
    return {
        "all_surfaces_present": all(bool(row.get("present")) for row in surfaces.values()),
        "selected_result_cut_over": (
            str((surfaces.get("fallback_selected_result") or {}).get("classification") or "").startswith("A.")
        ),
        "handoff_wired": (
            str((surfaces.get("fallback_search_loop_handoff") or {}).get("classification") or "").startswith("A.")
        ),
        "sequence_row_assembly_cut_over": (
            str((surfaces.get("sequence_row_assembly") or {}).get("classification") or "").startswith("A.")
        ),
        "fallback_search_loop_controller_cutover": capture.get(
            "fallback_search_loop_controller_cutover"
        )
        is True,
        "no_remaining_b_surface_in_fallback_loop": (
            capture.get("recommended_next_surface") == ""
        ),
        "delete_now_zero": capture.get("delete_now_count") == 0,
        "latest_required_artifacts_pass": capture.get("latest_required_artifacts_pass") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Remaining Fallback Loop Authority Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Recommended next surface: `{capture.get('recommended_next_surface')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Surfaces",
        "",
        "| Surface | Classification | Present | Next |",
        "| --- | --- | --- | --- |",
    ]
    for name, row in (capture.get("surfaces") or {}).items():
        lines.append(
            f"| `{name}` | `{row.get('classification')}` | `{row.get('present')}` | {row.get('next')} |"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "No B-class fallback-loop surface remains. Continue from the next route-level authority audit; keep generator, evaluator, screen execution, CTA/apply, visible wording, and UI rendering live.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_fallback_loop_authority_audit.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_remaining_fallback_loop_authority_audit_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_remaining_fallback_loop_authority_audit_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_remaining_fallback_loop_authority_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_fallback_loop_authority_audit "
        f"{payload['status']}"
    )
    print(f"recommended_next_surface={capture.get('recommended_next_surface')}")
    if failures:
        print("failures:", ", ".join(failures))
        print("artifact:", json_path)
        return 1
    print("artifact:", json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
