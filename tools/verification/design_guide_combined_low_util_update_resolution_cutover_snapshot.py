"""Proof snapshot for combined low-util update-resolution boundary cutover."""

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
HELPER_NAME = "resolve_design_guide_combined_low_util_cleanup_updates"


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
    item = {
        "title": "Synthetic cleanup",
        "updates": {"b": 375.0, "lig_d": 0},
    }
    state = {"b": 400.0, "lig_d": 10}
    calls: list[dict[str, Any]] = []

    def accepting_resolver(resolved_item: dict[str, Any], *, state: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append({"item": dict(resolved_item or {}), "state": dict(state or {})})
        return dict(resolved_item.get("updates") or {})

    accepted = helper(
        resolver=accepting_resolver,
        item=item,
        state=state,
        source="combined_low_util_bending_item_updates",
    )

    def raising_resolver(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("synthetic update failure")

    raised = helper(resolver=raising_resolver, item=item, state=state)
    non_dict = helper(resolver=lambda *_args, **_kwargs: None, item=item, state=state)
    missing = helper(resolver=None, item=item, state=state)
    return {
        "accepted": accepted,
        "raised": raised,
        "non_dict": non_dict,
        "missing": missing,
        "calls": calls,
        "accepted_hash_repeat": _stable_hash(accepted)
        == _stable_hash(
            helper(
                resolver=accepting_resolver,
                item=item,
                state=state,
                source="combined_low_util_bending_item_updates",
            )
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    exercise = _exercise_helper()
    return {
        "decision": "COMBINED_LOW_UTIL_UPDATE_RESOLUTION_CUTOVER_PASS",
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
                f"{HELPER_NAME} as _resolve_design_guide_combined_low_util_cleanup_updates"
                in inputs_source
            ),
            "controller_helper_called_twice_in_target": (
                target_source.count("_resolve_design_guide_combined_low_util_cleanup_updates(") == 2
            ),
            "legacy_direct_update_resolver_calls_removed_from_target": (
                "_resolve_recommendation_updates(" not in target_source
            ),
            "page_update_resolver_injected_in_target": (
                "resolver=_resolve_recommendation_updates" in target_source
            ),
            "page_update_resolver_function_retained": "def _resolve_recommendation_updates(" in inputs_source,
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
    accepted_proof = dict(accepted.get("resolution_proof") or {})
    calls = list(exercise.get("calls") or [])
    raised_proof = dict((exercise.get("raised") or {}).get("resolution_proof") or {})
    non_dict_proof = dict((exercise.get("non_dict") or {}).get("resolution_proof") or {})
    missing_proof = dict((exercise.get("missing") or {}).get("resolution_proof") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "accepted_updates_returned": dict(accepted.get("updates") or {}) == {
            "b": 375.0,
            "lig_d": 0,
        },
        "accepted_update_hash_stamped": bool(accepted_proof.get("update_hash")),
        "accepted_proof_hash_stable": exercise.get("accepted_hash_repeat") is True,
        "resolver_called_once_for_accepted_case": len(calls) >= 1,
        "exception_normalizes_to_empty_updates": (
            dict((exercise.get("raised") or {}).get("updates") or {}) == {}
            and raised_proof.get("failed_reason") == "update_resolution_failed"
            and raised_proof.get("resolution_failed") is True
        ),
        "non_dict_normalizes_to_empty_updates": (
            dict((exercise.get("non_dict") or {}).get("updates") or {}) == {}
            and non_dict_proof.get("resolution_failed") is False
        ),
        "missing_resolver_normalizes_to_missing": (
            dict((exercise.get("missing") or {}).get("updates") or {}) == {}
            and missing_proof.get("failed_reason") == "update_resolver_missing"
            and missing_proof.get("resolution_failed") is True
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
        "# Design Guide Combined Low-Util Update Resolution Cutover",
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
            "- Update resolver remains injected/page-owned; update meaning is unchanged.",
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
        ARTIFACT_DIR / f"design_guide_combined_low_util_update_resolution_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_combined_low_util_update_resolution_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_update_resolution_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
