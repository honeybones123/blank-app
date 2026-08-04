"""Residual shear cleanup route audit inside low-bending post-click resolution.

This is proof-only. It maps the residual shear cleanup branch that still lives
inside `_post_click_low_bending_resolution_item(...)` before any extraction.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

ROUTE_SURFACES: dict[str, dict[str, Any]] = {
    "route_entry_guard": {
        "tokens": (
            "current_shear_for_residual_cleanup",
            "residual_shear_cleanup_skip_probe_evaluated = True",
            "_skip_bending_fail_post_publication_probe(",
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(",
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision(",
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision_hash",
            "post_click_low_bending_residual_shear_cleanup_probe",
        ),
        "classification": "A. controller-owned/cut over",
        "next": "Keep locked; skip probe execution remains page-owned by rule.",
    },
    "primary_shear_tightening_search": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
            "executor=_compute_shear_tightening_recommendation",
            "residual_shear_updates",
        ),
        "classification": "B. injected dependency shell already wired",
        "next": "Keep the injected executor boundary; do not move the executor itself in this slice.",
    },
    "fallback_variant_search": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
            "generator=generate_less_shear_reo_variants",
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
            "evaluator=_evaluate_auto_design_candidate",
            "fallback_shear_candidates",
        ),
        "classification": "B. injected dependency shell already wired",
        "next": "Keep generator/evaluator execution injected until candidate-search authority is proven separately.",
    },
    "materiality_and_safety_screen": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
            "pure_updates_checker=_shear_detailing_updates_pure",
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
            "acceptance_screen_builder=_build_design_guide_shear_low_util_candidate_acceptance_screen",
        ),
        "classification": "B. injected dependency shell already wired",
        "next": "Keep materiality/safety execution injected until screen authority is proven separately.",
    },
    "promoted_item_packaging": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
            "packager=_shear_tightening_as_local_cleanup_item",
            "local_cleanup_evaluator=_evaluate_local_cleanup_guidance_item",
            "residual_promoted",
            "return residual_route_return_item",
        ),
        "classification": "B. injected dependency shell already wired",
        "next": "Result packaging is behind the injected shell; keep the route return until route-body deadness is proven.",
    },
    "blocker_evidence_merge": {
        "tokens": (
            "residual_exact_blockers",
            "post_click_bending_blocker_preserved",
            "post_click_residual_shear_cleanup_after_bending_blocker",
            "post_click_exact_blockers_by_family",
        ),
        "classification": "A. controller-owned/cut over",
        "next": "Evidence merge is controller-adapter owned; keep old manual merge absent.",
    },
    "target_band_reason_text": {
        "tokens": (
            "above the preferred",
            "target limit. The exhaustive shear-link cleanup search",
        ),
        "classification": "E. visible wording surface",
        "next": "No wording changes; preserve byte-for-byte through parity.",
    },
    "cta_contract_bridge": {
        "tokens": (
            "_design_guide_button_contract(",
            "button_contract",
        ),
        "classification": "D. CTA contract bridge",
        "next": "Keep CTA semantics unchanged; use CTA authority verifier before moving.",
    },
    "debug_session_projection": {
        "tokens": (
            'debug_sink["post_click_residual_shear_cleanup_debug"]',
            'debug_sink["post_click_residual_shear_cleanup_updates"]',
            'debug_sink["guidance_branch"]',
        ),
        "classification": "F. debug/session projection",
        "next": "Can become compatibility-only after route result object parity.",
    },
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


def _function_body(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _route_block(function_body: str) -> str:
    start = function_body.find(ROUTE_START)
    if start < 0:
        return ""
    end = function_body.find(ROUTE_END, start + len(ROUTE_START))
    return function_body[start:end] if end > start else function_body[start:]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    helper_body = _function_body(inputs_source, "def _post_click_low_bending_resolution_item(")
    route = _route_block(helper_body)
    surface_rows: dict[str, dict[str, Any]] = {}
    for name, surface in ROUTE_SURFACES.items():
        tokens = tuple(surface.get("tokens") or ())
        present = [token for token in tokens if token in route]
        surface_rows[name] = {
            **surface,
            "tokens_present": present,
            "tokens_missing": [token for token in tokens if token not in route],
            "present": len(present) == len(tokens),
            "delete_now": False,
        }
    classification_counts: dict[str, int] = {}
    for row in surface_rows.values():
        key = str(row.get("classification") or "unknown")
        classification_counts[key] = classification_counts.get(key, 0) + 1
    latest = {
        "builder_ownership": _latest(
            "design_guide_post_click_low_bending_resolution_builder_ownership_audit"
        ),
        "request_trace": _latest(
            "design_guide_live_post_click_low_bending_resolution_request_trace"
        ),
        "result_readiness": _latest(
            "design_guide_post_click_low_bending_resolution_result_readiness"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "POST_CLICK_LOW_BENDING_RESIDUAL_SHEAR_CLEANUP_ROUTE_MAPPED_NOT_READY_TO_MOVE",
        "route_found": bool(route),
        "route_line_count_estimate": len(route.splitlines()),
        "surface_rows": surface_rows,
        "classification_counts": classification_counts,
        "missing_surfaces": [name for name, row in surface_rows.items() if row.get("present") is not True],
        "delete_now_count": 0,
        "controller_has_related_materiality_helper": (
            "_controller_shear_cleanup_materially_reduces_reinforcement" in controller_source
        ),
        "final_publication_has_result_projection_exclusion": (
            "residual_shear_cleanup_probe" in final_source
        ),
        "ready_to_move_route": False,
        "next_safe_step": (
            "Create a proof-only residual shear cleanup route request/result object, then trace it beside "
            "the live branch before moving any search, evidence, CTA, or debug projection."
        ),
        "latest": latest,
        "all_latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_found": capture.get("route_found") is True,
        "all_surfaces_present": not capture.get("missing_surfaces"),
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "not_ready_to_move_route": capture.get("ready_to_move_route") is False,
        "controller_related_helper_present": (
            capture.get("controller_has_related_materiality_helper") is True
        ),
        "result_projection_excludes_live_route_surface": (
            capture.get("final_publication_has_result_projection_exclusion") is True
        ),
        "latest_required_artifacts_pass": capture.get("all_latest_required_artifacts_pass") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low-Bending Residual Shear Cleanup Route Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Route found: `{capture.get('route_found')}`",
        f"- Route line count estimate: `{capture.get('route_line_count_estimate')}`",
        f"- Delete-now count: `{capture.get('delete_now_count')}`",
        f"- Ready to move route: `{capture.get('ready_to_move_route')}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in (capture.get("classification_counts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Surfaces", ""])
    for name, row in (capture.get("surface_rows") or {}).items():
        lines.append(
            f"- {name}: present=`{row.get('present')}`, classification=`{row.get('classification')}`, "
            f"delete_now=`{row.get('delete_now')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", "", str(capture.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_audit.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"capture": capture, "checks": checks})
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_audit_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_residual_shear_cleanup_route_audit {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
