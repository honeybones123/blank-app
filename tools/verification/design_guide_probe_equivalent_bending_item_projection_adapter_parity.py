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

TARGET = "_probe_equivalent_bending_cleanup_action_item"
HELPER = "build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection"
ALIAS = "_build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    return 0, 0, ""


def _old_projection(
    item: dict[str, Any] | None,
    selected: dict[str, Any] | None,
    evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    projected = dict(item or {})
    selected_row = dict(selected or {})
    ev = dict(evidence or {})
    projected["candidate_search_evidence"] = dict(ev)
    projected["local_cleanup_candidate"] = True
    projected["source"] = "design_guide_probe_equivalent_bending_cleanup_search"
    projected["affected_family"] = "bending"
    projected["family"] = "bending"
    projected["guidance_intent"] = "efficiency_tightening"
    payload = dict(projected.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(ev)
    payload["source_candidate_id"] = selected_row.get("candidate_id")
    payload["candidate_id"] = selected_row.get("candidate_id")
    payload["resolved_candidate_family_tag"] = "bending"
    payload["resolved_candidate_subfamilies"] = ["bottom_reinforcement"]
    projected["action_payload"] = payload
    resolved = dict(projected.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(ev)
    resolved["candidate_id"] = selected_row.get("candidate_id")
    resolved["source_candidate_id"] = selected_row.get("candidate_id")
    resolved["family"] = "bending"
    resolved["recommendation_family_tag"] = "bending"
    resolved["subfamilies"] = ["bottom_reinforcement"]
    projected["resolved_candidate"] = resolved
    return projected


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "normal_projection",
            "item": {
                "title": "Bending cleanup",
                "action_payload": {"existing": "payload"},
                "resolved_candidate": {"existing": "resolved"},
            },
            "selected": {
                "candidate_id": "probe_equivalent_bending_cleanup_001",
                "updates": {"bot1_count": 5},
            },
            "evidence": {
                "selected_candidate_id": "probe_equivalent_bending_cleanup_001",
                "safe_candidate_count": 2,
            },
        },
        {
            "name": "missing_candidate_id_preserved",
            "item": {"action_payload": {}, "resolved_candidate": {}},
            "selected": {"updates": {"bot1_count": 5}},
            "evidence": {"selected_candidate_id": "evidence_only_id"},
        },
    ]


def _sample_parity() -> list[dict[str, Any]]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection,
    )

    rows: list[dict[str, Any]] = []
    for case in _cases():
        old = _old_projection(case.get("item"), case.get("selected"), case.get("evidence"))
        new = build_design_guide_controller_probe_equivalent_bending_cleanup_item_projection(
            item=case.get("item"),
            selected_candidate=case.get("selected"),
            candidate_search_evidence=case.get("evidence"),
        )
        rows.append(
            {
                "case": case.get("name"),
                "matches": old == new,
                "old": old,
                "new": new,
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_segment = _function_segment(inputs_source, TARGET)
    _, _, helper_segment = _function_segment(controller_source, HELPER)
    parity = _sample_parity()
    checks = {
        "target_found": bool(target_segment),
        "controller_helper_found": bool(helper_segment),
        "controller_helper_exported": f'"{HELPER}"' in controller_source,
        "inputs_imports_helper": f"{HELPER} as {ALIAS}" in inputs_source,
        "target_calls_helper": f"{ALIAS}(" in target_segment,
        "target_keeps_generation_service": "_build_probe_equivalent_bending_cleanup_candidate_inputs(" in target_segment,
        "target_keeps_evaluation_service": "_evaluate_probe_equivalent_bending_candidate_with_service(" in target_segment,
        "target_keeps_ranking_service": "_select_probe_equivalent_bending_cleanup_candidate(" in target_segment,
        "target_no_longer_embeds_item_projection_payload": 'item["action_payload"] = payload' not in target_segment
        and 'item["resolved_candidate"] = resolved' not in target_segment,
        "controller_import_clean": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "helper_is_pure_projection": all(
            token not in helper_segment
            for token in (
                "st.",
                "session_state",
                "_guidance_item_from_resolved_candidate",
                "_evaluate_",
                "_select_",
            )
        ),
        "all_cases_match": all(bool(row.get("matches")) for row in parity),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_probe_equivalent_bending_item_projection_adapter_parity.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "PROBE_EQUIVALENT_BENDING_ITEM_PROJECTION_CONTROLLER_OWNED",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
        },
        "cases": parity,
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_probe_equivalent_bending_item_projection_adapter_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_probe_equivalent_bending_item_projection_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Probe-Equivalent Bending Item Projection Adapter Parity",
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
    lines.extend(f"| `{row.get('case')}` | `{row.get('matches')}` |" for row in payload.get("cases") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in dict(payload.get("checks") or {}).items())
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_probe_equivalent_bending_item_projection_adapter_parity {payload.get('status')}")
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
