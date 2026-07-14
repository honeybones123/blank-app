"""Verify bending-only target-band item projection delegates to controller helpers."""

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

TARGET = "_bending_only_target_band_cleanup_item"
BEST_SAFE_HELPER = "build_design_guide_controller_bending_only_best_safe_cleanup_item_projection"
TARGET_HELPER = "build_design_guide_controller_bending_only_target_band_cleanup_item_projection"
BEST_SAFE_ALIAS = "_build_design_guide_controller_bending_only_best_safe_cleanup_item_projection"
TARGET_ALIAS = "_build_design_guide_controller_bending_only_target_band_cleanup_item_projection"


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


def _old_best_safe_projection(
    item: dict[str, Any],
    selected: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    out = dict(item)
    out["candidate_search_evidence"] = dict(evidence)
    out["local_cleanup_candidate"] = True
    out["source"] = "design_guide_bending_only_best_safe_cleanup_search"
    out["affected_family"] = "bending"
    out["family"] = "bending"
    out["allow_in_target_primary_action"] = True
    out["best_safe_partial_cleanup"] = False
    out["no_second_cta_required"] = False
    out["guidance_intent"] = "efficiency_tightening"
    payload = dict(out.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["best_safe_partial_cleanup"] = False
    payload["no_second_cta_required"] = False
    payload["source_candidate_id"] = selected["candidate_id"]
    payload["candidate_id"] = selected["candidate_id"]
    payload["resolved_candidate_family_tag"] = "bending"
    payload["resolved_candidate_subfamilies"] = list(selected.get("subfamilies") or ["bottom_reinforcement"])
    out["action_payload"] = payload
    resolved = dict(out.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["best_safe_partial_cleanup"] = False
    resolved["no_second_cta_required"] = False
    resolved["candidate_id"] = selected["candidate_id"]
    resolved["source_candidate_id"] = selected["candidate_id"]
    resolved["family"] = "bending"
    resolved["recommendation_family_tag"] = "bending"
    resolved["subfamilies"] = list(selected.get("subfamilies") or ["bottom_reinforcement"])
    out["resolved_candidate"] = resolved
    return out


def _old_target_projection(
    item: dict[str, Any],
    selected: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    selected_family = str(selected.get("family") or "bending").strip().lower() or "bending"
    selected_subfamilies = list(
        selected.get("subfamilies")
        or (["shear", "bottom_reinforcement"] if selected_family == "combined" else ["bottom_reinforcement"])
    )
    out = dict(item)
    out["candidate_search_evidence"] = dict(evidence)
    out["local_cleanup_candidate"] = True
    out["source"] = "design_guide_bending_only_cleanup_search"
    out["affected_family"] = selected_family
    out["family"] = selected_family
    out["selected_action_family"] = selected_family
    out["check_key"] = selected_family
    out["subfamilies"] = list(selected_subfamilies)
    out["allow_in_target_primary_action"] = True
    payload = dict(out.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    payload["source_candidate_id"] = selected["candidate_id"]
    payload["candidate_id"] = selected["candidate_id"]
    payload["family"] = selected_family
    payload["resolved_candidate_family_tag"] = selected_family
    payload["resolved_candidate_subfamilies"] = list(selected_subfamilies)
    out["action_payload"] = payload
    resolved = dict(out.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    resolved["candidate_id"] = selected["candidate_id"]
    resolved["source_candidate_id"] = selected["candidate_id"]
    resolved["family"] = selected_family
    resolved["recommendation_family_tag"] = selected_family
    resolved["subfamilies"] = list(selected_subfamilies)
    out["resolved_candidate"] = resolved
    return out


def _case_item() -> dict[str, Any]:
    return {
        "title": "Bending cleanup - further reduction reaches target range",
        "action_payload": {"existing": "payload"},
        "resolved_candidate": {"existing": "resolved"},
    }


def _case_evidence(candidate_id: str) -> dict[str, Any]:
    return {
        "selected_candidate_id": candidate_id,
        "selected_candidate_title": "Bending cleanup - further reduction reaches target range",
        "selected_candidate_updates": {"bot1_count": 5},
        "search_scope": "design_guide_bending_only_cleanup_search",
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)
    _, _, target_segment = _function_segment(inputs_source, TARGET)
    _, _, best_safe_segment = _function_segment(controller_source, BEST_SAFE_HELPER)
    _, _, target_helper_segment = _function_segment(controller_source, TARGET_HELPER)

    from design_brain.design_guide_controller import (
        build_design_guide_controller_bending_only_best_safe_cleanup_item_projection,
        build_design_guide_controller_bending_only_target_band_cleanup_item_projection,
    )

    best_safe_selected = {
        "candidate_id": "best_safe_001",
        "source_candidate_id": "best_safe_001",
        "subfamilies": ["geometry", "bottom_reinforcement"],
    }
    target_selected = {
        "candidate_id": "target_001",
        "source_candidate_id": "target_001",
        "family": "bending",
        "subfamilies": ["bottom_reinforcement"],
    }
    combined_selected = {
        "candidate_id": "combined_001",
        "source_candidate_id": "combined_001",
        "family": "combined",
        "subfamilies": ["shear", "bottom_reinforcement"],
    }

    parity_cases = []
    for name, old_fn, new_fn, selected in (
        (
            "best_safe_partial",
            _old_best_safe_projection,
            build_design_guide_controller_bending_only_best_safe_cleanup_item_projection,
            best_safe_selected,
        ),
        (
            "target_bending",
            _old_target_projection,
            build_design_guide_controller_bending_only_target_band_cleanup_item_projection,
            target_selected,
        ),
        (
            "target_combined_after_terminalisation",
            _old_target_projection,
            build_design_guide_controller_bending_only_target_band_cleanup_item_projection,
            combined_selected,
        ),
    ):
        evidence = _case_evidence(str(selected["candidate_id"]))
        old = old_fn(_case_item(), dict(selected), evidence)
        new = new_fn(
            item=_case_item(),
            selected_candidate=dict(selected),
            candidate_search_evidence=evidence,
        )
        parity_cases.append(
            {
                "case": name,
                "matches": old == new,
                "old": old,
                "new": new,
            }
        )

    source_checks = {
        "target_found": f"def {TARGET}(" in inputs_source,
        "controller_best_safe_helper_found": f"def {BEST_SAFE_HELPER}(" in controller_source,
        "controller_target_helper_found": f"def {TARGET_HELPER}(" in controller_source,
        "controller_best_safe_helper_exported": f'"{BEST_SAFE_HELPER}"' in controller_source,
        "controller_target_helper_exported": f'"{TARGET_HELPER}"' in controller_source,
        "inputs_imports_best_safe_helper": f"{BEST_SAFE_HELPER} as {BEST_SAFE_ALIAS}" in inputs_source,
        "inputs_imports_target_helper": f"{TARGET_HELPER} as {TARGET_ALIAS}" in inputs_source,
        "target_calls_best_safe_helper": f"{BEST_SAFE_ALIAS}(" in target_segment,
        "target_calls_target_helper": f"{TARGET_ALIAS}(" in target_segment,
        "target_keeps_terminalisation_fold": "allow_terminalisation_fold" in target_segment
        and "_shear_low_util_target_cleanup_item(" in target_segment,
        "target_keeps_candidate_evaluation_loop": "_evaluate_bending_only_target_band_candidate_with_service(" in target_segment,
        "target_keeps_debug_sink_writes": "debug_sink[\"bending_only_cleanup_search_used\"]" in target_segment,
        "target_removed_best_safe_inline_projection_payload_assignment": (
            'payload["best_safe_partial_cleanup"] = False' not in target_segment
        ),
        "target_removed_final_inline_projection_payload_assignment": (
            'payload["family"] = selected_family' not in target_segment
        ),
        "controller_imports_no_inputs_page": "import inputs_page" not in controller_source
        and "from inputs_page" not in controller_source,
        "controller_imports_no_streamlit": "streamlit" not in controller_source,
        "best_safe_helper_no_session_or_render": all(
            token not in best_safe_segment for token in ("st.", "session_state", "streamlit", "_guidance_item_from_resolved_candidate")
        ),
        "target_helper_no_session_or_render": all(
            token not in target_helper_segment for token in ("st.", "session_state", "streamlit", "_guidance_item_from_resolved_candidate")
        ),
    }

    checks = {
        **source_checks,
        "all_projection_parity_cases_match": all(case["matches"] for case in parity_cases),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    decision = (
        "BENDING_ONLY_ITEM_PROJECTION_ADAPTER_PARITY_PROVEN"
        if status == "PASS"
        else "BENDING_ONLY_ITEM_PROJECTION_ADAPTER_PARITY_FAILED"
    )
    return {
        "status": status,
        "decision": decision,
        "checks": checks,
        "parity_cases": parity_cases,
        "remaining_page_owned_surfaces": [
            "fast-render/cache shell",
            "candidate evaluation callback loop",
            "same-click terminalisation fold",
            "debug sink writes",
        ],
        "product_behavior_changed": False,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "-") + "Z"
    json_path = ARTIFACT_DIR / f"design_guide_bending_only_item_projection_adapter_parity_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_bending_only_item_projection_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bending-Only Item Projection Adapter Parity",
        "",
        f"## Executive Summary",
        payload["status"],
        "",
        "## Decision",
        payload["decision"],
        "",
        "## Checks",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in payload["checks"].items())
    lines.extend(["", "## Parity Cases"])
    lines.extend(f"- `{case['case']}`: `{case['matches']}`" for case in payload["parity_cases"])
    lines.extend(["", "## Remaining Page-Owned Surfaces"])
    lines.extend(f"- {surface}" for surface in payload["remaining_page_owned_surfaces"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
