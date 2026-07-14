"""Verify the global Design Brain minimum longitudinal bar rule.

This is a contract guard, not a renderer test. It proves that Design Brain
candidate filtering and the remaining page/shared apply bridge reject any
candidate that leaves fewer than two longitudinal bars on either face.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (  # noqa: E402
    filter_auto_design_candidates_by_row_layout,
    resolve_auto_design_candidate_row_layout_validity,
    resolve_minimum_longitudinal_bar_rule,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _base_state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "b": 300.0,
        "bw": 300.0,
        "D": 450.0,
        "cover_side": 40.0,
        "bot_row_count": 1,
        "bot_row_1_bars": 2,
        "bot1_count": 2,
        "bot_row_1_dia": 16,
        "db_bot_1": 16,
        "bot_row_2_bars": 0,
        "bot2_count": 0,
        "top_row_count": 1,
        "top_row_1_bars": 2,
        "top1_count": 2,
        "top_row_1_dia": 10,
        "db_top_1": 10,
        "top_row_2_bars": 0,
        "top2_count": 0,
    }
    state.update(overrides)
    return state


def _rule_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for name, state, updates, expected_valid in (
        ("valid_two_top_two_bottom", _base_state(), {}, True),
        ("reject_current_one_bottom_bar", _base_state(bot_row_1_bars=1, bot1_count=1), {}, False),
        ("reject_current_one_top_bar", _base_state(top_row_1_bars=1, top1_count=1), {}, False),
        ("reject_update_to_one_bottom_bar", _base_state(), {"bot_row_1_bars": 1, "bot1_count": 1}, False),
        ("reject_update_to_one_top_bar", _base_state(), {"top_row_1_bars": 1, "top1_count": 1}, False),
    ):
        rule = resolve_minimum_longitudinal_bar_rule(state, updates)
        cases.append(
            {
                "name": name,
                "expected_valid": expected_valid,
                "actual_valid": bool(rule.get("valid")),
                "violations": list(rule.get("violations") or []),
                "passes": bool(rule.get("valid")) is expected_valid,
            }
        )
    return cases


def _row_layout_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for name, kwargs, expected_valid in (
        (
            "row_layout_valid_two_top_two_bottom",
            {"bot1_count": 2, "bot2_count": 0, "top1_count": 2, "top2_count": 0},
            True,
        ),
        (
            "row_layout_reject_one_bottom_bar",
            {"bot1_count": 1, "bot2_count": 0, "top1_count": 2, "top2_count": 0},
            False,
        ),
        (
            "row_layout_reject_one_top_bar",
            {"bot1_count": 2, "bot2_count": 0, "top1_count": 1, "top2_count": 0},
            False,
        ),
    ):
        result = resolve_auto_design_candidate_row_layout_validity(
            beam_width=300.0,
            cover=40.0,
            db_bot_1=16.0,
            db_bot_2=16.0,
            db_top_1=10.0,
            db_top_2=10.0,
            **kwargs,
        )
        cases.append(
            {
                "name": name,
                "expected_valid": expected_valid,
                "actual_valid": bool(result.get("valid")),
                "minimum_bar_rule": dict(result.get("minimum_bar_rule") or {}),
                "passes": bool(result.get("valid")) is expected_valid,
            }
        )
    return cases


def _filter_case() -> dict[str, Any]:
    candidates = [
        {"label": "valid", "state": _base_state()},
        {"label": "invalid_one_bottom", "state": _base_state(bot_row_1_bars=1, bot1_count=1)},
        {"label": "invalid_one_top", "state": _base_state(top_row_1_bars=1, top1_count=1)},
    ]
    result = filter_auto_design_candidates_by_row_layout(candidates)
    kept_labels = [str(row.get("label") or "") for row in result.get("filtered_candidates") or []]
    rejected_labels = [str(row.get("label") or "") for row in result.get("rejected_candidates") or []]
    return {
        "name": "auto_design_filter_rejects_one_bar_faces",
        "kept_labels": kept_labels,
        "rejected_labels": rejected_labels,
        "passes": kept_labels == ["valid"] and rejected_labels == ["invalid_one_bottom", "invalid_one_top"],
    }


def _source_boundary_checks() -> dict[str, Any]:
    candidate_source = (ROOT / "design_brain" / "candidate_evaluation.py").read_text(encoding="utf-8", errors="replace")
    bending_fail_source = (ROOT / "design_brain" / "families" / "bending_fail.py").read_text(encoding="utf-8", errors="replace")
    inputs_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="replace")
    widget_source = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8", errors="replace")
    forbidden_fragments = {
        "candidate_probe_cleanup_counts_to_one": "range(max(1, int(count) - 1), 0, -1)" in candidate_source,
        "page_bending_count_cleanup_counts_to_one": "for trial_count in range(max(0, current_count - 1), 0, -1)" in inputs_source,
        "page_zero_cleanup_clamps_primary_bottom_to_one": 'row1_bars = max(1, _int_from_state(base, "bot_row_1_bars"' in inputs_source,
        "bending_fail_contract_runtime_clamps_primary_bottom_to_one": 'base_count = max(1, _as_int(base.get("bot_row_1_bars")' in bending_fail_source,
    }
    widget_filters_one = "valid_count_options" in widget_source and "if int(option) != 1" in widget_source
    return {
        "forbidden_fragments": forbidden_fragments,
        "candidate_probe_uses_two_bar_floor": "minimum_bottom_bars = 2" in candidate_source,
        "bending_fail_runtime_uses_two_bar_floor": 'base_count = max(2, _as_int(base.get("bot_row_1_bars")' in bending_fail_source,
        "page_bridge_uses_two_bar_floor": 'row1_bars = max(2, _int_from_state(base, "bot_row_1_bars"' in inputs_source,
        "widget_filters_one_bar_options": bool(widget_filters_one),
        "passes": not any(forbidden_fragments.values()) and bool(widget_filters_one),
    }


def build_snapshot() -> dict[str, Any]:
    rule_cases = _rule_cases()
    row_layout_cases = _row_layout_cases()
    filter_case = _filter_case()
    source_boundary = _source_boundary_checks()
    failures: list[str] = []
    for case in rule_cases + row_layout_cases + [filter_case]:
        if not bool(case.get("passes")):
            failures.append(str(case.get("name") or "unnamed_case"))
    if not bool(source_boundary.get("passes")):
        failures.append("source_boundary_still_allows_one_bar_floor")
    return {
        "schema": "design_brain_minimum_longitudinal_bars_family_rule.v1",
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
        "rule": "top and bottom longitudinal faces must have at least two bars; no family candidate may publish/apply one bar",
        "owner": "design_brain.candidate_evaluation.resolve_minimum_longitudinal_bar_rule",
        "rule_cases": rule_cases,
        "row_layout_cases": row_layout_cases,
        "filter_case": filter_case,
        "source_boundary": source_boundary,
    }


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "-")
    artifact = ARTIFACT_DIR / f"design_brain_minimum_longitudinal_bars_family_rule_{timestamp}.json"
    report = AUDIT_DIR / f"design_brain_minimum_longitudinal_bars_family_rule_{timestamp}.md"
    artifact.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report.write_text(
        "\n".join(
            [
                "# Design Brain Minimum Longitudinal Bars Family Rule",
                "",
                f"Result: **{snapshot['result']}**",
                "",
                "Rule: top and bottom longitudinal faces must not publish/apply a one-bar layout.",
                "",
                "## Failures",
                *(f"- {failure}" for failure in snapshot.get("failures") or ["None"]),
                "",
                "## Source Boundary",
                f"- Owner: `{snapshot['owner']}`",
                f"- Forbidden one-bar fragments present: `{any((snapshot.get('source_boundary') or {}).get('forbidden_fragments', {}).values())}`",
                f"- Widget filters one-bar options: `{(snapshot.get('source_boundary') or {}).get('widget_filters_one_bar_options')}`",
            ]
        ),
        encoding="utf-8",
    )
    return artifact, report


def main() -> int:
    snapshot = build_snapshot()
    artifact, report = _write_artifacts(snapshot)
    print(f"design_brain_minimum_longitudinal_bars_family_rule {snapshot['result']}")
    print(f"artifact: {artifact}")
    print(f"report: {report}")
    return 0 if snapshot["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
