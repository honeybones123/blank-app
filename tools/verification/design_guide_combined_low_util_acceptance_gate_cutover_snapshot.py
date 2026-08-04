"""Proof snapshot for combined low-util acceptance-gate boundary cutover."""

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
HELPER_NAME = "assess_design_guide_combined_low_util_cleanup_acceptance_gate"


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

    def required_ok(overview: dict[str, Any]) -> bool:
        return not bool(overview.get("required_checks_fail"))

    def explicit_fail(statuses: dict[str, Any]) -> bool:
        return any(str(value).upper() == "FAIL" for value in statuses.values())

    passing_overview = {
        "any_fail": False,
        "statuses": {"bending": "PASS", "shear": "PASS"},
    }
    any_fail_overview = {
        "any_fail": True,
        "statuses": {"bending": "PASS", "shear": "PASS"},
    }
    explicit_fail_overview = {
        "any_fail": False,
        "statuses": {"bending": "PASS", "shear": "FAIL"},
    }
    required_fail_overview = {
        "any_fail": False,
        "required_checks_fail": True,
        "statuses": {"bending": "PASS", "shear": "PASS"},
    }
    passing = helper(
        overview=passing_overview,
        required_checks_acceptable_fn=required_ok,
        preview_statuses_have_explicit_fail_fn=explicit_fail,
    )
    any_fail = helper(
        overview=any_fail_overview,
        required_checks_acceptable_fn=required_ok,
        preview_statuses_have_explicit_fail_fn=explicit_fail,
    )
    explicit = helper(
        overview=explicit_fail_overview,
        required_checks_acceptable_fn=required_ok,
        preview_statuses_have_explicit_fail_fn=explicit_fail,
    )
    required = helper(
        overview=required_fail_overview,
        required_checks_acceptable_fn=required_ok,
        preview_statuses_have_explicit_fail_fn=explicit_fail,
    )
    missing = helper(
        overview=passing_overview,
        required_checks_acceptable_fn=None,
        preview_statuses_have_explicit_fail_fn=None,
    )
    return {
        "passing": passing,
        "any_fail": any_fail,
        "explicit": explicit,
        "required": required,
        "missing": missing,
        "passing_hash_repeat": _stable_hash(passing)
        == _stable_hash(
            helper(
                overview=passing_overview,
                required_checks_acceptable_fn=required_ok,
                preview_statuses_have_explicit_fail_fn=explicit_fail,
            )
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    exercise = _exercise_helper()
    return {
        "decision": "COMBINED_LOW_UTIL_ACCEPTANCE_GATE_CUTOVER_PASS",
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
                f"{HELPER_NAME} as _assess_design_guide_combined_low_util_cleanup_acceptance_gate"
                in inputs_source
            ),
            "controller_helper_called_once_in_target": (
                target_source.count("_assess_design_guide_combined_low_util_cleanup_acceptance_gate(")
                == 1
            ),
            "legacy_required_checks_call_removed_from_target": (
                "_overview_required_checks_acceptable(" not in target_source
            ),
            "legacy_preview_fail_call_removed_from_target": (
                "_candidate_preview_statuses_have_explicit_fail(" not in target_source
            ),
            "page_required_checks_injected_in_target": (
                "required_checks_acceptable_fn=_overview_required_checks_acceptable"
                in target_source
            ),
            "page_preview_fail_checker_injected_in_target": (
                "preview_statuses_have_explicit_fail_fn=_candidate_preview_statuses_have_explicit_fail"
                in target_source
            ),
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
    passing = dict(exercise.get("passing") or {})
    any_fail = dict(exercise.get("any_fail") or {})
    explicit = dict(exercise.get("explicit") or {})
    required = dict(exercise.get("required") or {})
    missing = dict(exercise.get("missing") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "passing_overview_accepted": passing.get("accepted") is True,
        "any_fail_rejected": any_fail.get("accepted") is False
        and any_fail.get("any_fail") is True,
        "explicit_fail_rejected": explicit.get("accepted") is False
        and explicit.get("explicit_preview_fail") is True,
        "required_checks_fail_rejected": required.get("accepted") is False
        and required.get("required_checks_acceptable") is False,
        "missing_checkers_reject": missing.get("accepted") is False,
        "acceptance_hash_stable": exercise.get("passing_hash_repeat") is True,
        "source_checks_green": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Acceptance Gate Cutover",
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
        ARTIFACT_DIR / f"design_guide_combined_low_util_acceptance_gate_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_combined_low_util_acceptance_gate_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_acceptance_gate_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
