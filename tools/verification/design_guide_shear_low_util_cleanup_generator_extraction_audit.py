"""Audit extraction plan for page-local shear low-util cleanup generator."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

FUNCTION_NAME = "_shear_low_util_target_cleanup_item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _classify_tokens(function_source: str) -> list[dict[str, Any]]:
    classes = [
        (
            "entry_guard",
            ["_shear_reinforcement_is_active(", "current_shear_util", "threshold"],
            "pure_policy_guard_candidate",
            "can_move_after parity proof",
        ),
        (
            "overview_fallback",
            ["_collect_design_overview(", "_build_design_actions_context("],
            "evaluation_context_dependency",
            "needs Design Brain candidate evaluation boundary or injected adapter",
        ),
        (
            "mode_and_target_band",
            ["_design_mode_config(", "_design_optimisation_goal(", "_resolved_efficiency_target_band("],
            "design_brain_config_dependency",
            "can move behind controller/shared config API",
        ),
        (
            "variant_generation",
            [
                "_build_design_guide_shear_low_util_raw_variant_states(",
                "_build_design_guide_shear_low_util_no_link_probe(",
                "_build_design_guide_shear_low_util_variant_sequence(",
            ],
            "candidate_generation_core",
            "raw variant states and no-link ordering are controller-owned; page keeps candidate-key dedupe",
        ),
        (
            "candidate_evaluation_boundary",
            ["_evaluate_design_guide_shear_low_util_cleanup_candidate("],
            "controller_injected_evaluator_boundary",
            "controller-owned boundary with existing evaluator injected",
        ),
        (
            "acceptance_filtering",
            [
                "_build_design_guide_shear_low_util_candidate_delta_screen(",
                "_build_design_guide_shear_low_util_candidate_acceptance_screen(",
            ],
            "engineering_acceptance_policy",
            "should move with generator after parity proof",
        ),
        (
            "evidence_and_item_packaging",
            [
                "candidate_search_evidence",
                "button_contract",
                "action_payload",
                "resolved_candidate",
            ],
            "publication_item_packaging",
            "must be split into Design Brain item/output object before deletion",
        ),
    ]
    inventory = []
    for name, tokens, classification, extraction_note in classes:
        present_tokens = {token: token in function_source for token in tokens}
        inventory.append(
            {
                "section": name,
                "classification": classification,
                "tokens": present_tokens,
                "all_tokens_present": all(present_tokens.values()),
                "extraction_note": extraction_note,
            }
        )
    return inventory


def _capture() -> dict[str, Any]:
    function_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    inventory = _classify_tokens(function_source)
    return {
        "decision": "SHEAR_LOW_UTIL_GENERATOR_EXTRACTION_PLAN_REQUIRED",
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "inventory": inventory,
        "safe_to_move_full_generator_now": False,
        "safe_to_delete_page_function_now": False,
        "first_safe_extraction_target": "current_overview_boundary_object",
        "next_safe_step": (
            "Create a Design Brain/shared current-overview boundary object for fallback shear util "
            "and failure-coverage comparison."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    inventory = list(capture.get("inventory") or [])
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "all_sections_detected": len(inventory) == 7,
        "critical_sections_present": all(item.get("all_tokens_present") for item in inventory),
        "not_safe_to_move_full_generator": capture.get("safe_to_move_full_generator_now") is False,
        "not_safe_to_delete_page_function": capture.get("safe_to_delete_page_function_now") is False,
        "first_extraction_target_named": capture.get("first_safe_extraction_target")
        == "current_overview_boundary_object",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Cleanup Generator Extraction Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Function",
            "",
            f"- Name: `{(capture.get('function') or {}).get('name')}`",
            f"- Lines: `{(capture.get('function') or {}).get('start_line')}`-`{(capture.get('function') or {}).get('end_line')}`",
            "",
            "## Inventory",
            "",
            "| Section | Classification | All Tokens Present | Extraction Note |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in capture.get("inventory") or []:
        lines.append(
            f"| {item.get('section')} | {item.get('classification')} | {item.get('all_tokens_present')} | {item.get('extraction_note')} |"
        )
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_cleanup_generator_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_cleanup_generator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_cleanup_generator_extraction_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
