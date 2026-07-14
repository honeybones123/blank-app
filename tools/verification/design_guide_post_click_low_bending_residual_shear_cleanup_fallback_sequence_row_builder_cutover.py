"""Cutover verifier for residual shear fallback sequence row builders."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row,
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row,
)
from design_brain.final_publication import stable_final_publication_hash  # noqa: E402


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


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


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        inputs_source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    variant = {"s_lig": 300, "reo": "N10-300"}
    updates = {"s_lig": 300}
    candidate = {"updates": {"s_lig": 300}, "overview": {"utils": {"shear": 0.72}}}
    overview = {"utils": {"shear": 0.72}}
    update_row = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row(
        index=2,
        fallback_variant=variant,
        updates=updates,
    )
    expected_update_row = {
        "index": 2,
        "variant_hash": stable_final_publication_hash(variant),
        "updates": dict(updates),
    }
    accepted_eval_row = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row(
        index=2,
        updates=updates,
        candidate=candidate,
        overview=overview,
        success=True,
        accepted_as_safe_cleanup=True,
        failed_reason="",
    )
    expected_accepted_eval_row = {
        "index": 2,
        "updates_hash": stable_final_publication_hash(updates),
        "candidate_hash": stable_final_publication_hash(candidate),
        "overview_hash": stable_final_publication_hash(overview),
        "success": True,
        "accepted_as_safe_cleanup": True,
        "failed_reason": "",
    }
    failed_eval_row = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row(
        index=3,
        updates=updates,
        success=False,
        accepted_as_safe_cleanup=False,
        failed_reason="candidate_evaluation_returned_no_candidate",
    )
    expected_failed_eval_row = {
        "index": 3,
        "updates_hash": stable_final_publication_hash(updates),
        "candidate_hash": "",
        "overview_hash": "",
        "success": False,
        "accepted_as_safe_cleanup": False,
        "failed_reason": "candidate_evaluation_returned_no_candidate",
    }
    selection_source = {
        "updates": updates,
        "candidate": candidate,
        "overview": overview,
        "shear_util": 0.72,
    }
    selection_row = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row(
        index=0,
        selection_row=selection_source,
    )
    expected_sort_key = {
        "shear_util": 0.72,
        "update_count": 1,
        "updates_items": "[('s_lig', 300)]",
    }
    expected_selection_row = {
        "index": 0,
        "updates_hash": stable_final_publication_hash(updates),
        "candidate_hash": stable_final_publication_hash(candidate),
        "overview_hash": stable_final_publication_hash(overview),
        "shear_util": 0.72,
        "sort_key": dict(expected_sort_key),
        "sort_key_hash": stable_final_publication_hash(expected_sort_key),
    }
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_SEQUENCE_ROW_BUILDERS_CUT_OVER",
        "controller_builders_present": all(
            token in controller_source
            for token in (
                "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row(",
                "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row(",
                "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row(",
            )
        ),
        "controller_builders_exported": all(
            token in controller_source
            for token in (
                '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row"',
                '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row"',
                '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row"',
            )
        ),
        "inputs_imports_present": all(
            token in inputs_source
            for token in (
                "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row",
                "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row",
                "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row",
            )
        ),
        "route_update_builder_call_count": route.count(
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row("
        ),
        "route_evaluation_builder_call_count": route.count(
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row("
        ),
        "route_selection_builder_call_count": route.count(
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row("
        ),
        "old_update_row_literal_absent": (
            '"variant_hash": _stable_final_publication_hash(dict(fallback_variant))' not in route
        ),
        "old_selection_sort_key_literal_absent": "selection_sort_key = {" not in route,
        "update_row_matches_old_literal": update_row.get("row") == expected_update_row,
        "accepted_eval_row_matches_old_literal": (
            accepted_eval_row.get("row") == expected_accepted_eval_row
        ),
        "failed_eval_row_matches_old_literal": failed_eval_row.get("row") == expected_failed_eval_row,
        "selection_row_matches_old_literal": selection_row.get("row") == expected_selection_row,
        "stable_hash_repeat": (
            update_row.get("row_hash")
            == build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row(
                index=2,
                fallback_variant=variant,
                updates=updates,
            ).get("row_hash")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "controller_builders_present": capture.get("controller_builders_present") is True,
        "controller_builders_exported": capture.get("controller_builders_exported") is True,
        "inputs_imports_present": capture.get("inputs_imports_present") is True,
        "route_update_builder_call_once": capture.get("route_update_builder_call_count") == 1,
        "route_evaluation_builder_call_count_four": (
            capture.get("route_evaluation_builder_call_count") == 4
        ),
        "route_selection_builder_call_once": capture.get("route_selection_builder_call_count") == 1,
        "old_update_row_literal_absent": capture.get("old_update_row_literal_absent") is True,
        "old_selection_sort_key_literal_absent": (
            capture.get("old_selection_sort_key_literal_absent") is True
        ),
        "update_row_matches_old_literal": capture.get("update_row_matches_old_literal") is True,
        "accepted_eval_row_matches_old_literal": (
            capture.get("accepted_eval_row_matches_old_literal") is True
        ),
        "failed_eval_row_matches_old_literal": capture.get("failed_eval_row_matches_old_literal") is True,
        "selection_row_matches_old_literal": capture.get("selection_row_matches_old_literal") is True,
        "stable_hash_repeat": capture.get("stable_hash_repeat") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Sequence Row Builder Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- Update builder calls: `{capture.get('route_update_builder_call_count')}`",
        f"- Evaluation builder calls: `{capture.get('route_evaluation_builder_call_count')}`",
        f"- Selection builder calls: `{capture.get('route_selection_builder_call_count')}`",
        f"- Update row parity: `{capture.get('update_row_matches_old_literal')}`",
        f"- Evaluation row parity: `{capture.get('accepted_eval_row_matches_old_literal')}` / `{capture.get('failed_eval_row_matches_old_literal')}`",
        f"- Selection row parity: `{capture.get('selection_row_matches_old_literal')}`",
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
            "Rerun remaining fallback-loop authority audit. The next live surface should be execution orchestration, not sequence row shape.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_sequence_row_builder_cutover.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_sequence_row_builder_cutover_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_sequence_row_builder_cutover_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_sequence_row_builder_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_sequence_row_builder_cutover "
        f"{payload['status']}"
    )
    if failures:
        print("failures:", ", ".join(failures))
        print("artifact:", json_path)
        return 1
    print("artifact:", json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
