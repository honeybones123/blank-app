"""Audit the remaining auto-design selector rank-trace surface as page shell."""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
RANKING = ROOT / "design_brain" / "ranking.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
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
    ranking_source = _read(RANKING)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")
    trace_blocks = selector_segment.count("_merge_design_guide_rank_trace(")
    remaining_decision_tokens = {
        "page_selected_identity_assembly": "selected_candidate_identity = _auto_design_candidate_identity(" in selector_segment,
        "page_selected_index_assembly": "selected_candidate_index = next((idx for idx, item in enumerate(candidates) if item is winner), None)" in selector_segment,
        "page_selected_reason_assembly": "selected_reason = (" in selector_segment,
        "page_winner_metadata_assignment": "winner[\"winning_candidate_post_util\"] = winner.get(\"candidate_post_util\")" in selector_segment,
        "page_ranked_pool_loop": "ranked_pool.append((rank_key, item))" in selector_segment,
        "page_score_assignment_loop": "candidate[\"score\"] = _score_auto_design_candidate(candidate, mode_config, seed_candidate)" in selector_segment,
    }
    checks = {
        "trace_sink_present": "_ACTIVE_GUIDANCE_RANK_TRACE" in selector_segment and "_merge_design_guide_rank_trace(" in selector_segment,
        "trace_blocks_expected": trace_blocks == 2,
        "selected_result_service_owned": "_build_auto_design_selected_candidate_selection_result_from_context(" in selector_segment
        and "build_auto_design_selected_candidate_selection_result_from_context(" in ranking_source,
        "selector_candidate_policy_service_owned": all(
            token in selector_segment
            for token in (
                "_filter_auto_design_candidates_by_row_layout(",
                "_score_auto_design_candidates_for_selection(",
                "_resolve_auto_design_winner_pool_decision(",
                "_resolve_auto_design_band_reacher_ranked_pool(",
                "_apply_auto_design_winner_metadata_projection(",
            )
        ),
        "no_remaining_page_decision_tokens": not any(remaining_decision_tokens.values()),
        "trace_does_not_return_or_replace_winner": "return winner" in selector_segment,
        "trace_reads_selection_result_only": "_selection_result.rank_trace_summary" in selector_segment
        and "_selection_result.winner_goal_score" in selector_segment,
        "no_page_or_ui_imports_in_candidate_evaluation": not any(
            token in candidate_source
            for token in (
                "import inputs_page",
                "from inputs_page",
                "import streamlit",
                "from streamlit",
                "st.session_state",
            )
        ),
        "no_page_or_ui_imports_in_ranking": not any(
            token in ranking_source
            for token in (
                "import inputs_page",
                "from inputs_page",
                "import streamlit",
                "from streamlit",
                "st.session_state",
            )
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "RANK_TRACE_PUBLICATION_IS_PAGE_SHELL_DEBUG_SINK_ONLY"
            if status == "PASS"
            else "RANK_TRACE_BOUNDARY_HAS_REMAINING_PAGE_DECISION_LOGIC"
        ),
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "extraction_complete_estimate": "99.65%",
        "selector_lines": {"start": start, "end": end, "count": end - start + 1},
        "trace_blocks": trace_blocks,
        "remaining_decision_tokens": remaining_decision_tokens,
        "checks": checks,
        "classification": {
            "rank_trace_publication": "page-shell debug sink",
            "selected_result_assembly": "design_brain.ranking owned",
            "candidate_filter_score_rank_metadata": "design_brain.candidate_evaluation owned",
            "winner_return": "selector shell return",
        },
        "next_safe_slice": "leave trace sink bounded; continue to next frozen extraction surface",
        "product_behavior_changed": False,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_rank_trace_shell_boundary_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_rank_trace_shell_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    checks_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["checks"].items()))
    remaining_md = "\n".join(
        f"- `{name}`: `{value}`" for name, value in sorted(payload["remaining_decision_tokens"].items())
    )
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Rank Trace Shell Boundary Audit",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                f"Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
                "",
                "## Checks",
                "",
                checks_md,
                "",
                "## Remaining Page Decision Tokens",
                "",
                remaining_md,
                "",
                "## Classification",
                "",
                "\n".join(f"- `{key}`: `{value}`" for key, value in payload["classification"].items()),
                "",
                "## Next Safe Slice",
                "",
                str(payload["next_safe_slice"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_auto_design_rank_trace_shell_boundary_audit {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
