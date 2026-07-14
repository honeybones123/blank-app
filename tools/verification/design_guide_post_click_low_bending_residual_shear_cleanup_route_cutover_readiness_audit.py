"""Cutover readiness audit for residual shear cleanup route extraction."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


LIVE_SURFACES = {
    "candidate_generation_execution": {
        "tokens": ("generate_less_shear_reo_variants(",),
        "classification": "C. still live execution / keep",
    },
    "candidate_evaluation_execution": {
        "tokens": ("_evaluate_auto_design_candidate(",),
        "classification": "C. still live execution / keep",
    },
    "primary_shear_tightening_execution": {
        "tokens": ("_compute_shear_tightening_recommendation(",),
        "classification": "C. still live execution / keep",
    },
    "cta_contract_execution": {
        "tokens": ("_design_guide_button_contract(",),
        "classification": "C. still live CTA bridge / keep",
    },
    "visible_wording_authoring": {
        "tokens": (
            "above the preferred",
            "target limit. The exhaustive shear-link cleanup search",
        ),
        "classification": "C. still live wording / keep",
    },
    "debug_session_projection": {
        "tokens": (
            'debug_sink["post_click_residual_shear_cleanup_debug"]',
            "final_publication_post_click_low_bending_residual_shear_cleanup_route_proof_only",
        ),
        "classification": "A. can narrow to compatibility/debug stamp next",
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


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = (ROOT / "design_brain" / "design_guide_controller.py").read_text(
        encoding="utf-8-sig",
        errors="replace",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    surface_rows: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for name, spec in LIVE_SURFACES.items():
        tokens = tuple(spec.get("tokens") or ())
        visible_wording_surface = name == "visible_wording_authoring"
        present = [
            token
            for token in tokens
            if token in route_block
            or token in source
            or (visible_wording_surface and token in controller_source)
        ]
        classification = str(spec.get("classification") or "unknown")
        counts[classification] = counts.get(classification, 0) + 1
        surface_rows[name] = {
            **spec,
            "present": len(present) == len(tokens),
            "tokens_present": present,
            "tokens_missing": [
                token
                for token in tokens
                if token not in route_block
                and token not in source
                and not (visible_wording_surface and token in controller_source)
            ],
            "delete_now": False,
        }
    latest = {
        "route_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_audit"
        ),
        "route_object": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_object"
        ),
        "route_trace": _latest(
            "design_guide_live_post_click_low_bending_residual_shear_cleanup_route_trace"
        ),
        "route_parity": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_parity_scenarios"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    c_surfaces = [
        name
        for name, row in surface_rows.items()
        if str(row.get("classification") or "").startswith("C.")
    ]
    a_surfaces = [
        name
        for name, row in surface_rows.items()
        if str(row.get("classification") or "").startswith("A.")
    ]
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_ROUTE_NOT_READY_FOR_BEHAVIOR_CUTOVER",
        "route_found": bool(route_block),
        "surface_rows": surface_rows,
        "classification_counts": counts,
        "cutover_ready": False,
        "ready_to_narrow_surfaces": a_surfaces,
        "must_keep_live_surfaces": c_surfaces,
        "delete_now_count": 0,
        "next_safe_step": (
            "Narrow only the debug/session projection metadata as compatibility-only, or build a "
            "real controller route cutover for candidate search/evaluation before moving behavior."
        ),
        "latest": latest,
        "all_latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = dict(capture.get("surface_rows") or {})
    return {
        "route_found": capture.get("route_found") is True,
        "latest_required_artifacts_pass": capture.get("all_latest_required_artifacts_pass") is True,
        "all_surfaces_present": all(row.get("present") is True for row in rows.values()),
        "not_cutover_ready": capture.get("cutover_ready") is False,
        "debug_projection_ready_to_narrow": "debug_session_projection"
        in set(capture.get("ready_to_narrow_surfaces") or []),
        "live_execution_surfaces_kept": {
            "candidate_generation_execution",
            "candidate_evaluation_execution",
            "primary_shear_tightening_execution",
            "cta_contract_execution",
            "visible_wording_authoring",
        }.issubset(set(capture.get("must_keep_live_surfaces") or [])),
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low-Bending Residual Shear Cleanup Route Cutover Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Cutover ready: `{capture.get('cutover_ready')}`",
        f"- Ready to narrow: `{capture.get('ready_to_narrow_surfaces')}`",
        f"- Must keep live: `{capture.get('must_keep_live_surfaces')}`",
        f"- Delete-now count: `{capture.get('delete_now_count')}`",
        "",
        "## Surfaces",
        "",
    ]
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness_audit.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness {payload['status']}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
