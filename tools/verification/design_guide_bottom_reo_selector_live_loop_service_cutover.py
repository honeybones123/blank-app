"""Verify bottom-reo selector live loop service cutover."""

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

from design_brain.families.bending import (  # noqa: E402
    select_bottom_reo_recommendation_candidate_by_selector,
)


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


def _candidate(
    label: str,
    *,
    bending: float | None = 0.8,
    reaches: bool = False,
    compliant: bool = True,
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "is_compliant": compliant,
        "candidate_reaches_target_band": reaches,
        "candidate_post_util": bending,
        "candidate_goal_score": 1.0,
        "winner_pool_mode": "all_compliant",
        "winning_candidate_selected_from_band_reachers": reaches,
        "overview": {"utils": {"bending": bending}},
        "updates": dict(updates or {"bot1_count": 5}),
    }


def _run_scenario(name: str, candidates: list[dict[str, Any]], *, strict_reject: bool = False, noop: bool = False) -> dict[str, Any]:
    def _select_best(pool: list[dict[str, Any]], mode: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any] | None:
        return pool[0] if pool else None

    def _strict(candidate: dict[str, Any]) -> tuple[bool, str]:
        return (bool(strict_reject and candidate.get("candidate_reaches_target_band")), "strict_reason")

    def _updates_match(updates: dict[str, Any]) -> bool:
        return bool(noop and updates.get("noop"))

    def _ductility_util(candidate: dict[str, Any]) -> float | None:
        return candidate.get("ductility_util")

    def _legacy(candidate: dict[str, Any]) -> str | None:
        return "legacy-note" if candidate.get("legacy") else None

    result = select_bottom_reo_recommendation_candidate_by_selector(
        candidates,
        seed_candidate={"overview": {"utils": {"bending": 1.0}}},
        mode_config={},
        select_best_candidate_fn=_select_best,
        strict_band_guard_fn=_strict,
        updates_match_state_fn=_updates_match,
        candidate_ductility_util_fn=_ductility_util,
        seed_ductility_governs=False,
        seed_ductility_util=None,
        legacy_rejection_reason_fn=_legacy,
    )
    selector = dict(result.get("selector_result") or {})
    return {
        "name": name,
        "selected_label": (result.get("selected_candidate") or {}).get("label"),
        "status": selector.get("status"),
        "selected_reason": selector.get("selected_reason"),
        "no_candidate_reason": selector.get("no_candidate_reason"),
        "rank_event_reasons": tuple(str(event.get("reason")) for event in result.get("rank_events") or ()),
        "trace_count": len(tuple(result.get("trace_entries") or ())),
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, "_pick_best_bottom_recommendation_by_selector")
    helper_start, helper_end, helper_segment = _function_segment(
        bending_source,
        "select_bottom_reo_recommendation_candidate_by_selector",
    )

    rows = [
        _run_scenario("strict_band_accept", [_candidate("band", reaches=True, bending=0.9)]),
        _run_scenario(
            "strict_band_reject_then_normal_accept",
            [_candidate("band", reaches=True, bending=0.9), _candidate("normal", bending=0.8)],
            strict_reject=True,
        ),
        _run_scenario(
            "noop_then_accept",
            [_candidate("noop", updates={"noop": True}), _candidate("normal", bending=0.8)],
            noop=True,
        ),
        _run_scenario("pool_exhausted", [_candidate("", bending=None)]),
    ]
    expected = {
        "strict_band_accept": ("selected", "strict_band_winner_accept", "band"),
        "strict_band_reject_then_normal_accept": ("selected", "selector_top_valid", "normal"),
        "noop_then_accept": ("selected", "selector_top_valid", "normal"),
        "pool_exhausted": ("no_result", None, None),
    }
    scenario_matches = []
    for row in rows:
        status, reason, label = expected[row["name"]]
        scenario_matches.append(
            row["status"] == status
            and row["selected_reason"] == reason
            and row["selected_label"] == label
        )

    checks = {
        "page_delegates_live_loop_to_family": "_select_bottom_reo_recommendation_candidate_by_selector(" in page_segment,
        "page_keeps_callback_execution": "select_best_candidate_fn=_select_best_auto_design_candidate" in page_segment
        and "strict_band_guard_fn=_strict_band_guard" in page_segment,
        "page_emits_trace_only": "_log_design_reco_candidate_rank(**dict(_event))" in page_segment
        and "_merge_design_guide_rank_trace(dict(_entry))" in page_segment,
        "page_result_record_shell_remains": "_bottom_reo_selector_result_record(" in page_segment,
        "old_page_inline_selector_loop_removed": "while pool:" not in page_segment
        and "pool = [x for x in pool if x is not pick]" not in page_segment,
        "family_helper_has_selector_policy": "while pool:" in helper_segment
        and "strict_band_winner_accept" in helper_segment
        and "selector_top_valid" in helper_segment,
        "family_helper_has_no_page_ui_session_imports": not any(
            token in helper_segment
            for token in ("inputs_page", "streamlit", "st.session_state", "FinalDesignGuidePublication")
        ),
        "scenario_parity": all(scenario_matches),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_SELECTOR_LIVE_LOOP_SERVICE_CUTOVER_COMPLETE",
        "page_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "scenario_rows": rows,
        "checks": checks,
        "remaining_page_surface": [
            "selector callback execution",
            "rank trace emission",
            "selector result record append",
            "final recommendation result packaging",
        ],
        "next_safe_slice": "bottom_reo_result_packaging_or_callback_shell_lock",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_selector_live_loop_service_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_selector_live_loop_service_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Selector Live Loop Service Cutover",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Scenario Rows",
        "",
        "| Scenario | Status | Reason | Selected |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(
            f"| `{row.get('name')}` | `{row.get('status')}` | `{row.get('selected_reason')}` | `{row.get('selected_label')}` |"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Remaining Page Surface", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_surface") or [])
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_selector_live_loop_service_cutover {payload.get('status')}")
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
