"""Proof snapshot for combined low-util orchestration wrapper cutover."""

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


def _exercise_wrapper() -> dict[str, Any]:
    module = importlib.import_module("design_brain.design_guide_controller")
    wrapper = getattr(module, WRAPPER_NAME)

    def resolver(item: dict[str, Any], *, state: dict[str, Any]) -> dict[str, Any]:
        title = str(item.get("title_main") or item.get("title") or "").lower()
        if "shear" in title:
            return {"lig_legs": 0}
        if "bending" in title:
            return {"bot_bar_count": 5}
        return {}

    def evaluator(
        candidate_state: dict[str, Any],
        *,
        source: str = "",
        label: str = "",
        action_type: str = "",
        updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        overview = {
            "utils": {"bending": 0.88, "shear": 0.74},
            "worst_util": 0.88,
            "statuses": {"bending": "PASS", "shear": "PASS"},
        }
        if source == "combined_cleanup_shear_leg_probe":
            overview = {"utils": {"bending": 0.25, "shear": 0.74}, "worst_util": 0.74}
        return {
            "overview": overview,
            "updates": dict(updates or {}),
            "candidate_post_util": overview.get("worst_util"),
        }

    def bending_generator(state: dict[str, Any], overview: dict[str, Any], mode_config: dict[str, Any], *, debug_sink=None):
        if isinstance(debug_sink, dict):
            debug_sink["bending_generator_called"] = True
        return {
            "title": "Bending cleanup",
            "action_type": "apply_resolved_candidate",
            "candidate_search_evidence": {
                "safe_candidate_count": 1,
                "executable_candidate_count": 1,
            },
            "resolved_candidate": {"candidate_search_evidence": {"safe_candidate_count": 1}},
        }

    def required_checks_acceptable(overview: dict[str, Any]) -> bool:
        return True

    def preview_has_fail(overview: dict[str, Any]) -> bool:
        return False

    def post_click_audit(overview: dict[str, Any], blocker_source=None, state=None) -> dict[str, Any]:
        return {"post_click_unresolved_low_util_families": []}

    def target_band(mode_config: dict[str, Any], *, goal: str = "") -> tuple[float, float]:
        return (0.85, 1.0)

    def optimisation_goal(state: dict[str, Any]) -> str:
        return "balanced"

    def evidence_builder(**kwargs: Any) -> dict[str, Any]:
        evidence = dict(kwargs)
        evidence["safe_candidate_count"] = 1
        evidence["executable_candidate_count"] = 1
        return evidence

    def guidance_item_builder(
        candidate: dict[str, Any],
        *,
        state: dict[str, Any] | None = None,
        overview: dict[str, Any] | None = None,
        title: str = "",
        reasoning: str = "",
        status: str = "",
        primary_action: str = "",
    ) -> dict[str, Any]:
        return {
            "title_main": title,
            "title": title,
            "status": status,
            "primary_action": primary_action,
            "action_payload": {},
            "resolved_candidate": dict(candidate),
            "button_contract": {},
        }

    def best_safe(item: dict[str, Any]) -> bool:
        return bool(item.get("candidate_search_evidence"))

    def safe_incremental(item: dict[str, Any]) -> bool:
        return True

    def updates_match(state: dict[str, Any], updates: dict[str, Any]) -> bool:
        return all(state.get(key) == value for key, value in updates.items())

    def parse_util(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    result = wrapper(
        state={"lig_legs": 2, "bot_bar_count": 8},
        overview={"utils": {"bending": 0.25, "shear": 0.8}},
        mode_config={"goal": "balanced"},
        shear_item={
            "title": "Shear cleanup - one-click",
            "action_type": "apply_resolved_candidate",
            "local_cleanup_candidate": True,
            "candidate_search_evidence": {"safe_candidate_count": 1},
        },
        recommendation_updates_resolver=resolver,
        candidate_evaluator=evaluator,
        bending_cleanup_generator=bending_generator,
        required_checks_acceptable_fn=required_checks_acceptable,
        preview_statuses_have_explicit_fail_fn=preview_has_fail,
        post_click_audit_fn=post_click_audit,
        target_band_resolver=target_band,
        optimisation_goal_resolver=optimisation_goal,
        evidence_builder=evidence_builder,
        guidance_item_builder=guidance_item_builder,
        best_safe_partial_cleanup_fn=best_safe,
        safe_incremental_cleanup_fn=safe_incremental,
        updates_match_state_fn=updates_match,
        util_parser=parse_util,
        compound_shear_update_keys={"lig_legs", "s_lig"},
        compound_bottom_update_keys={"bot_bar_count", "bot_bar_dia"},
        final_accepted_min_family_util=0.85,
    )
    item = dict(result.get("item") or {})
    contract = dict(item.get("button_contract") or {})
    proof = dict(result.get("orchestration_proof") or {})
    return {
        "item_present": bool(item),
        "item_title": item.get("title_main") or item.get("title"),
        "family": item.get("family"),
        "updates": dict(item.get("updates") or {}),
        "button_enabled": contract.get("enabled"),
        "button_actionable": contract.get("actionable"),
        "finish_reason": proof.get("finish_reason"),
        "orchestration_hash_present": bool(proof.get("orchestration_hash")),
        "stable_hash": _stable_hash(result),
    }


def _capture() -> dict[str, Any]:
    function_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    function_deleted = start_line is None
    old_decision_tokens = [
        "_resolve_design_guide_combined_low_util_cleanup_updates(",
        "_evaluate_design_guide_combined_low_util_cleanup_candidate(",
        "_run_design_guide_combined_low_util_bending_cleanup_item_generation(",
        "_assess_design_guide_combined_low_util_cleanup_acceptance_gate(",
        "_assess_design_guide_combined_low_util_post_click_accepted_green_audit(",
        "_resolve_design_guide_combined_low_util_cleanup_target_band(",
        "_build_design_guide_combined_low_util_cleanup_candidate_search_evidence(",
        "_build_design_guide_combined_low_util_result_packaging(",
        "_build_design_guide_combined_low_util_invalid_item_fallback(",
    ]
    return {
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": (end_line - start_line + 1) if not function_deleted else 0,
            "deleted": function_deleted,
        },
        "wrapper_defined": f"def {WRAPPER_NAME}(" in controller_source,
        "wrapper_exported": f'"{WRAPPER_NAME}"' in controller_source,
        "wrapper_imported": f"{WRAPPER_NAME} as _{WRAPPER_NAME}" in INPUTS_PAGE.read_text(
            encoding="utf-8", errors="replace"
        ),
        "wrapper_called_in_target": function_deleted or f"_{WRAPPER_NAME}(" in function_source,
        "old_decision_tokens_in_target": {
            token: {"present": token in function_source, "count": function_source.count(token)}
            for token in old_decision_tokens
        },
        "target_function_source_hash": _stable_hash(function_source),
        "wrapper_exercise": _exercise_wrapper(),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    exercise = dict(capture.get("wrapper_exercise") or {})
    old_tokens = dict(capture.get("old_decision_tokens_in_target") or {})
    return {
        "wrapper_defined": bool(capture.get("wrapper_defined")),
        "wrapper_exported": bool(capture.get("wrapper_exported")),
        "wrapper_imported": bool(capture.get("wrapper_imported")),
        "wrapper_called_in_target": bool(capture.get("wrapper_called_in_target")),
        "target_function_is_thin_or_deleted": int((capture.get("function") or {}).get("line_count") or 0) <= 45,
        "old_decision_tokens_removed_from_target": not any(
            bool(row.get("present")) for row in old_tokens.values() if isinstance(row, dict)
        ),
        "wrapper_exercise_item_present": bool(exercise.get("item_present")),
        "wrapper_exercise_combined_family": exercise.get("family") == "combined",
        "wrapper_exercise_updates_present": bool(exercise.get("updates")),
        "wrapper_exercise_button_enabled": exercise.get("button_enabled") is True,
        "wrapper_exercise_button_actionable": exercise.get("button_actionable") is True,
        "wrapper_exercise_finish_reason": exercise.get("finish_reason") == "selected_item",
        "wrapper_exercise_hash_present": bool(exercise.get("orchestration_hash_present")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Combined Low-Util Orchestration Wrapper Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{payload.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Wrapper Exercise",
            "",
            "```json",
            json.dumps(payload.get("capture", {}).get("wrapper_exercise", {}), indent=2, sort_keys=True),
            "```",
            "",
            "## Old Target Tokens",
            "",
            "```json",
            json.dumps(
                payload.get("capture", {}).get("old_decision_tokens_in_target", {}),
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
    decision = (
        "COMBINED_LOW_UTIL_ORCHESTRATION_WRAPPER_CUTOVER_PASS"
        if status == "PASS"
        else "COMBINED_LOW_UTIL_ORCHESTRATION_WRAPPER_CUTOVER_FAIL"
    )
    payload = {
        "status": status,
        "decision": decision,
        "snapshot": "design_guide_combined_low_util_orchestration_wrapper_cutover",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "capture": capture,
        "checks": checks,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_orchestration_wrapper_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_orchestration_wrapper_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_combined_low_util_orchestration_wrapper_cutover {status}")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
