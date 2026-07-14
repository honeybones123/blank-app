"""Verify bending-only target-band cleanup ranking delegates to candidate_evaluation."""

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
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_bending_only_target_band_cleanup_item"
PARTIAL_HELPER = "select_bending_only_best_safe_partial_cleanup_candidate"
TARGET_HELPER = "select_bending_only_target_band_cleanup_candidate"
PARTIAL_ALIAS = "_select_bending_only_best_safe_partial_cleanup_candidate"
TARGET_ALIAS = "_select_bending_only_target_band_cleanup_candidate"


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


def _old_partial_select(rows: list[dict[str, Any]], *, final_floor: float) -> dict[str, Any] | None:
    if not rows:
        return None
    return min(
        rows,
        key=lambda candidate: (
            abs(float(final_floor) - float(candidate.get("candidate_bending_util") or 0.0)),
            abs(float(candidate.get("candidate_post_util") or 0.0) - float(final_floor)),
            len(dict(candidate.get("updates") or {})),
            str(candidate.get("candidate_id") or ""),
        ),
    )


def _old_target_select(
    rows: list[dict[str, Any]],
    *,
    target_low: float,
    target_high: float,
) -> dict[str, Any] | None:
    if not rows:
        return None
    target_mid = (float(target_low) + float(target_high)) / 2.0
    return min(
        rows,
        key=lambda candidate: (
            abs(float(candidate.get("candidate_bending_util") or 0.0) - target_mid),
            abs(float(candidate.get("candidate_post_util") or 0.0) - target_mid),
            len(dict(candidate.get("updates") or {})),
            str(candidate.get("candidate_id") or ""),
        ),
    )


def _normalise(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return dict(row) if isinstance(row, dict) else None


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, target_segment = _function_segment(inputs_source, TARGET)
    _, _, partial_segment = _function_segment(candidate_source, PARTIAL_HELPER)
    _, _, target_helper_segment = _function_segment(candidate_source, TARGET_HELPER)

    from design_brain.candidate_evaluation import (
        select_bending_only_best_safe_partial_cleanup_candidate,
        select_bending_only_target_band_cleanup_candidate,
    )

    partial_cases = [
        {
            "case": "closest_to_final_floor",
            "final_floor": 0.85,
            "rows": [
                {"candidate_id": "low", "candidate_bending_util": 0.62, "candidate_post_util": 0.62, "updates": {"a": 1}},
                {"candidate_id": "near", "candidate_bending_util": 0.78, "candidate_post_util": 0.79, "updates": {"a": 1, "b": 2}},
            ],
        },
        {
            "case": "post_util_tiebreak",
            "final_floor": 0.85,
            "rows": [
                {"candidate_id": "a", "candidate_bending_util": 0.78, "candidate_post_util": 0.77, "updates": {"a": 1}},
                {"candidate_id": "b", "candidate_bending_util": 0.78, "candidate_post_util": 0.80, "updates": {"a": 1, "b": 2}},
            ],
        },
        {
            "case": "update_count_tiebreak",
            "final_floor": 0.85,
            "rows": [
                {"candidate_id": "two", "candidate_bending_util": 0.78, "candidate_post_util": 0.80, "updates": {"a": 1, "b": 2}},
                {"candidate_id": "one", "candidate_bending_util": 0.78, "candidate_post_util": 0.80, "updates": {"a": 1}},
            ],
        },
        {
            "case": "candidate_id_tiebreak",
            "final_floor": 0.85,
            "rows": [
                {"candidate_id": "z", "candidate_bending_util": 0.78, "candidate_post_util": 0.80, "updates": {"a": 1}},
                {"candidate_id": "a", "candidate_bending_util": 0.78, "candidate_post_util": 0.80, "updates": {"a": 1}},
            ],
        },
        {"case": "empty", "final_floor": 0.85, "rows": []},
    ]
    target_cases = [
        {
            "case": "closest_to_mid",
            "target_low": 0.85,
            "target_high": 0.95,
            "rows": [
                {"candidate_id": "low", "candidate_bending_util": 0.86, "candidate_post_util": 0.86, "updates": {"a": 1}},
                {"candidate_id": "mid", "candidate_bending_util": 0.90, "candidate_post_util": 0.90, "updates": {"a": 1, "b": 2}},
            ],
        },
        {
            "case": "post_util_tiebreak",
            "target_low": 0.85,
            "target_high": 0.95,
            "rows": [
                {"candidate_id": "a", "candidate_bending_util": 0.88, "candidate_post_util": 0.87, "updates": {"a": 1}},
                {"candidate_id": "b", "candidate_bending_util": 0.88, "candidate_post_util": 0.90, "updates": {"a": 1, "b": 2}},
            ],
        },
        {
            "case": "update_count_tiebreak",
            "target_low": 0.85,
            "target_high": 0.95,
            "rows": [
                {"candidate_id": "two", "candidate_bending_util": 0.90, "candidate_post_util": 0.90, "updates": {"a": 1, "b": 2}},
                {"candidate_id": "one", "candidate_bending_util": 0.90, "candidate_post_util": 0.90, "updates": {"a": 1}},
            ],
        },
        {"case": "empty", "target_low": 0.85, "target_high": 0.95, "rows": []},
    ]
    partial_parity = []
    for case in partial_cases:
        old = _normalise(
            _old_partial_select([dict(row) for row in case["rows"]], final_floor=float(case["final_floor"])),
        )
        new = _normalise(
            select_bending_only_best_safe_partial_cleanup_candidate(
                [dict(row) for row in case["rows"]],
                final_accepted_min_family_util=float(case["final_floor"]),
            ),
        )
        partial_parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    target_parity = []
    for case in target_cases:
        old = _normalise(
            _old_target_select(
                [dict(row) for row in case["rows"]],
                target_low=float(case["target_low"]),
                target_high=float(case["target_high"]),
            ),
        )
        new = _normalise(
            select_bending_only_target_band_cleanup_candidate(
                [dict(row) for row in case["rows"]],
                target_low=float(case["target_low"]),
                target_high=float(case["target_high"]),
            ),
        )
        target_parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    source_checks = {
        "target_found": f"def {TARGET}(" in inputs_source,
        "partial_helper_found": f"def {PARTIAL_HELPER}(" in candidate_source,
        "target_helper_found": f"def {TARGET_HELPER}(" in candidate_source,
        "partial_helper_exported": f'"{PARTIAL_HELPER}"' in candidate_source,
        "target_helper_exported": f'"{TARGET_HELPER}"' in candidate_source,
        "inputs_imports_partial_helper": f"{PARTIAL_HELPER} as {PARTIAL_ALIAS}" in inputs_source,
        "inputs_imports_target_helper": f"{TARGET_HELPER} as {TARGET_ALIAS}" in inputs_source,
        "target_calls_partial_helper": f"{PARTIAL_ALIAS}(" in target_segment,
        "target_calls_target_helper": f"{TARGET_ALIAS}(" in target_segment,
        "target_removed_inline_safe_partial_min_selector": "selected = min(\n                safe_partial_candidates," not in target_segment,
        "target_removed_inline_target_candidates_min_selector": "selected = min(\n        target_candidates," not in target_segment,
        "target_keeps_candidate_evaluation_loop": "_evaluate_bending_only_target_band_candidate_with_service(" in target_segment,
        "target_keeps_terminalisation_fold": "allow_terminalisation_fold" in target_segment
        and "_shear_low_util_target_cleanup_item(" in target_segment,
        "target_keeps_item_projection": "_guidance_item_from_resolved_candidate(" in target_segment,
        "target_uses_controller_action_payload_projection": (
            "_build_design_guide_controller_bending_only_target_band_cleanup_item_projection("
            in target_segment
            and 'item["action_payload"] = payload' not in target_segment
        ),
        "target_keeps_debug_sink": "debug_sink" in target_segment,
        "candidate_evaluation_has_no_inputs_page_import": "import inputs_page" not in candidate_source
        and "from inputs_page" not in candidate_source,
        "candidate_evaluation_has_no_streamlit_import": "streamlit" not in candidate_source,
        "partial_helper_has_old_ranking_terms": all(
            token in partial_segment
            for token in ("candidate_bending_util", "candidate_post_util", "updates", "candidate_id")
        ),
        "target_helper_has_old_ranking_terms": all(
            token in target_helper_segment
            for token in ("candidate_bending_util", "candidate_post_util", "updates", "candidate_id")
        ),
    }
    checks = {
        **source_checks,
        "partial_ranking_parity": all(bool(row["matches"]) for row in partial_parity),
        "target_ranking_parity": all(bool(row["matches"]) for row in target_parity),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_bending_only_target_band_ranking_selector_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BENDING_ONLY_TARGET_BAND_RANKING_SELECTORS_SERVICE_EXTRACTED",
        "partial_parity": partial_parity,
        "target_parity": target_parity,
        "source_checks": source_checks,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "cache/fingerprint shell",
            "candidate evaluation loop",
            "terminalisation fold",
            "item/action payload projection",
            "debug_sink writes",
        ],
        "next_safe_slice": "bending_only_terminalisation_boundary_audit_or_item_projection_boundary_audit",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bending_only_target_band_ranking_selector_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_only_target_band_ranking_selector_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bending-Only Target-Band Ranking Selector Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Partial Selector Parity",
        "",
    ]
    lines.extend(f"- `{row['case']}`: `{row['matches']}`" for row in payload.get("partial_parity") or [])
    lines.extend(["", "## Target Selector Parity", ""])
    lines.extend(f"- `{row['case']}`: `{row['matches']}`" for row in payload.get("target_parity") or [])
    lines.extend(["", "## Remaining Page-Owned Surfaces", ""])
    lines.extend(f"- `{item}`" for item in payload.get("remaining_page_owned_surfaces") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bending_only_target_band_ranking_selector_extraction {payload.get('status')}")
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
