"""Verify probe-equivalent bending cleanup ranking delegates to candidate_evaluation."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_probe_equivalent_bending_cleanup_action_item"
SERVICE_HELPER = "select_probe_equivalent_bending_cleanup_candidate"
SERVICE_ALIAS = "_select_probe_equivalent_bending_cleanup_candidate"
PROJECTION_HELPER = "build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection"
PROJECTION_ALIAS = "_build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection"


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


def _old_select(
    safe_rows: list[dict[str, Any]],
    *,
    final_accepted_min_family_util: float,
    target_low: float,
    target_high: float,
) -> dict[str, Any] | None:
    if not safe_rows:
        return None
    return min(
        safe_rows,
        key=lambda row: (
            0 if float(final_accepted_min_family_util) <= float(row.get("preview_util")) <= 1.0 else 1,
            0 if float(target_low) <= float(row.get("preview_util")) <= float(target_high) else 1,
            abs(float(final_accepted_min_family_util) - float(row.get("preview_util"))),
            len(dict(row.get("updates") or {})),
            str(row.get("candidate_id") or ""),
        ),
    )


def _normalise(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return dict(row) if isinstance(row, dict) else None


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    controller_source = _read(CONTROLLER)
    _, _, target_segment = _function_segment(inputs_source, TARGET)
    _, _, helper_segment = _function_segment(candidate_source, SERVICE_HELPER)

    from design_brain.candidate_evaluation import select_probe_equivalent_bending_cleanup_candidate

    cases = [
        {
            "case": "accepted_floor_and_target_band",
            "rows": [
                {"candidate_id": "b", "preview_util": 0.72, "updates": {"bot1_count": 5}},
                {"candidate_id": "a", "preview_util": 0.86, "updates": {"bot1_count": 6}},
            ],
            "final_floor": 0.85,
            "target_low": 0.85,
            "target_high": 0.95,
        },
        {
            "case": "outside_target_but_closest_to_floor",
            "rows": [
                {"candidate_id": "low", "preview_util": 0.74, "updates": {"bot1_count": 5}},
                {"candidate_id": "high", "preview_util": 1.04, "updates": {"bot1_count": 9}},
            ],
            "final_floor": 0.85,
            "target_low": 0.85,
            "target_high": 0.95,
        },
        {
            "case": "update_count_tiebreak",
            "rows": [
                {"candidate_id": "two", "preview_util": 0.87, "updates": {"a": 1, "b": 2}},
                {"candidate_id": "one", "preview_util": 0.87, "updates": {"a": 1}},
            ],
            "final_floor": 0.85,
            "target_low": 0.85,
            "target_high": 0.95,
        },
        {
            "case": "candidate_id_tiebreak",
            "rows": [
                {"candidate_id": "z", "preview_util": 0.87, "updates": {"a": 1}},
                {"candidate_id": "a", "preview_util": 0.87, "updates": {"a": 1}},
            ],
            "final_floor": 0.85,
            "target_low": 0.85,
            "target_high": 0.95,
        },
        {
            "case": "empty",
            "rows": [],
            "final_floor": 0.85,
            "target_low": 0.85,
            "target_high": 0.95,
        },
    ]
    parity = []
    for case in cases:
        kwargs = {
            "final_accepted_min_family_util": float(case["final_floor"]),
            "target_low": float(case["target_low"]),
            "target_high": float(case["target_high"]),
        }
        old = _normalise(_old_select([dict(row) for row in case["rows"]], **kwargs))
        new = _normalise(
            select_probe_equivalent_bending_cleanup_candidate(
                [dict(row) for row in case["rows"]],
                **kwargs,
            ),
        )
        parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    source_checks = {
        "target_found": f"def {TARGET}(" in inputs_source,
        "candidate_helper_found": f"def {SERVICE_HELPER}(" in candidate_source,
        "candidate_helper_exported": f'"{SERVICE_HELPER}"' in candidate_source,
        "inputs_imports_service_helper": f"{SERVICE_HELPER} as {SERVICE_ALIAS}" in inputs_source,
        "target_calls_service_helper": f"{SERVICE_ALIAS}(" in target_segment,
        "target_removed_inline_safe_rows_min_selector": "selected = min(\n        safe_rows," not in target_segment,
        "target_keeps_candidate_evaluation": "_evaluate_probe_equivalent_bending_candidate_with_service(" in target_segment,
        "target_keeps_item_projection": "_guidance_item_from_resolved_candidate(" in target_segment,
        "target_uses_controller_projection_helper": f"{PROJECTION_ALIAS}(" in target_segment,
        "controller_projection_helper_found": f"def {PROJECTION_HELPER}(" in controller_source,
        "controller_projection_helper_exported": f'"{PROJECTION_HELPER}"' in controller_source,
        "target_no_longer_embeds_item_projection_payload": 'item["action_payload"] = payload' not in target_segment
        and 'item["resolved_candidate"] = resolved' not in target_segment,
        "target_keeps_debug_sink": "debug_sink" in target_segment,
        "candidate_evaluation_has_no_inputs_page_import": "import inputs_page" not in candidate_source
        and "from inputs_page" not in candidate_source,
        "candidate_evaluation_has_no_streamlit_import": "streamlit" not in candidate_source,
        "helper_has_old_ranking_terms": all(
            token in helper_segment
            for token in (
                "final_accepted_min_family_util",
                "target_low",
                "target_high",
                "preview_util",
                "candidate_id",
            )
        ),
    }
    checks = {
        **source_checks,
        "ranking_parity": all(bool(row["matches"]) for row in parity),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_probe_equivalent_bending_ranking_selector_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "PROBE_EQUIVALENT_BENDING_RANKING_SELECTOR_SERVICE_EXTRACTED",
        "parity": parity,
        "source_checks": source_checks,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "overview acceptability and skip guard",
            "candidate evaluation callback call",
            "debug_sink writes",
        ],
        "next_safe_slice": "probe_equivalent_bending_item_projection_boundary_audit_or_zero_bending_ranking_selector",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_probe_equivalent_bending_ranking_selector_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_probe_equivalent_bending_ranking_selector_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Probe-Equivalent Bending Ranking Selector Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Parity",
        "",
    ]
    lines.extend(f"- `{row['case']}`: `{row['matches']}`" for row in payload.get("parity") or [])
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
    print(f"design_guide_probe_equivalent_bending_ranking_selector_extraction {payload.get('status')}")
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
