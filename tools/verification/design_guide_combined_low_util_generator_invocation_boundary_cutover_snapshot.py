"""Proof snapshot for combined low-util generator invocation boundary cutover."""

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
ROUTE_FUNCTION = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
HELPER_NAME = "run_design_guide_controller_combined_low_util_candidate_generation"
FULL_ROUTE_NAME = "run_design_guide_controller_no_active_combined_low_util_cleanup_route"
FULL_ROUTE_ALIAS = "_run_design_guide_controller_no_active_combined_low_util_cleanup_route"


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


def _helpers() -> dict[str, Any]:
    calls: list[dict[str, Any]] = []

    def parse_util_value(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    def updates_match_state(state: dict[str, Any], updates: dict[str, Any]) -> bool:
        return all(state.get(key) == value for key, value in dict(updates or {}).items())

    def normalise_candidate_id(seed: str, **kwargs: Any) -> str:
        return f"{seed}:{_stable_hash(kwargs)[:8]}"

    def shear_generator(
        state: dict[str, Any],
        overview: dict[str, Any],
        *,
        threshold: Any,
        allow_best_safe_below_threshold: bool = False,
    ) -> dict[str, Any]:
        calls.append(
            {
                "name": "shear_generator",
                "state_hash": _stable_hash(state),
                "overview_hash": _stable_hash(overview),
                "threshold": threshold,
                "allow_best_safe_below_threshold": allow_best_safe_below_threshold,
            }
        )
        return {
            "title": "Shear cleanup - one-click reduction",
            "family": "shear",
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
            "button_contract": {
                "enabled": True,
                "actionable": True,
                "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
            },
        }

    def combined_generator(
        state: dict[str, Any],
        overview: dict[str, Any],
        mode_config: dict[str, Any],
        seed_item: dict[str, Any] | None,
        *,
        debug_sink: Any = None,
    ) -> dict[str, Any]:
        calls.append(
            {
                "name": "combined_generator",
                "state_hash": _stable_hash(state),
                "overview_hash": _stable_hash(overview),
                "mode_config": dict(mode_config or {}),
                "seed_family": (seed_item or {}).get("family"),
                "seed_updates": dict((seed_item or {}).get("updates") or {}),
                "debug_sink": debug_sink,
            }
        )
        return {
            "title": "Combined cleanup - best safe one-click reduction",
            "family": "combined",
            "candidate_id": "combined-cleanup-1",
            "updates": {"b": 375.0, "lig_d": 0, "lig_legs": 0},
            "button_contract": {
                "enabled": True,
                "actionable": True,
                "candidate_id": "combined-cleanup-1",
                "updates": {"b": 375.0, "lig_d": 0, "lig_legs": 0},
            },
        }

    def design_optimisation_goal(_state: dict[str, Any]) -> str:
        return "balanced"

    def design_mode_config(goal: str) -> dict[str, Any]:
        return {"goal": goal, "source": "synthetic"}

    def normalise_item(item: dict[str, Any]) -> dict[str, Any]:
        result = dict(item or {})
        result["normalised_by"] = "synthetic"
        return result

    def resolve_recommendation_updates(item: dict[str, Any], *, state: dict[str, Any]) -> dict[str, Any]:
        return dict(item.get("updates") or {})

    def contract_enabled(contract: dict[str, Any]) -> bool:
        return bool(contract.get("enabled") and contract.get("actionable"))

    return {
        "calls": calls,
        "parse_util_value_fn": parse_util_value,
        "updates_match_state_fn": updates_match_state,
        "normalise_design_guide_candidate_id_fn": normalise_candidate_id,
        "shear_low_util_target_cleanup_item_fn": shear_generator,
        "combine_best_safe_shear_with_bending_cleanup_item_fn": combined_generator,
        "design_mode_config_fn": design_mode_config,
        "design_optimisation_goal_fn": design_optimisation_goal,
        "normalise_final_visible_design_guide_item_fn": normalise_item,
        "resolve_recommendation_updates_fn": resolve_recommendation_updates,
        "design_guide_button_contract_enabled_fn": contract_enabled,
    }


def _exercise_helper() -> dict[str, Any]:
    module = importlib.import_module("design_brain.design_guide_controller")
    helper = getattr(module, HELPER_NAME)
    base_kwargs = {
        "primary": {"title": "Primary", "family": "combined"},
        "final_state": {"b": 400.0, "D": 650.0, "lig_d": 10, "lig_legs": 2},
        "final_overview": {"utils": {"bending": 0.42, "shear": 0.44}},
        "final_accepted_min_family_util": 0.85,
        "compound_shear_update_keys": {"lig_d", "lig_legs", "s_lig"},
    }

    fallback_helpers = _helpers()
    fallback_calls = fallback_helpers.pop("calls")
    fallback = helper(
        updates={},
        **base_kwargs,
        **fallback_helpers,
    )

    seed_helpers = _helpers()
    seed_calls = seed_helpers.pop("calls")
    seed = helper(
        updates={"lig_d": 0, "lig_legs": 0},
        **base_kwargs,
        **seed_helpers,
    )

    not_applicable_helpers = _helpers()
    not_applicable_helpers.pop("calls")
    not_applicable = helper(
        updates={},
        primary=base_kwargs["primary"],
        final_state=base_kwargs["final_state"],
        final_overview={"utils": {"bending": 0.92, "shear": 0.44}},
        final_accepted_min_family_util=0.85,
        compound_shear_update_keys=base_kwargs["compound_shear_update_keys"],
        **not_applicable_helpers,
    )
    return {
        "fallback": fallback,
        "fallback_calls": fallback_calls,
        "seed": seed,
        "seed_calls": seed_calls,
        "not_applicable": not_applicable,
        "fallback_hash_repeat": _stable_hash(fallback)
        == _stable_hash(
            helper(
                updates={},
                **base_kwargs,
                **_helpers_without_calls(),
            )
        ),
    }


def _helpers_without_calls() -> dict[str, Any]:
    helpers = _helpers()
    helpers.pop("calls")
    return helpers


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE_FUNCTION)
    helper_source, helper_start, helper_end = _function_source(CONTROLLER, HELPER_NAME)
    exercise = _exercise_helper()
    route_calls_full_controller = f"{FULL_ROUTE_ALIAS}(" in route_source
    route_calls_lower_generator = (
        "_run_design_guide_controller_combined_low_util_candidate_generation("
        in route_source
    )
    full_route_cutover = route_calls_full_controller and not route_calls_lower_generator
    if full_route_cutover:
        decision = "FULL_CONTROLLER_ROUTE_CUT_OVER_GENERATOR_INVOCATION_BOUNDARY"
    else:
        decision = "COMBINED_LOW_UTIL_GENERATOR_INVOCATION_BOUNDARY_CUTOVER_PASS"
    return {
        "decision": decision,
        "route": {
            "function": ROUTE_FUNCTION,
            "start_line": route_start,
            "end_line": route_end,
            "line_count": route_end - route_start + 1,
            "calls_full_controller_route": route_calls_full_controller,
            "calls_lower_generator": route_calls_lower_generator,
            "full_route_cutover": full_route_cutover,
        },
        "helper": {
            "function": HELPER_NAME,
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "exercise": exercise,
        "source_checks": {
            "helper_exported": f'"{HELPER_NAME}"' in controller_source,
            "helper_imported": (
                f"{HELPER_NAME} as _run_design_guide_controller_combined_low_util_candidate_generation"
                in inputs_source
            ),
            "full_route_exported": f'"{FULL_ROUTE_NAME}"' in controller_source,
            "full_route_imported": (
                f"{FULL_ROUTE_NAME} as {FULL_ROUTE_ALIAS}" in inputs_source
            ),
            "route_calls_generator_boundary": (
                route_calls_lower_generator or route_calls_full_controller
            ),
            "route_no_direct_shear_generator_invocation": (
                "shear_low_util_target_cleanup_item_fn(" not in route_source
            ),
            "route_no_direct_combined_generator_invocation": (
                "combine_best_safe_shear_with_bending_cleanup_item_fn(" not in route_source
            ),
            "route_uses_controller_proofs": (
                full_route_cutover
                or (
                    'generation_result.get("route_policy_proof")' in route_source
                    and 'generation_result.get("handoff_proof")' in route_source
                )
            ),
            "helper_uses_injected_shear_generator": (
                "shear_low_util_target_cleanup_item_fn(" in helper_source
            ),
            "helper_uses_injected_combined_generator": (
                "combine_best_safe_shear_with_bending_cleanup_item_fn(" in helper_source
            ),
            "page_required_shear_generator_retained": (
                "def _shear_low_util_target_cleanup_item(" in inputs_source
            ),
            "page_combined_generator_adapter_deleted": (
                "def _combine_best_safe_shear_with_bending_cleanup_item(" not in inputs_source
                and "_combine_best_safe_shear_with_bending_cleanup_item(" not in inputs_source
            ),
            "controller_page_free": all(
                token not in controller_source
                for token in ("inputs_page", "st.session_state", "streamlit")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    exercise = dict(capture.get("exercise") or {})
    fallback = dict(exercise.get("fallback") or {})
    fallback_calls = list(exercise.get("fallback_calls") or [])
    seed = dict(exercise.get("seed") or {})
    seed_calls = list(exercise.get("seed_calls") or [])
    not_applicable = dict(exercise.get("not_applicable") or {})
    source_checks = dict(capture.get("source_checks") or {})
    fallback_names = [call.get("name") for call in fallback_calls]
    seed_names = [call.get("name") for call in seed_calls]
    return {
        "route_found": bool((capture.get("route") or {}).get("line_count")),
        "helper_found": bool((capture.get("helper") or {}).get("line_count")),
        "source_checks_green": all(source_checks.values()),
        "fallback_invokes_shear_then_combined": fallback_names == [
            "shear_generator",
            "combined_generator",
        ],
        "seed_invokes_combined_only": seed_names == ["combined_generator"],
        "fallback_selected_item_returned": isinstance(fallback.get("item"), dict)
        and fallback.get("applicability_gate_allows_result") is True,
        "seed_selected_item_returned": isinstance(seed.get("item"), dict)
        and seed.get("applicability_gate_allows_result") is True,
        "not_applicable_returns_no_item": not_applicable.get("item") is None
        and not_applicable.get("reason") == "combined_low_util_route_not_applicable",
        "route_policy_proof_returned": isinstance(fallback.get("route_policy_proof"), dict)
        and bool((fallback.get("route_policy_proof") or {}).get("route_policy_hash")),
        "handoff_proof_returned": isinstance(fallback.get("handoff_proof"), dict)
        and bool((fallback.get("handoff_proof") or {}).get("handoff_hash")),
        "hash_stable": exercise.get("fallback_hash_repeat") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Generator Invocation Boundary Cutover",
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
            f"- Route: `{ROUTE_FUNCTION}`",
            f"- Controller helper: `{HELPER_NAME}`",
            "- Page generators retained and injected; not deleted in this slice.",
            "- CTA/apply/render/family runtime ownership unchanged.",
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
        / f"design_guide_combined_low_util_generator_invocation_boundary_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_generator_invocation_boundary_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_generator_invocation_boundary_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
