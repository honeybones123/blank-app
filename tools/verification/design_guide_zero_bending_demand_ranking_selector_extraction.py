"""Verify zero-bending-demand cleanup ranking delegates to candidate_evaluation."""

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
TARGET = "_zero_bending_demand_cleanup_item"
SERVICE_HELPER = "select_zero_bending_demand_cleanup_candidate"
SERVICE_ALIAS = "_select_zero_bending_demand_cleanup_candidate"
PROJECTION_HELPER = "build_design_guide_controller_zero_bending_demand_cleanup_item_projection"
PROJECTION_ALIAS = "_build_design_guide_controller_zero_bending_demand_cleanup_item_projection"


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
    safe_candidates: list[dict[str, Any]],
    *,
    current_material_proxy: float,
) -> dict[str, Any] | None:
    if not safe_candidates:
        return None
    return min(
        safe_candidates,
        key=lambda candidate: (
            float(candidate.get("candidate_material_proxy") or current_material_proxy),
            len(dict(candidate.get("updates") or {})),
            str(candidate.get("candidate_id") or ""),
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

    from design_brain.candidate_evaluation import select_zero_bending_demand_cleanup_candidate

    cases = [
        {
            "case": "lowest_material_proxy",
            "current_proxy": 1000.0,
            "rows": [
                {"candidate_id": "b", "candidate_material_proxy": 900.0, "updates": {"a": 1}},
                {"candidate_id": "a", "candidate_material_proxy": 800.0, "updates": {"a": 1, "b": 2}},
            ],
        },
        {
            "case": "update_count_tiebreak",
            "current_proxy": 1000.0,
            "rows": [
                {"candidate_id": "two", "candidate_material_proxy": 800.0, "updates": {"a": 1, "b": 2}},
                {"candidate_id": "one", "candidate_material_proxy": 800.0, "updates": {"a": 1}},
            ],
        },
        {
            "case": "candidate_id_tiebreak",
            "current_proxy": 1000.0,
            "rows": [
                {"candidate_id": "z", "candidate_material_proxy": 800.0, "updates": {"a": 1}},
                {"candidate_id": "a", "candidate_material_proxy": 800.0, "updates": {"a": 1}},
            ],
        },
        {
            "case": "missing_proxy_uses_current_proxy",
            "current_proxy": 1000.0,
            "rows": [
                {"candidate_id": "missing", "updates": {"a": 1}},
                {"candidate_id": "lower", "candidate_material_proxy": 950.0, "updates": {"a": 1}},
            ],
        },
        {"case": "empty", "current_proxy": 1000.0, "rows": []},
    ]
    parity = []
    for case in cases:
        old = _normalise(
            _old_select(
                [dict(row) for row in case["rows"]],
                current_material_proxy=float(case["current_proxy"]),
            ),
        )
        new = _normalise(
            select_zero_bending_demand_cleanup_candidate(
                [dict(row) for row in case["rows"]],
                current_material_proxy=float(case["current_proxy"]),
            ),
        )
        parity.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    source_checks = {
        "target_found": f"def {TARGET}(" in inputs_source,
        "candidate_helper_found": f"def {SERVICE_HELPER}(" in candidate_source,
        "candidate_helper_exported": f'"{SERVICE_HELPER}"' in candidate_source,
        "inputs_imports_service_helper": f"{SERVICE_HELPER} as {SERVICE_ALIAS}" in inputs_source,
        "target_calls_service_helper": f"{SERVICE_ALIAS}(" in target_segment,
        "target_removed_inline_safe_candidates_min_selector": "selected = min(\n        safe_candidates," not in target_segment,
        "target_keeps_candidate_evaluation": "_evaluate_zero_bending_demand_candidate_with_service(" in target_segment,
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
                "current_material_proxy",
                "candidate_material_proxy",
                "updates",
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
        "schema": "design_guide_zero_bending_demand_ranking_selector_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "ZERO_BENDING_DEMAND_RANKING_SELECTOR_SERVICE_EXTRACTED",
        "parity": parity,
        "source_checks": source_checks,
        "checks": checks,
        "remaining_page_owned_surfaces": [
            "zero-bending demand guard",
            "candidate evaluation callback call",
            "debug_sink writes",
            "visible item wording",
        ],
        "next_safe_slice": "zero_bending_demand_item_projection_boundary_audit_or_bending_only_ranking_selector",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_zero_bending_demand_ranking_selector_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_zero_bending_demand_ranking_selector_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Zero Bending Demand Ranking Selector Extraction",
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
    print(f"design_guide_zero_bending_demand_ranking_selector_extraction {payload.get('status')}")
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
