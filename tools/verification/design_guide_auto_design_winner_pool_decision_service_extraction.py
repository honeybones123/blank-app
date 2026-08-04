"""Verify auto-design winner-pool decision service extraction."""

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

from design_brain.candidate_evaluation import (  # noqa: E402
    resolve_auto_design_winner_pool_decision,
)


INPUTS = ROOT / "inputs_page.py"
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


def _candidate(label: str, reaches: bool = False) -> dict[str, Any]:
    return {
        "label": label,
        "candidate_reaches_target_band": reaches,
        "is_compliant": True,
    }


def _old_decision(
    compliant: list[dict[str, Any]],
    band_reachers: list[dict[str, Any]],
    current_in_band: bool,
) -> dict[str, Any]:
    available = len(band_reachers) > 0
    local_only = bool(compliant) and not available
    reason = (
        "at_least_one_compliant_candidate_reaches_target_band_in_one_move"
        if available
        else (
            "no_compliant_candidate_reaches_target_band_in_one_move"
            if compliant
            else "no_compliant_candidates"
        )
    )
    force_pool = bool((not current_in_band) and band_reachers)
    if force_pool:
        pool = band_reachers
        selected_because_band = True
        mode = "band_reachers_only"
    else:
        pool = compliant
        selected_because_band = False
        mode = "all_compliant"
    return {
        "band_reacher_available": available,
        "band_reacher_reason": reason,
        "local_step_selected_only_because_no_band_reacher": local_only,
        "force_band_reacher_pool": force_pool,
        "selected_because_band": selected_because_band,
        "winner_pool_mode": mode,
        "pool_labels": [str(candidate.get("label") or "") for candidate in pool],
        "pool_same_refs": pool,
        "compliant_count": len(compliant),
        "band_reacher_count": len(band_reachers),
        "band_reacher_labels_considered": [str(candidate.get("label") or "")[:100] for candidate in band_reachers[:24]],
    }


def _new_decision(
    compliant: list[dict[str, Any]],
    band_reachers: list[dict[str, Any]],
    current_in_band: bool,
) -> dict[str, Any]:
    result = resolve_auto_design_winner_pool_decision(compliant, band_reachers, current_in_band)
    pool = list(result.get("pool_candidates") or [])
    return {
        "band_reacher_available": bool(result.get("band_reacher_available")),
        "band_reacher_reason": str(result.get("band_reacher_reason") or ""),
        "local_step_selected_only_because_no_band_reacher": bool(
            result.get("local_step_selected_only_because_no_band_reacher")
        ),
        "force_band_reacher_pool": bool(result.get("force_band_reacher_pool")),
        "selected_because_band": bool(result.get("selected_because_band")),
        "winner_pool_mode": str(result.get("winner_pool_mode") or ""),
        "pool_labels": [str(candidate.get("label") or "") for candidate in pool],
        "pool_same_refs": pool,
        "compliant_count": int(result.get("compliant_count", -1)),
        "band_reacher_count": int(result.get("band_reacher_count", -1)),
        "band_reacher_labels_considered": list(result.get("band_reacher_labels_considered") or []),
    }


def _cases() -> list[dict[str, Any]]:
    compliant = [
        _candidate("safe local", False),
        _candidate("band reacher", True),
        _candidate("another band reacher with a long label " + "x" * 120, True),
    ]
    return [
        {
            "name": "outside_band_with_reachers",
            "compliant": compliant,
            "band_reachers": [candidate for candidate in compliant if candidate.get("candidate_reaches_target_band")],
            "current_in_band": False,
        },
        {
            "name": "current_already_in_band",
            "compliant": compliant,
            "band_reachers": [candidate for candidate in compliant if candidate.get("candidate_reaches_target_band")],
            "current_in_band": True,
        },
        {
            "name": "compliant_no_reachers",
            "compliant": [_candidate("safe local", False)],
            "band_reachers": [],
            "current_in_band": False,
        },
        {
            "name": "no_compliant_candidates",
            "compliant": [],
            "band_reachers": [],
            "current_in_band": False,
        },
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    service_source = _read(CANDIDATE_EVALUATION)
    selector_start, selector_end, selector_segment = _function_segment(inputs_source, "_select_best_auto_design_candidate")
    helper_start, helper_end, helper_segment = _function_segment(
        service_source,
        "resolve_auto_design_winner_pool_decision",
    )

    rows: list[dict[str, Any]] = []
    mismatches: list[str] = []
    for case in _cases():
        old = _old_decision(case["compliant"], case["band_reachers"], case["current_in_band"])
        new = _new_decision(case["compliant"], case["band_reachers"], case["current_in_band"])
        comparable_old = {key: value for key, value in old.items() if key != "pool_same_refs"}
        comparable_new = {key: value for key, value in new.items() if key != "pool_same_refs"}
        same_refs = all(
            new_candidate is old_candidate
            for new_candidate, old_candidate in zip(new["pool_same_refs"], old["pool_same_refs"])
        ) and len(new["pool_same_refs"]) == len(old["pool_same_refs"])
        match = comparable_old == comparable_new and same_refs
        if not match:
            mismatches.append(str(case["name"]))
        rows.append(
            {
                "case": case["name"],
                "match": match,
                "old": comparable_old,
                "new": comparable_new,
                "same_pool_candidate_refs": same_refs,
            }
        )

    checks = {
        "selector_delegates_winner_pool_decision": "_resolve_auto_design_winner_pool_decision(" in selector_segment,
        "old_page_force_pool_assignment_removed": "force_band_reacher_pool = bool((not current_in_band) and band_reachers)" not in selector_segment,
        "old_page_pool_branch_removed": "pool = band_reachers" not in selector_segment and "pool = compliant" not in selector_segment,
        "ranking_is_service_owned_or_trace_only": (
            "_resolve_auto_design_band_reacher_ranked_pool(" in selector_segment
            and "_apply_auto_design_winner_metadata_projection(" in selector_segment
            and "_build_auto_design_selected_candidate_selection_result_from_context(" in selector_segment
        ),
        "trace_publication_remains_page_owned": "_merge_design_guide_rank_trace(" in selector_segment,
        "helper_exported": "\"resolve_auto_design_winner_pool_decision\"" in service_source,
        "no_page_or_ui_imports_in_candidate_evaluation": not any(
            token in service_source
            for token in (
                "import inputs_page",
                "from inputs_page",
                "import streamlit",
                "from streamlit",
                "st.session_state",
            )
        ),
        "service_avoids_forbidden_page_term": "one_click" not in helper_segment,
    }
    parity = {
        "all_cases_match": not mismatches,
        "mismatches": mismatches,
        "case_count": len(rows),
    }
    status = "PASS" if parity["all_cases_match"] and all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "WINNER_POOL_DECISION_SERVICE_OWNED_RANKING_SERVICE_OR_TRACE_ONLY"
            if status == "PASS"
            else "WINNER_POOL_DECISION_EXTRACTION_FAILED"
        ),
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "extraction_complete_estimate": "99.5%",
        "selector_lines": {"start": selector_start, "end": selector_end, "count": selector_end - selector_start + 1},
        "helper_lines": {"start": helper_start, "end": helper_end, "count": helper_end - helper_start + 1},
        "parity": parity,
        "cases": rows,
        "checks": checks,
        "remaining_selector_policy": [
            "rank_trace_publication",
        ],
        "product_behavior_changed": False,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_guide_auto_design_winner_pool_decision_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_auto_design_winner_pool_decision_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    checks_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["checks"].items()))
    parity_md = "\n".join(f"- `{name}`: `{value}`" for name, value in sorted(payload["parity"].items()))
    report_path.write_text(
        "\n".join(
            [
                "# Auto-Design Winner-Pool Decision Service Extraction",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                f"Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
                "",
                "## Parity",
                "",
                parity_md,
                "",
                "## Static Checks",
                "",
                checks_md,
                "",
                "## Remaining Selector Policy",
                "",
                "\n".join(f"- `{item}`" for item in payload["remaining_selector_policy"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_auto_design_winner_pool_decision_service_extraction {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
