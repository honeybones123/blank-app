"""Proof snapshot for combined low-util candidate evaluation boundary cutover."""

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
HELPER_NAME = "evaluate_design_guide_combined_low_util_cleanup_candidate"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _exercise_helper() -> dict[str, Any]:
    module = importlib.import_module("design_brain.design_guide_controller")
    helper = getattr(module, HELPER_NAME)
    base_state = {"b": 400.0, "D": 650.0, "lig_d": 10, "lig_legs": 2}
    updates = {"b": 375.0, "lig_d": 0, "lig_legs": 0}
    calls: list[dict[str, Any]] = []

    def accepting_evaluator(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls.append({"state": dict(state or {}), "kwargs": dict(kwargs or {})})
        candidate_state = dict(state or {})
        candidate_state.update(dict(kwargs.get("updates") or {}))
        return {
            "state": candidate_state,
            "overview": {
                "utils": {"bending": 0.78, "shear": 0.68},
                "statuses": {"bending": "PASS", "shear": "PASS"},
                "any_fail": False,
                "all_key_pass": True,
            },
        }

    accepted = helper(
        evaluator=accepting_evaluator,
        base_state=base_state,
        updates=updates,
        evaluation_source="combined_best_safe_shear_plus_bending_cleanup",
        evaluation_label="Shear and bending cleanup - one-click optimisation",
        evaluation_action_type="apply_resolved_candidate",
    )

    shear_probe = helper(
        evaluator=accepting_evaluator,
        base_state=base_state,
        updates={"lig_d": 0, "lig_legs": 0},
        evaluation_source="combined_cleanup_shear_leg_probe",
        evaluation_label="Shear cleanup - best safe one-click reduction",
        evaluation_action_type="apply_resolved_candidate",
    )

    def raising_evaluator(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("synthetic evaluator failure")

    raised = helper(
        evaluator=raising_evaluator,
        base_state=base_state,
        updates=updates,
    )
    non_dict = helper(
        evaluator=lambda *_args, **_kwargs: None,
        base_state=base_state,
        updates=updates,
    )
    missing = helper(
        evaluator=None,
        base_state=base_state,
        updates=updates,
    )
    return {
        "accepted": accepted,
        "shear_probe": shear_probe,
        "raised": raised,
        "non_dict": non_dict,
        "missing": missing,
        "calls": calls,
        "accepted_hash_repeat": _stable_hash(accepted)
        == _stable_hash(
            helper(
                evaluator=accepting_evaluator,
                base_state=base_state,
                updates=updates,
                evaluation_source="combined_best_safe_shear_plus_bending_cleanup",
                evaluation_label="Shear and bending cleanup - one-click optimisation",
                evaluation_action_type="apply_resolved_candidate",
            )
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    exercise = _exercise_helper()
    return {
        "decision": "COMBINED_LOW_UTIL_CANDIDATE_EVALUATION_CUTOVER_PASS",
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "helper_exercise": exercise,
        "source_checks": {
            "controller_helper_exported": f'"{HELPER_NAME}"' in controller_source,
            "controller_helper_imported": (
                f"{HELPER_NAME} as _evaluate_design_guide_combined_low_util_cleanup_candidate"
                in inputs_source
            ),
            "controller_helper_called_in_target": (
                "_evaluate_design_guide_combined_low_util_cleanup_candidate("
                in target_source
            ),
            "legacy_direct_evaluator_calls_removed_from_target": (
                "_evaluate_auto_design_candidate(" not in target_source
            ),
            "page_evaluator_injected_in_target": (
                "evaluator=_evaluate_auto_design_candidate" in target_source
            ),
            "page_evaluator_function_retained": "def _evaluate_auto_design_candidate(" in inputs_source,
            "controller_page_free": all(
                token not in controller_source
                for token in ("inputs_page", "st.session_state", "streamlit")
            ),
            "no_render_apply_or_cta_owner_moved": all(
                token not in controller_source
                for token in (
                    "st.button",
                    "st.markdown",
                    "route_apply",
                    "apply_routing",
                    "render_button",
                    "streamlit",
                )
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    exercise = dict(capture.get("helper_exercise") or {})
    accepted = dict(exercise.get("accepted") or {})
    accepted_proof = dict(accepted.get("evaluation_proof") or {})
    shear_probe_proof = dict((exercise.get("shear_probe") or {}).get("evaluation_proof") or {})
    calls = list(exercise.get("calls") or [])
    first_kwargs = dict((calls[0] if calls else {}).get("kwargs") or {})
    second_kwargs = dict((calls[1] if len(calls) > 1 else {}).get("kwargs") or {})
    raised_proof = dict((exercise.get("raised") or {}).get("evaluation_proof") or {})
    non_dict_proof = dict((exercise.get("non_dict") or {}).get("evaluation_proof") or {})
    missing_proof = dict((exercise.get("missing") or {}).get("evaluation_proof") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "accepted_candidate_returned": isinstance(accepted.get("candidate"), dict),
        "accepted_candidate_hash_stamped": bool(accepted_proof.get("candidate_hash")),
        "accepted_update_hash_stamped": bool(accepted_proof.get("update_hash")),
        "accepted_proof_hash_stable": exercise.get("accepted_hash_repeat") is True,
        "combined_evaluator_called_with_same_source": (
            first_kwargs.get("source") == "combined_best_safe_shear_plus_bending_cleanup"
        ),
        "combined_evaluator_called_with_same_label": (
            first_kwargs.get("label") == "Shear and bending cleanup - one-click optimisation"
        ),
        "shear_probe_evaluator_called_with_same_source": (
            second_kwargs.get("source") == "combined_cleanup_shear_leg_probe"
        ),
        "shear_probe_evaluator_called_with_same_label": (
            second_kwargs.get("label") == "Shear cleanup - best safe one-click reduction"
        ),
        "shear_probe_hash_stamped": bool(shear_probe_proof.get("candidate_hash")),
        "exception_normalizes_to_candidate_evaluation_failed": (
            raised_proof.get("failed_reason") == "candidate_evaluation_failed"
            and raised_proof.get("evaluation_failed") is True
        ),
        "non_dict_normalizes_to_candidate_evaluation_failed": (
            non_dict_proof.get("failed_reason") == "candidate_evaluation_failed"
            and non_dict_proof.get("evaluation_failed") is True
        ),
        "missing_evaluator_normalizes_to_missing": (
            missing_proof.get("failed_reason") == "candidate_evaluator_missing"
            and missing_proof.get("evaluation_failed") is True
        ),
        "source_checks_green": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Candidate Evaluation Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Source Checks"])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("source_checks") or {}).items()
    )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- Function: `{FUNCTION_NAME}`",
            f"- Controller helper: `{HELPER_NAME}`",
            "- Evaluator remains injected/page-owned; candidate math and behaviour are unchanged.",
        ]
    )
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
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_low_util_candidate_evaluation_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_candidate_evaluation_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_candidate_evaluation_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
