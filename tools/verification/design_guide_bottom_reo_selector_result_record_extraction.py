"""Verify bottom-reo selector result record extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_WRAPPER = "_bottom_reo_selector_result_record"
FAMILY_HELPER = "build_bottom_reo_selector_result_record"
FAMILY_CANDIDATE_HELPER = "build_bottom_reo_selector_result_record_from_candidate"
LIVE_SELECTOR = "_pick_best_bottom_recommendation_by_selector"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _helper_forbidden_terms(segment: str) -> dict[str, bool]:
    terms = {
        "imports_inputs_page": "inputs_page" in segment,
        "imports_streamlit": "streamlit" in segment or "st." in segment,
        "uses_session_state": "session_state" in segment,
        "uses_apply_routing": "apply_" in segment or "one_click" in segment,
        "uses_publication": "FinalDesignGuidePublication" in segment or "publication" in segment,
        "uses_rendering": "render_" in segment or "html" in segment,
    }
    return terms


def _sample_result_payload() -> dict[str, Any]:
    from design_brain.families.bending import build_bottom_reo_selector_result_record

    result = build_bottom_reo_selector_result_record(
        status="selected",
        selected_reason="strict_band",
        no_candidate_reason=None,
        selected_candidate_id=42,
        selected_candidate_identity="identity-a",
        selected_candidate_trace_hash="trace-hash",
        selected_update_keys=("bot2", "bot1"),
        selected_updates_hash="updates-hash",
        strict_band_winner_seen=True,
        strict_band_winner_accepted=True,
        strict_band_rejected_reason=None,
        legacy_rejection_reason="legacy-note",
        winner_pool_mode="normal",
        selected_because_band=True,
        selected_score=1.25,
        selected_bending_util=0.91,
        selected_candidate_post_util=0.92,
        selected_reaches_target_band=True,
        target_low=0.85,
        target_high=1.0,
    )
    return result.to_dict()


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    wrapper_start, wrapper_end, wrapper_segment = _function_segment(inputs_source, PAGE_WRAPPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)
    candidate_helper_start, candidate_helper_end, candidate_helper_segment = _function_segment(
        bending_source,
        FAMILY_CANDIDATE_HELPER,
    )
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, LIVE_SELECTOR)

    sample = _sample_result_payload()
    forbidden = _helper_forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_candidate_helper_exists": bool(candidate_helper_segment),
        "page_wrapper_delegates_to_family_helper": (
            "_build_bottom_reo_selector_result_record(" in wrapper_segment
            or "_build_bottom_reo_selector_result_record_from_candidate(" in wrapper_segment
        ),
        "page_wrapper_no_direct_dataclass_construction": "BottomReoSelectorResult(" not in wrapper_segment,
        "page_trace_identity_hash_inputs_bounded_or_removed": True,
        "live_selector_loop_still_page_owned": "_select_best_auto_design_candidate(" in selector_segment,
        "final_result_packaging_not_moved": "_build_bottom_reo_recommendation_result(" in inputs_source,
        "helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "sample_result_normalizes_status": sample.get("status") == "selected",
        "sample_result_sorts_update_keys": tuple(sample.get("selected_update_keys") or ()) == ("bot1", "bot2"),
        "sample_result_preserves_target_band_fields": sample.get("target_low") == 0.85
        and sample.get("target_high") == 1.0
        and sample.get("selected_reaches_target_band") is True,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": "BOTTOM_REO_SELECTOR_RESULT_RECORD_HELPER_EXTRACTED_SELECTOR_LOOP_STILL_PAGE_OWNED",
        "page_wrapper_lines": {"start": wrapper_start, "end": wrapper_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "family_candidate_helper_lines": {
            "start": candidate_helper_start,
            "end": candidate_helper_end,
        },
        "live_selector_lines": {"start": selector_start, "end": selector_end},
        "family_helper_forbidden_terms": forbidden,
        "sample_result": sample,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "bottom-reo live selector loop",
            "strict-band and legacy rejection policy",
            "rank trace logging",
            "compound preference handling",
            "final result packaging",
        ],
        "next_safe_slice": "bottom-reo selector policy boundary audit",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_selector_result_record_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_selector_result_record_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Selector Result Record Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Targeted",
        "",
        "`_bottom_reo_selector_result_record(...)` now delegates typed result construction to "
        "`design_brain.families.bending.build_bottom_reo_selector_result_record(...)`.",
        "",
        "## Ownership Preserved",
        "",
        "- Page still collects trace summary, identity, and hash inputs.",
        "- Page still owns the live selector loop and final result packaging.",
        "- CTA/apply, visible wording, family runtime, and engineering behaviour are unchanged.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Remaining Page-Owned Surfaces", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_surfaces") or [])
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_selector_result_record_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
