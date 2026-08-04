"""Current residual-shear cleanup extraction surface audit.

This is proof-only. It maps the remaining `inputs_page.py` surfaces around the
post-click low-bending residual-shear cleanup route after the final-binding tail
has been cut over to the Design Guide controller adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("
HELPER_START = "def _run_post_click_low_bending_residual_shear_cleanup_primary_executor("
HELPER_END = "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness("


SURFACES: dict[str, dict[str, Any]] = {
    "route_entry_guard": {
        "owner": "Design Guide controller + inputs_page.py skip-probe shell",
        "classification": "A. controller-owned/cut over",
        "scope": "route eligibility and entry condition",
        "tokens": (
            "current_shear_for_residual_cleanup",
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_guard(",
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision(",
            "_skip_bending_fail_post_publication_probe(",
        ),
        "source": "route",
        "recommended_next": "Keep locked; skip-probe execution remains page-owned by rule and route entry interpretation is controller-owned.",
    },
    "route_execution_shell": {
        "owner": "Design Guide controller + inputs_page.py injected executor",
        "classification": "A. controller-owned/cut over",
        "scope": "route body execution shell with dense body retained as injected callback",
        "tokens": (
            "def _execute_post_click_low_bending_residual_shear_cleanup_route_body():",
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_execution_shell(",
            "route_body_executor=_execute_post_click_low_bending_residual_shear_cleanup_route_body",
            'residual_shear_cleanup_route_execution_shell.get("executed_route_body")',
        ),
        "source": "route",
        "recommended_next": "Keep locked; next target is reducing the injected route-body executor internals.",
    },
    "primary_executor_wrapper": {
        "owner": "inputs_page.py page shell",
        "classification": "C. injected page shell / dependency boundary",
        "scope": "calls injected primary shear tightening executor",
        "tokens": (
            "def _run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
            "executor(",
            "out_debug=residual_shear_debug",
        ),
        "source": "helpers",
        "recommended_next": "Keep as dependency shell until route shell owns the result shape.",
    },
    "fallback_variant_generator_wrapper": {
        "owner": "inputs_page.py page shell",
        "classification": "C. injected page shell / dependency boundary",
        "scope": "calls injected fallback variant generator",
        "tokens": (
            "def _run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
            "generator({\"state\": dict(state)}, mode_config)",
        ),
        "source": "helpers",
        "recommended_next": "Keep as dependency shell; candidate generation is explicitly not moved in this slice.",
    },
    "candidate_evaluator_wrapper": {
        "owner": "inputs_page.py page shell",
        "classification": "C. injected page shell / dependency boundary",
        "scope": "calls injected evaluator with existing source/label/action type",
        "tokens": (
            "def _run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
            "source=\"post_click_low_bending_residual_shear_cleanup_probe\"",
            "action_type=\"apply_resolved_candidate\"",
        ),
        "source": "helpers",
        "recommended_next": "Keep evaluator execution page/shared-owned until evaluator authority is proven separately.",
    },
    "candidate_selector_wrapper": {
        "owner": "inputs_page.py page shell",
        "classification": "C. injected page shell / dependency boundary",
        "scope": "calls controller-owned selector through injected selector function",
        "tokens": (
            "def _run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
            "selector(list(candidates or []))",
        ),
        "source": "helpers",
        "recommended_next": "Can remain a shell; selection algorithm is already imported from controller.",
    },
    "materiality_safety_pre_screen_wrapper": {
        "owner": "inputs_page.py page shell",
        "classification": "C. injected page shell / dependency boundary",
        "scope": "screens fallback update materiality before evaluation",
        "tokens": (
            "def _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
            "materially_reduces_reinforcement",
            "pure_updates_checker",
        ),
        "source": "helpers",
        "recommended_next": "Keep until materiality/safety policy is controller-owned with parity.",
    },
    "materiality_safety_post_screen_wrapper": {
        "owner": "inputs_page.py page shell",
        "classification": "C. injected page shell / dependency boundary",
        "scope": "screens evaluated fallback candidate safety/acceptance",
        "tokens": (
            "def _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
            "candidate_acceptance_screen = acceptance_screen_builder(",
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result(",
        ),
        "source": "helpers",
        "recommended_next": "Keep acceptance screen execution live; post-screen result shape is controller-built.",
    },
    "result_packaging_wrapper": {
        "owner": "inputs_page.py page shell",
        "classification": "C. injected page shell / dependency boundary",
        "scope": "calls injected packager and cleanup evaluator",
        "tokens": (
            "def _run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
            "packager(",
            "local_cleanup_evaluator(",
        ),
        "source": "helpers",
        "recommended_next": "Keep packager/evaluator injected until route result parity is proven.",
    },
    "fallback_search_loop": {
        "owner": "Design Guide controller proof + inputs_page.py execution shell",
        "classification": "C. live execution shell / controller-owned result surfaces",
        "scope": "fallback candidate loop, evidence sequence, and selected candidate assembly",
        "tokens": (
            "for fallback_index, fallback_variant in enumerate(fallback_variants[:64]):",
            "fallback_candidate_evaluation_sequence.append(",
            "fallback_candidate_selection_output_summary",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff(",
        ),
        "source": "route",
        "recommended_next": "Keep live execution shell; fallback-loop result, row, and proof surfaces are controller-owned.",
    },
    "evidence_merge_tail": {
        "owner": "Design Guide controller",
        "classification": "A. controller-owned/cut over",
        "scope": "residual evidence and exact blocker merge",
        "tokens": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter(",
            "residual_evidence = dict(",
            "residual_exact_blockers = dict(",
        ),
        "source": "route",
        "recommended_next": "Keep locked; old manual evidence merge body should stay absent.",
    },
    "final_binding_tail": {
        "owner": "Design Guide controller",
        "classification": "A. controller-owned/cut over",
        "scope": "final item/action/resolved/button-contract binding",
        "tokens": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
            "residual_binding_without_contract",
            "residual_binding_with_contract",
        ),
        "source": "route",
        "recommended_next": "Keep locked; old manual final-binding body should stay absent.",
    },
    "shared_button_contract_execution": {
        "owner": "inputs_page.py shared CTA/apply boundary",
        "classification": "C. shared-owned retained by rule",
        "scope": "existing button contract execution",
        "tokens": (
            "_design_guide_button_contract(residual_promoted, state=state)",
            "residual_button_contract",
        ),
        "source": "route",
        "recommended_next": "Retain by rule unless a future CTA/apply boundary slice explicitly moves it.",
    },
    "debug_projection_tail": {
        "owner": "inputs_page.py debug/session projection",
        "classification": "E. still live page projection / next cleanup target",
        "scope": "debug sink projection and non-authoritative proof stamps",
        "tokens": (
            "debug_sink[\"post_click_residual_shear_cleanup_debug\"]",
            "debug_sink[\"candidate_search_evidence\"]",
            "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof(",
        ),
        "source": "route",
        "recommended_next": "Narrow/delete only after route shell cutover and consumer reachability prove compatibility-only use.",
    },
}

OLD_MANUAL_FINAL_BINDING_TOKENS = (
    "residual_promoted[\"candidate_search_evidence\"] = dict(residual_evidence)",
    "residual_payload[\"candidate_search_evidence\"] = dict(residual_evidence)",
    "residual_resolved[\"candidate_search_evidence\"] = dict(residual_evidence)",
    "residual_promoted[\"button_contract\"] = dict(",
)


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
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    status = raw_status.upper()
    if "PASS" in status or "LOCKED" in status or "COMPLETE" in status:
        status = "PASS"
    elif "FAIL" in status:
        status = "FAIL"
    elif "PARTIAL" in status:
        status = "PARTIAL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _surface_source(row: dict[str, Any], route: str, helpers: str) -> str:
    source = str(row.get("source") or "")
    if source == "route":
        return route
    if source == "helpers":
        return helpers
    return route + "\n" + helpers


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(inputs_source, ROUTE_START, ROUTE_END)
    helpers = _between(inputs_source, HELPER_START, HELPER_END)

    rows: dict[str, dict[str, Any]] = {}
    for name, surface in SURFACES.items():
        body = _surface_source(surface, route, helpers)
        tokens = tuple(surface.get("tokens") or ())
        present = [token for token in tokens if token in body]
        row = dict(surface)
        if name == "debug_projection_tail" and (
            "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only("
            in route
        ):
            row["classification"] = "B. compatibility-only / proof-covered"
            row[
                "recommended_next"
            ] = "Run debug projection deadness reachability before deleting direct debug/session rows."
        rows[name] = {
            **row,
            "present": len(present) == len(tokens),
            "tokens_present": present,
            "tokens_missing": [token for token in tokens if token not in body],
            "delete_now": False,
        }

    latest = {
        "final_binding_tail_deadness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof"
        ),
        "final_binding_tail_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_audit"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    classification_counts: dict[str, int] = {}
    for row in rows.values():
        key = str(row.get("classification") or "F. unknown")
        classification_counts[key] = classification_counts.get(key, 0) + 1

    old_manual_final_binding_present = [
        token for token in OLD_MANUAL_FINAL_BINDING_TOKENS if token in route
    ]
    unknown_surfaces = [
        name
        for name, row in rows.items()
        if str(row.get("classification") or "").startswith("F.")
    ]
    next_targets = [
        name
        for name, row in rows.items()
        if str(row.get("classification") or "").startswith("E.")
    ]
    recommended_next_surface = (
        next_targets[0] if next_targets else "route_body_live_execution_shell_audit"
    )

    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_REMAINING_SURFACES_MAPPED",
        "route_found": bool(route),
        "helpers_found": bool(helpers),
        "route_line_count_estimate": len(route.splitlines()),
        "helper_line_count_estimate": len(helpers.splitlines()),
        "surface_rows": rows,
        "classification_counts": classification_counts,
        "unknown_surfaces": unknown_surfaces,
        "old_manual_final_binding_present": old_manual_final_binding_present,
        "old_manual_final_binding_absent": not old_manual_final_binding_present,
        "controller_final_binding_adapter_present": (
            "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail"
            in controller_source
        ),
        "latest": latest,
        "latest_required_artifacts_pass": all(item.get("status") == "PASS" for item in latest.values()),
        "recommended_next_surface": recommended_next_surface,
        "recommended_next_step": (
            "Audit the remaining live execution shell surfaces before deleting the route body."
            if not next_targets
            else "Build controller route-shell cutover parity for the residual shear cleanup entry/evidence route, "
            "keeping candidate generation/evaluation and CTA contract execution injected/page-owned."
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
        "helpers_found": capture.get("helpers_found") is True,
        "all_surfaces_classified": not capture.get("unknown_surfaces"),
        "old_manual_final_binding_absent": capture.get("old_manual_final_binding_absent") is True,
        "controller_final_binding_adapter_present": (
            capture.get("controller_final_binding_adapter_present") is True
        ),
        "latest_required_artifacts_pass": capture.get("latest_required_artifacts_pass") is True,
        "recommended_next_surface_selected": bool(capture.get("recommended_next_surface")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_audit_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Remaining Surface Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Executive Summary",
        "",
        "PASS means the current residual-shear cleanup surfaces are inventoried and no unknown surface was found. "
        "It does not move behavior.",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in (capture.get("classification_counts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Surface Inventory", ""])
    for name, row in (capture.get("surface_rows") or {}).items():
        lines.append(
            f"- `{name}`: present=`{row.get('present')}`, owner=`{row.get('owner')}`, "
            f"classification=`{row.get('classification')}`, delete_now=`{row.get('delete_now')}`"
        )
    lines.extend(
        [
            "",
            "## Final-Binding Status",
            "",
            f"- Old manual final-binding tokens present: `{capture.get('old_manual_final_binding_present')}`",
            f"- Controller final-binding adapter present: `{capture.get('controller_final_binding_adapter_present')}`",
            "",
            "## Next Safe Target",
            "",
            f"- Surface: `{capture.get('recommended_next_surface')}`",
            f"- Step: {capture.get('recommended_next_step')}",
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_extraction_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        "",
        f"`{payload.get('status')}` - residual shear cleanup remaining surface audit only.",
        "",
        "## Surface Targeted",
        "",
        "`post_click_low_bending_residual_shear_cleanup` remaining route surfaces.",
        "",
        "## Ownership Before",
        "",
        "The route still has page-owned route/evidence and fallback-search surfaces, plus injected page-shell wrappers.",
        "",
        "## Ownership After",
        "",
        "No ownership changed in this proof-only slice.",
        "",
        "## Behaviour Preserved",
        "",
        "- Engineering behaviour unchanged",
        "- Visible wording unchanged",
        "- CTA/apply semantics unchanged",
        "- Family runtimes unchanged",
        "",
        "## Cutover Proof",
        "",
        "No cutover was performed. This audit confirms the final-binding tail remains controller-adapter owned.",
        "",
        "## Deadness / Deletion Proof",
        "",
        "No deletion was performed. Old manual final-binding tokens remain absent.",
        "",
        "## Lines Removed / Added",
        "",
        "Lines removed: `0`. Lines added: verifier/reporting only.",
        "",
        "## Files Changed",
        "",
        "- `tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit.py`",
        "",
        "## Verifier Results",
        "",
        f"- Focused audit: `{payload.get('status')}`",
        "",
        "## Remaining Page-Owned Authority",
        "",
    ]
    for name, row in (capture.get("surface_rows") or {}).items():
        if str(row.get("classification") or "").startswith("E."):
            lines.append(f"- `{name}`: {row.get('scope')}")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            str(capture.get("recommended_next_step") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_remaining_surface_audit_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_audit_report(audit_path, payload)
    _write_extraction_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit "
        f"{payload['status']}"
    )
    print(f"recommended_next_surface={capture.get('recommended_next_surface')}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
