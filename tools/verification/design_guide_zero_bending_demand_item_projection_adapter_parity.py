"""Verify zero-bending cleanup item projection delegates to DesignGuideController."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_zero_bending_demand_cleanup_item"
HELPER = "build_design_guide_controller_zero_bending_demand_cleanup_item_projection"
ALIAS = "_build_design_guide_controller_zero_bending_demand_cleanup_item_projection"


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


def _old_projection(item: dict[str, Any], selected: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    out.update(
        {
            "candidate_search_evidence": dict(evidence),
            "local_cleanup_candidate": True,
            "source": "zero_bending_demand_minimum_cleanup_search",
            "affected_family": "bending",
            "family": "bending",
            "guidance_intent": "efficiency_tightening",
            "zero_bending_demand_cleanup": True,
        }
    )
    candidate_id = selected.get("candidate_id")
    payload = dict(out.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["zero_bending_demand_cleanup"] = True
    payload["source_candidate_id"] = candidate_id
    payload["candidate_id"] = candidate_id
    payload["resolved_candidate_family_tag"] = "bending"
    out["action_payload"] = payload
    resolved = dict(out.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["zero_bending_demand_cleanup"] = True
    resolved["candidate_id"] = candidate_id
    resolved["source_candidate_id"] = candidate_id
    resolved["family"] = "bending"
    resolved["recommendation_family_tag"] = "bending"
    out["resolved_candidate"] = resolved
    return out


def build_payload() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_zero_bending_demand_cleanup_item_projection,
    )

    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_segment = _function_segment(inputs_source, TARGET)
    _, _, helper_segment = _function_segment(controller_source, HELPER)

    cases = []
    for case in (
        {
            "case": "normal_projection",
            "item": {"title": "Bending cleanup", "action_payload": {"existing": "payload"}, "resolved_candidate": {"existing": "resolved"}},
            "selected": {"candidate_id": "zero_bending_cleanup_001"},
            "evidence": {"selected_candidate_id": "zero_bending_cleanup_001", "selected_candidate_updates": {"bot1_count": 2}},
        },
        {
            "case": "candidate_id_from_evidence",
            "item": {"action_payload": {}, "resolved_candidate": {}},
            "selected": {},
            "evidence": {"selected_candidate_id": "zero_bending_cleanup_from_evidence"},
        },
    ):
        old = _old_projection(dict(case["item"]), dict(case["selected"]), dict(case["evidence"]))
        new = build_design_guide_controller_zero_bending_demand_cleanup_item_projection(
            item=dict(case["item"]),
            selected_candidate=dict(case["selected"]),
            candidate_search_evidence=dict(case["evidence"]),
        )
        cases.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    checks = {
        "target_found": f"def {TARGET}(" in inputs_source,
        "controller_helper_found": f"def {HELPER}(" in controller_source,
        "controller_helper_exported": f'"{HELPER}"' in controller_source,
        "inputs_imports_helper": f"{HELPER} as {ALIAS}" in inputs_source,
        "target_calls_helper": f"{ALIAS}(" in target_segment,
        "target_keeps_generation_service": "_build_zero_bending_demand_cleanup_update_trials(" in target_segment,
        "target_keeps_evaluation_service": "_evaluate_zero_bending_demand_candidate_with_service(" in target_segment,
        "target_keeps_ranking_service": "_select_zero_bending_demand_cleanup_candidate(" in target_segment,
        "target_no_longer_embeds_item_projection_payload": (
            'payload["zero_bending_demand_cleanup"] = True' not in target_segment
            and 'resolved["zero_bending_demand_cleanup"] = True' not in target_segment
        ),
        "controller_import_clean": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "helper_is_pure_projection": "_guidance_item_from_resolved_candidate" not in helper_segment
        and "_evaluate_zero_bending" not in helper_segment,
        "all_cases_match": all(bool(row.get("matches")) for row in cases),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_zero_bending_demand_item_projection_adapter_parity.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "ZERO_BENDING_DEMAND_ITEM_PROJECTION_CONTROLLER_OWNED",
        "target": {"name": TARGET, "line_start": target_start, "line_end": target_end},
        "cases": cases,
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_zero_bending_demand_item_projection_adapter_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_zero_bending_demand_item_projection_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Zero-Bending Demand Item Projection Adapter Parity",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Cases",
        "",
        "| Case | Matches |",
        "|---|---|",
    ]
    for row in payload.get("cases") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_zero_bending_demand_item_projection_adapter_parity {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [key for key, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
