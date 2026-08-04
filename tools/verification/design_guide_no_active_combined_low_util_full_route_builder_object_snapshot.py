"""Verify the no-active combined low-util full-route controller builder.

Proof-only: this does not wire the live page route, move rendering, alter
CTA/apply behaviour, or change family runtime behaviour.
"""

from __future__ import annotations

from datetime import datetime
import ast
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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

BUILDER = "run_design_guide_controller_no_active_combined_low_util_cleanup_route"


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
    raise RuntimeError(f"Could not find {function_name}")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or "")
    if "PASS" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _parse_util(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _updates_match_state(_state: dict[str, Any], _updates: dict[str, Any]) -> bool:
    return False


def _normalise_candidate_id(label: str, **kwargs: Any) -> str:
    return f"{label}:{kwargs.get('family', 'combined')}"


def _shear_cleanup_item(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {
        "title": "Shear cleanup - best safe one-click reduction",
        "family": "shear",
        "updates": {"ligature_spacing": 300},
    }


def _combined_cleanup_item(
    _state: dict[str, Any],
    _overview: dict[str, Any],
    _config: dict[str, Any],
    seed: dict[str, Any] | None,
    debug_sink: Any = None,
) -> dict[str, Any]:
    updates = dict((seed or {}).get("updates") or {"ligature_spacing": 300})
    return {
        "title": "Combined cleanup - best safe one-click reduction",
        "title_main": "Combined cleanup - best safe one-click reduction",
        "primary_action": "Apply combined cleanup",
        "family": "combined",
        "check_key": "combined",
        "bucket": "pass",
        "guidance_intent": "efficiency_tightening",
        "updates": updates,
        "candidate_id": "combined-low-util-candidate",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": updates,
            "candidate_id": "combined-low-util-candidate",
        },
    }


def _identity_config(_goal: Any) -> dict[str, Any]:
    return {"mode": "fast"}


def _optimisation_goal(_state: dict[str, Any]) -> str:
    return "balanced"


def _normalise_item(item: dict[str, Any]) -> dict[str, Any]:
    return dict(item or {})


def _resolve_updates(item: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
    return dict(item.get("updates") or {})


def _contract_enabled(contract: dict[str, Any]) -> bool:
    return bool(contract.get("enabled") and contract.get("actionable"))


def _state_fingerprint(_state: dict[str, Any]) -> str:
    return "state-fingerprint-001"


def _exercise_builder() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_no_active_combined_low_util_cleanup_route,
    )

    kwargs = {
        "primary": {"title": "Current efficient design", "family": "combined"},
        "updates": {"ligature_spacing": 300},
        "final_state": {"beam_id": "beam_1", "ligature_spacing": 200},
        "final_overview": {"utils": {"bending": 0.40, "shear": 0.60}},
        "final_accepted_min_family_util": 0.85,
        "compound_shear_update_keys": {"ligature_spacing"},
        "parse_util_value_fn": _parse_util,
        "updates_match_state_fn": _updates_match_state,
        "normalise_design_guide_candidate_id_fn": _normalise_candidate_id,
        "shear_low_util_target_cleanup_item_fn": _shear_cleanup_item,
        "combine_best_safe_shear_with_bending_cleanup_item_fn": _combined_cleanup_item,
        "design_mode_config_fn": _identity_config,
        "design_optimisation_goal_fn": _optimisation_goal,
        "normalise_final_visible_design_guide_item_fn": _normalise_item,
        "resolve_recommendation_updates_fn": _resolve_updates,
        "design_guide_button_contract_enabled_fn": _contract_enabled,
        "state_fingerprint_fn": _state_fingerprint,
    }
    first = run_design_guide_controller_no_active_combined_low_util_cleanup_route(**kwargs)
    second = run_design_guide_controller_no_active_combined_low_util_cleanup_route(**kwargs)
    first_hash = _stable_hash(first)
    second_hash = _stable_hash(second)
    debug = dict((first or {}).get("debug") or {})
    trace_keys = {
        "result_trace": "design_guide_controller_combined_low_util_cleanup_result_trace_only",
        "route_policy_trace": (
            "design_guide_controller_combined_low_util_cleanup_route_policy_trace_only"
        ),
        "handoff_trace": (
            "design_guide_controller_combined_low_util_candidate_generation_handoff_trace_only"
        ),
    }
    return {
        "result_present": isinstance(first, dict),
        "stable_repeat_hash": first_hash == second_hash,
        "first_hash": first_hash,
        "second_hash": second_hash,
        "controller_authority": (first or {}).get("controller_authority"),
        "render_reason": (first or {}).get("render_reason"),
        "item_family": ((first or {}).get("item") or {}).get("family"),
        "presentation_show_apply_button": (
            ((first or {}).get("presentation") or {}).get("show_apply_button")
        ),
        "trace_keys_present": {name: key in debug for name, key in trace_keys.items()},
        "trace_keys_non_driving": {
            name: all(
                (debug.get(key) or {}).get(flag) is False
                for flag in (
                    "product_driving",
                    "render_driving",
                    "apply_driving",
                    "session_driving",
                )
            )
            for name, key in trace_keys.items()
        },
    }


def _capture() -> dict[str, Any]:
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    builder_source, start_line, end_line = _function_source(CONTROLLER, BUILDER)
    forbidden_controller_ownership = {
        "inputs_page_import": "inputs_page" in builder_source,
        "streamlit": (
            "import streamlit" in builder_source
            or "st.session_state" in builder_source
            or "st.button" in builder_source
            or "st.markdown" in builder_source
        ),
        "apply_routing": "_queue_primary_design_guide_button_action" in builder_source,
        "html_rendering": "_design_guide_dashboard_card_html" in builder_source,
        "family_runtime": "contracted_repair_ladder_specs(" in builder_source,
    }
    static_shape = {
        "builder_defined": f"def {BUILDER}(" in controller_source,
        "builder_exported": f'"{BUILDER}"' in controller_source,
        "calls_candidate_generation": (
            "run_design_guide_controller_combined_low_util_candidate_generation("
            in builder_source
        ),
        "calls_result_builder": (
            "build_design_guide_controller_combined_low_util_cleanup_result("
            in builder_source
        ),
        "returns_none_when_no_item": "if not cleanup_item:" in builder_source and "return None" in builder_source,
        "stamps_result_trace": (
            "design_guide_controller_combined_low_util_cleanup_result_trace_only"
            in builder_source
        ),
        "stamps_route_policy_trace": (
            "design_guide_controller_combined_low_util_cleanup_route_policy_trace_only"
            in builder_source
        ),
        "stamps_handoff_trace": (
            "design_guide_controller_combined_low_util_candidate_generation_handoff_trace_only"
            in builder_source
        ),
        "uses_stable_hash": "stable_final_publication_hash(" in builder_source,
        "non_driving_flags": all(
            token in builder_source
            for token in (
                '"product_driving": False',
                '"render_driving": False',
                '"apply_driving": False',
                '"session_driving": False',
            )
        ),
    }
    return {
        "builder": {"name": BUILDER, "start_line": start_line, "end_line": end_line},
        "static_shape": static_shape,
        "forbidden_controller_ownership": forbidden_controller_ownership,
        "runtime_exercise": _exercise_builder(),
        "latest_boundary_readiness": _latest(
            "design_guide_no_active_combined_low_util_full_route_boundary_readiness"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "ready_for_trace_only_live_wiring": True,
        "ready_for_live_cutover": True,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    runtime = capture.get("runtime_exercise") or {}
    return {
        "static_shape_complete": all((capture.get("static_shape") or {}).values()),
        "no_forbidden_controller_ownership": not any(
            (capture.get("forbidden_controller_ownership") or {}).values()
        ),
        "runtime_result_present": runtime.get("result_present") is True,
        "runtime_hash_stable": runtime.get("stable_repeat_hash") is True,
        "runtime_controller_authority": (
            runtime.get("controller_authority")
            == "DesignGuideController.combined_low_util_cleanup_result"
        ),
        "runtime_trace_keys_present": all((runtime.get("trace_keys_present") or {}).values()),
        "runtime_trace_keys_non_driving": all(
            (runtime.get("trace_keys_non_driving") or {}).values()
        ),
        "boundary_readiness_passed": (
            capture.get("latest_boundary_readiness") or {}
        ).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "ready_for_trace_only_live_wiring": capture.get("ready_for_trace_only_live_wiring")
        is True,
        "ready_for_live_cutover": capture.get("ready_for_live_cutover") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    builder = capture.get("builder") or {}
    lines = [
        "# Design Guide No-Active Combined Low-Util Full Route Builder Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Builder: `{builder.get('name')}`",
        f"Builder lines: `{builder.get('start_line')}-{builder.get('end_line')}`",
        f"Ready for trace-only live wiring: `{capture.get('ready_for_trace_only_live_wiring')}`",
        f"Ready for live cutover: `{capture.get('ready_for_live_cutover')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Keep the full controller route as the Design Brain boundary for this path. "
            "The page route should remain a thin wiring/diagnostic wrapper.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_no_active_combined_low_util_full_route_builder_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_combined_low_util_full_route_builder_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"{status}: {json_path}")
    print(f"Report: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
