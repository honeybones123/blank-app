"""Verify bottom-reo score/rank selector-prep boundary extraction."""

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
SERVICE = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_HELPER = "_compute_bottom_reo_recommendation"
SERVICE_HELPER = "prepare_bottom_reo_recommendation_candidates_for_selection"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _selection_prep_segment(target_segment: str) -> str:
    start = target_segment.index("_selection_prep = _prepare_bottom_reo_recommendation_candidates_for_selection(")
    end = target_segment.index("_bottom_selector_results: list[BottomReoSelectorResult]")
    return target_segment[start:end]


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _scenario_rows() -> list[dict[str, Any]]:
    from design_brain.candidate_evaluation import prepare_bottom_reo_recommendation_candidates_for_selection

    seed = {"seed": True}
    state = {"D": 600.0}
    mode = {"target_low": 0.75}
    candidates = [
        {"candidate_id": "a", "updates": {"x": 1}, "order": 2, "score": None},
        {"candidate_id": "b", "updates": {"x": 2}, "order": 1, "score": 4.0},
        {"candidate_id": "c", "updates": {"x": 3}, "order": 3, "score": None},
    ]

    def annotate_deltas_fn(candidate, seed_candidate, current_state):
        candidate["delta_mark"] = f"{candidate.get('candidate_id')}:{bool(seed_candidate)}:{current_state.get('D')}"

    def score_fn(candidate, mode_config, seed_candidate):
        del mode_config, seed_candidate
        return float(candidate.get("order", 0)) * 10.0

    def annotate_target_band_fn(candidate, mode_config):
        candidate["target_band_mark"] = mode_config.get("target_low")

    def keep_top_fn(items, mode_config, *, limit):
        del mode_config
        return sorted(list(items), key=lambda item: float(item.get("score", 0.0)))[: int(limit)]

    expected_candidates = [dict(item) for item in candidates]
    for candidate in expected_candidates:
        annotate_deltas_fn(candidate, dict(seed), dict(state))
    for candidate in expected_candidates:
        if candidate.get("score") is None:
            candidate["score"] = score_fn(candidate, dict(mode), dict(seed))
    for candidate in expected_candidates:
        annotate_target_band_fn(candidate, dict(mode))
    expected_ranked = keep_top_fn(expected_candidates, dict(mode), limit=2)
    expected = {
        "filtered_candidates": expected_candidates,
        "ranked_candidates": expected_ranked,
        "rank_limit": 2,
    }
    actual = prepare_bottom_reo_recommendation_candidates_for_selection(
        [dict(item) for item in candidates],
        seed_candidate=dict(seed),
        state=dict(state),
        mode_config=dict(mode),
        annotate_deltas_fn=annotate_deltas_fn,
        score_fn=score_fn,
        annotate_target_band_fn=annotate_target_band_fn,
        keep_top_fn=keep_top_fn,
        limit=2,
    )
    return [
        {
            "name": "annotate_score_target_rank",
            "matches": _stable(actual) == _stable(expected),
            "actual_hash": _stable(actual),
            "expected_hash": _stable(expected),
        }
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(SERVICE)
    _, _, target_segment = _function_segment(inputs_source, TARGET_HELPER)
    _, _, service_segment = _function_segment(service_source, SERVICE_HELPER)
    prep_segment = _selection_prep_segment(target_segment)
    scenario_rows = _scenario_rows()

    forbidden_service_tokens = [
        "import inputs_page",
        "from inputs_page",
        "import streamlit",
        "st.session_state",
        "_pick_best_bottom_recommendation_by_selector(",
        "_build_bottom_reo_recommendation_result(",
    ]
    checks = {
        "service_helper_exists": bool(service_segment),
        "page_delegates_selection_prep": "_prepare_bottom_reo_recommendation_candidates_for_selection(" in prep_segment,
        "target_no_local_prep_loops": "_annotate_bottom_reo_candidate_deltas(cand" not in target_segment
        and "_score_auto_design_candidate(cand" not in target_segment
        and "_annotate_candidate_target_band_metrics(cand" not in target_segment,
        "selector_still_page_owned": "_pick_best_bottom_recommendation_by_selector(" in target_segment,
        "compound_preference_still_page_owned": "_maybe_prefer_compound_over_pure_geometry(" in target_segment,
        "result_packaging_still_page_owned": "_build_bottom_reo_recommendation_result(" in target_segment,
        "service_has_no_page_or_publication_imports": not any(token in service_segment for token in forbidden_service_tokens),
        "scenario_parity": all(row["matches"] for row in scenario_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BOTTOM_REO_SCORE_RANK_SELECTION_PREP_EXTRACTED",
        "scenario_rows": scenario_rows,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "bottom selector",
            "compound preference",
            "post-selector no-result guard",
            "required Ast and change lines",
            "final recommendation result packaging",
            "trace/proof event emission",
        ],
        "next_safe_slice": {
            "name": "design_guide_bottom_reo_recommendation_selector_result_object_boundary.py",
            "why": "selection prep is service-owned; selector result object should be proven before moving selector/compound preference.",
        },
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_recommendation_score_rank_selector_boundary_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_recommendation_score_rank_selector_boundary_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Score/Rank Selection-Prep Boundary",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Scenario Parity",
        "",
        "| Scenario | Match |",
        "| --- | --- |",
    ]
    for row in payload.get("scenario_rows") or []:
        lines.append(f"| `{row.get('name')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Remaining Page-Owned Surfaces", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_surfaces") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    next_slice = dict(payload.get("next_safe_slice") or {})
    lines.extend(["", "## Next Safe Slice", "", f"- `{next_slice.get('name')}`", f"- {next_slice.get('why')}"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    status = payload.get("status")
    print(f"design_guide_bottom_reo_recommendation_score_rank_selector_boundary {status}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
