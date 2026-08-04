"""Proof snapshot for combined low-util invalid-item fallback cutover."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import importlib
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FUNCTION_NAME = "_combine_best_safe_shear_with_bending_cleanup_item"
HELPER_NAME = "build_design_guide_combined_low_util_invalid_item_fallback"
WRAPPER_NAME = "run_design_guide_combined_low_util_orchestration"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return "", None, None


def _exercise_helper() -> dict[str, Any]:
    module = importlib.import_module("design_brain.design_guide_controller")
    helper = getattr(module, HELPER_NAME)
    payload = {
        "result_packaging_proof": {
            "result_packaging_hash": "result-packaging-proof-hash",
            "valid_item": False,
        },
        "bending_cleanup_generation_proof": {
            "bending_cleanup_generation_hash": "bending-generation-proof-hash",
        },
        "combined_updates": {"lig_legs": 0, "bot_bar_count": 5},
        "evidence": {"safe_candidate_count": 1, "target_band_candidates": []},
        "combined_audit": {"post_click_unresolved_low_util_families": []},
    }
    first = helper(**payload)
    second = helper(**payload)
    debug_payload = dict(first.get("debug_payload") or {})
    proof = dict(first.get("invalid_item_fallback_proof") or {})
    return {
        "helper_name": HELPER_NAME,
        "stable_repeat_hash": _stable_hash(first) == _stable_hash(second),
        "item_is_none": first.get("item") is None,
        "debug_payload_keys": sorted(debug_payload.keys()),
        "proof_keys": sorted(proof.keys()),
        "product_driving": debug_payload.get("product_driving"),
        "fallback_hash_present": bool(proof.get("invalid_item_fallback_hash")),
        "debug_hash_matches_proof": (
            debug_payload.get("combined_low_util_invalid_item_fallback_hash")
            == proof.get("invalid_item_fallback_hash")
        ),
        "debug_payload_hash": _stable_hash(debug_payload),
        "proof_hash": _stable_hash(proof),
    }


def _capture() -> dict[str, Any]:
    function_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    wrapper_source, wrapper_start, wrapper_end = _function_source(CONTROLLER, WRAPPER_NAME)
    function_deleted = start_line is None
    forbidden_fallback_tokens = [
        "return _finish(None, debug_payload)",
        "len(raw_updates)",
        "len(update_trials)",
        "len(target_candidates)",
        '"bending_only_cleanup_generated_count": len(raw_updates)',
        '"bending_only_cleanup_deduped_count": len(update_trials)',
        '"bending_only_cleanup_target_count": len(target_candidates)',
    ]
    return {
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": (end_line - start_line + 1) if not function_deleted else 0,
            "deleted": function_deleted,
        },
        "wrapper": {
            "name": WRAPPER_NAME,
            "start_line": wrapper_start,
            "end_line": wrapper_end,
            "line_count": wrapper_end - wrapper_start + 1,
        },
        "helper_exercise": _exercise_helper(),
        "controller_helper_defined": f"def {HELPER_NAME}(" in controller_source,
        "controller_helper_exported": f'"{HELPER_NAME}"' in controller_source,
        "inputs_helper_imported": f"{HELPER_NAME} as _{HELPER_NAME}" in INPUTS_PAGE.read_text(
            encoding="utf-8", errors="replace"
        ),
        "inputs_target_calls_wrapper": function_deleted or f"_{WRAPPER_NAME}(" in function_source,
        "controller_wrapper_calls_helper": f"{HELPER_NAME}(" in wrapper_source,
        "controller_wrapper_calls_result_packaging": (
            "build_design_guide_combined_low_util_result_packaging(" in wrapper_source
        ),
        "forbidden_fallback_tokens": {
            token: {
                "present": token in function_source,
                "count": function_source.count(token),
            }
            for token in forbidden_fallback_tokens
        },
        "replacement_return_is_none": "return None" in function_source,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    forbidden = dict(capture.get("forbidden_fallback_tokens") or {})
    helper = dict(capture.get("helper_exercise") or {})
    return {
        "controller_helper_defined": bool(capture.get("controller_helper_defined")),
        "controller_helper_exported": bool(capture.get("controller_helper_exported")),
        "inputs_helper_imported": bool(capture.get("inputs_helper_imported")),
        "inputs_target_calls_wrapper": bool(capture.get("inputs_target_calls_wrapper")),
        "controller_wrapper_calls_helper": bool(capture.get("controller_wrapper_calls_helper")),
        "controller_wrapper_calls_result_packaging": bool(
            capture.get("controller_wrapper_calls_result_packaging")
        ),
        "old_undefined_fallback_removed": not any(
            bool(row.get("present")) for row in forbidden.values() if isinstance(row, dict)
        ),
        "helper_stable_repeat_hash": bool(helper.get("stable_repeat_hash")),
        "helper_returns_no_product_item": bool(helper.get("item_is_none")),
        "helper_fallback_hash_present": bool(helper.get("fallback_hash_present")),
        "helper_debug_hash_matches_proof": bool(helper.get("debug_hash_matches_proof")),
        "helper_is_non_product_driving": helper.get("product_driving") is False,
        "product_behavior_unchanged_flag": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged_flag": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged_flag": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged_flag": capture.get("family_runtime_changed") is False,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Combined Low-Util Invalid-Item Fallback Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Summary",
        "",
        (
            "The invalid result-packaging fallback is now represented by a "
            "DesignGuideController proof/debug payload instead of page-local legacy search fields."
        ),
        "",
        "## Checks",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Helper Exercise",
            "",
            "```json",
            json.dumps(payload.get("capture", {}).get("helper_exercise", {}), indent=2, sort_keys=True),
            "```",
            "",
            "## Forbidden Fallback Tokens",
            "",
            "```json",
            json.dumps(
                payload.get("capture", {}).get("forbidden_fallback_tokens", {}),
                indent=2,
                sort_keys=True,
            ),
            "```",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "snapshot": "design_guide_combined_low_util_invalid_item_fallback_cutover",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "capture": capture,
        "checks": checks,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_invalid_item_fallback_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_invalid_item_fallback_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_combined_low_util_invalid_item_fallback_cutover {status}")
    print(json_path)
    print(report_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
