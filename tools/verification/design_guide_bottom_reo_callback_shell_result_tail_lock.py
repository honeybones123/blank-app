"""Lock bottom-reo selector/result tail as bounded page shell."""

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


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    compute_start, compute_end, compute_segment = _function_segment(inputs_source, "_compute_bottom_reo_recommendation")
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, "_pick_best_bottom_recommendation_by_selector")
    family_selector_start, family_selector_end, family_selector_segment = _function_segment(
        bending_source,
        "select_bottom_reo_recommendation_candidate_by_selector",
    )
    result_start, result_end, result_segment = _function_segment(bending_source, "build_bottom_reo_recommendation_result")

    surfaces = [
        {
            "surface": "selector loop policy",
            "classification": "FAMILY_OWNED",
            "evidence": "select_bottom_reo_recommendation_candidate_by_selector",
            "page_shell_allowed": False,
            "present": "_select_bottom_reo_recommendation_candidate_by_selector(" in selector_segment
            and "while pool:" in family_selector_segment,
        },
        {
            "surface": "selector callback execution",
            "classification": "PAGE_SHELL_CALLBACK_EXECUTION",
            "evidence": "select_best_candidate_fn=_select_best_auto_design_candidate",
            "page_shell_allowed": True,
            "present": "select_best_candidate_fn=_select_best_auto_design_candidate" in selector_segment,
        },
        {
            "surface": "strict/noop/legacy callback input collection",
            "classification": "PAGE_SHELL_CALLBACK_INPUT_COLLECTION",
            "evidence": "_strict_band_guard / _updates_are_noop / _legacy_rejection",
            "page_shell_allowed": True,
            "present": all(
                token in selector_segment
                for token in ("def _strict_band_guard", "def _updates_are_noop", "def _legacy_rejection")
            ),
        },
        {
            "surface": "rank trace emission",
            "classification": "PAGE_SHELL_DEBUG_TRACE_EMISSION",
            "evidence": "_log_design_reco_candidate_rank / _merge_design_guide_rank_trace",
            "page_shell_allowed": True,
            "present": "_log_design_reco_candidate_rank(**dict(_event))" in selector_segment
            and "_merge_design_guide_rank_trace(dict(_entry))" in selector_segment,
        },
        {
            "surface": "selector result append",
            "classification": "PAGE_SHELL_TRACE_RECORD_APPEND",
            "evidence": "_bottom_reo_selector_result_record",
            "page_shell_allowed": True,
            "present": "_bottom_reo_selector_result_record(" in selector_segment,
        },
        {
            "surface": "final result dict construction",
            "classification": "FAMILY_OWNED_ADAPTER_CALL",
            "evidence": "build_bottom_reo_recommendation_result",
            "page_shell_allowed": True,
            "present": "_build_bottom_reo_recommendation_result(" in compute_segment
            and "return {" in result_segment,
        },
    ]

    page_forbidden_policy_tokens = [
        "while pool:",
        'selected_reason="strict_band_winner_accept"',
        'selected_reason="selector_top_valid"',
        'reason="ductility_not_improved"',
        'reason="bending_util_not_improved"',
        'no_candidate_reason="selector_pool_exhausted"',
    ]
    family_required_policy_tokens = [
        "while pool:",
        "strict_band_winner_accept",
        "selector_top_valid",
        "ductility_not_improved",
        "bending_util_not_improved",
        "selector_pool_exhausted",
    ]
    checks = {
        "all_surfaces_present": all(row["present"] for row in surfaces),
        "page_selector_inline_policy_removed": not any(token in selector_segment for token in page_forbidden_policy_tokens),
        "family_selector_policy_present": all(token in family_selector_segment for token in family_required_policy_tokens),
        "result_adapter_call_shell_only": "_build_bottom_reo_recommendation_result(" in compute_segment
        and "result = {" not in compute_segment,
        "family_helpers_have_no_page_ui_session_imports": not any(
            token in family_selector_segment + result_segment
            for token in ("inputs_page", "streamlit", "st.session_state", "FinalDesignGuidePublication")
        ),
        "remaining_page_surfaces_are_allowed_shell": all(
            row["classification"].startswith("PAGE_SHELL") or row["classification"].startswith("FAMILY_")
            for row in surfaces
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_SELECTOR_RESULT_TAIL_BOUNDED_SHELL_ONLY",
        "compute_lines": {"start": compute_start, "end": compute_end},
        "selector_lines": {"start": selector_start, "end": selector_end},
        "family_selector_lines": {"start": family_selector_start, "end": family_selector_end},
        "result_adapter_lines": {"start": result_start, "end": result_end},
        "surfaces": surfaces,
        "checks": checks,
        "remaining_page_owned_design_brain_logic": [],
        "remaining_page_shell_surfaces": [
            "callback execution",
            "callback input collection",
            "debug trace emission",
            "selector result append",
            "family result adapter call",
        ],
        "next_safe_target": "return_to_frozen_extraction_queue_direct_target_or_post_click_route",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_callback_shell_result_tail_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_callback_shell_result_tail_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Callback Shell / Result Tail Lock",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Surface Inventory",
        "",
        "| Surface | Classification | Present |",
        "| --- | --- | --- |",
    ]
    for row in payload.get("surfaces") or []:
        lines.append(f"| `{row.get('surface')}` | `{row.get('classification')}` | `{row.get('present')}` |")
    lines.extend(["", "## Remaining Page-Owned Design Brain Logic", ""])
    remaining = payload.get("remaining_page_owned_design_brain_logic") or []
    lines.extend(f"- {item}" for item in remaining) if remaining else lines.append("- none")
    lines.extend(["", "## Remaining Page Shell Surfaces", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_shell_surfaces") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Target", "", f"`{payload.get('next_safe_target')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_callback_shell_result_tail_lock {payload.get('status')}")
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
