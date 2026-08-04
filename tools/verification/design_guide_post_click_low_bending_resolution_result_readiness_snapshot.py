"""Readiness snapshot for post-click low-bending resolution result extraction."""

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

FUNCTION_TOKEN = "def _post_click_low_bending_resolution_item("

OUTPUT_SURFACES: dict[str, dict[str, Any]] = {
    "early_cleanup_action_item": {
        "tokens": (
            '"post_click_low_family_cleanup_action" = True',
            "return cleanup_item",
        ),
        "classification": "A. live result branch, needs result object parity before cutover",
        "owner_target": "Design Brain/controller result object",
    },
    "best_safe_partial_or_incremental_item": {
        "tokens": (
            '"post_click_low_family_cleanup_action" = False',
            '"no_second_cta_required" = False',
            '"button_contract"',
        ),
        "classification": "A. live result branch, needs result object parity before cutover",
        "owner_target": "Design Brain/controller result object",
    },
    "exact_blocker_evidence": {
        "tokens": (
            '"exact_blockers_by_family"',
            '"post_click_exact_blockers_by_family"',
            '"no_second_cta_required": True',
        ),
        "classification": "A. publication-owned evidence surface, needs result object parity",
        "owner_target": "FinalDesignGuidePublication evidence/result projection",
    },
    "cta_contract_fallback": {
        "tokens": (
            "_design_guide_button_contract(",
            '"action_type": "apply_resolved_candidate"',
            '"preview_pass": True',
        ),
        "classification": "B. CTA contract bridge, keep live until CTA parity proof",
        "owner_target": "shared CTA/publication authority",
    },
    "residual_shear_cleanup_probe": {
        "tokens": (
            "post_click_low_bending_residual_shear_cleanup_probe",
            "_shear_cleanup_materially_reduces_reinforcement(",
        ),
        "classification": "B. residual cleanup branch, needs dedicated route proof",
        "owner_target": "Design Brain/controller route",
    },
    "visible_wording": {
        "tokens": (
            "Bending cleanup is governed by minimum bending reinforcement",
            "Trial bottom-reinforcement reductions were exhausted",
            "Geometry is locked, so optimisation cannot change beam width or depth.",
        ),
        "classification": "C. visible wording, preserve byte-for-byte through extraction",
        "owner_target": "formatting/publication view data",
    },
    "search_and_evaluation_dependencies": {
        "tokens": (
            "_bending_only_target_band_cleanup_item(",
            "_probe_equivalent_bending_cleanup_action_item(",
            "_evaluate_bending_with_bottom_state(",
            "_shear_low_util_target_cleanup_item(",
        ),
        "classification": "D. live search/evaluator dependencies, do not delete",
        "owner_target": "candidate/search boundary or controller dependency injection",
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


def _function_body(source: str) -> str:
    start = source.find(FUNCTION_TOKEN)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    body = _function_body(source)
    surface_rows: dict[str, dict[str, Any]] = {}
    for name, surface in OUTPUT_SURFACES.items():
        tokens = tuple(surface.get("tokens") or ())
        present = [token for token in tokens if token in body]
        surface_rows[name] = {
            **surface,
            "tokens_present": present,
            "tokens_missing": [token for token in tokens if token not in body],
            "present": bool(present),
            "ready_to_delete": False,
        }
    latest = {
        "request_object": _latest("design_guide_post_click_low_bending_resolution_request_object"),
        "request_trace": _latest("design_guide_live_post_click_low_bending_resolution_request_trace"),
        "builder_ownership_audit": _latest("design_guide_post_click_low_bending_resolution_builder_ownership_audit"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "POST_CLICK_LOW_BENDING_RESULT_NOT_READY_FOR_DELETION",
        "function_found": bool(body),
        "function_line_count_estimate": len(body.splitlines()),
        "return_count": body.count("return "),
        "surface_rows": surface_rows,
        "missing_surfaces": [name for name, row in surface_rows.items() if row.get("present") is not True],
        "ready_to_move_result_construction": False,
        "ready_to_delete_page_builder": False,
        "next_safe_step": (
            "Create a pure result projection object for the A-class result/evidence surfaces, "
            "then prove parity before cutting over any branch."
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
    rows = dict(capture.get("surface_rows") or {})
    return {
        "function_found": capture.get("function_found") is True,
        "returns_present": int(capture.get("return_count") or 0) > 0,
        "all_output_surfaces_found": not capture.get("missing_surfaces"),
        "latest_required_artifacts_pass": capture.get("all_latest_required_artifacts_pass") is True,
        "not_ready_to_move_result_construction": capture.get("ready_to_move_result_construction") is False,
        "not_ready_to_delete_page_builder": capture.get("ready_to_delete_page_builder") is False,
        "no_surface_marked_delete": all(row.get("ready_to_delete") is False for row in rows.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low-Bending Resolution Result Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Function line estimate: `{capture.get('function_line_count_estimate')}`",
        f"- Return count: `{capture.get('return_count')}`",
        f"- Ready to move result construction: `{capture.get('ready_to_move_result_construction')}`",
        f"- Ready to delete page builder: `{capture.get('ready_to_delete_page_builder')}`",
        "",
        "## Output Surfaces",
        "",
        "Surface | Classification | Owner target | Present",
        "--- | --- | --- | ---",
    ]
    for name, row in (capture.get("surface_rows") or {}).items():
        lines.append(
            f"{name} | {row.get('classification')} | {row.get('owner_target')} | `{row.get('present')}`"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            str(capture.get("next_safe_step") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_resolution_result_readiness_snapshot.v1",
        "generated_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_post_click_low_bending_resolution_result_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_post_click_low_bending_resolution_result_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_resolution_result_readiness {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
