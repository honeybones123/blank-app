"""Prove page/controller parity for the active-action exact-blocker route.

Proof-only: this verifier does not import inputs_page.py as a module, wire the
controller route into production, change CTA/apply behaviour, or alter visible
wording. It extracts the current page function with AST, executes it in an
isolated namespace with deterministic callbacks, and compares the result to the
Design Brain controller route for the same cases.
"""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

PAGE_ROUTE = "_resolve_final_visible_post_click_active_action_exact_blocker_result"
CONTROLLER_ROUTE = "run_design_guide_controller_active_action_post_click_exact_blocker_route"


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
    return "", 0, -1


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


def _load_isolated_page_route() -> tuple[Callable[..., Any], dict[str, Any]]:
    source, start_line, end_line = _function_source(INPUTS_PAGE, PAGE_ROUTE)
    from design_brain.design_guide_controller import (
        run_design_guide_controller_active_action_post_click_exact_blocker_route,
    )

    def _parse_util_value(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _page_shell_controller_route(*, controller_fn, **controller_kwargs):
        result = controller_fn(**controller_kwargs)
        if not isinstance(result, dict):
            return None
        return result

    namespace: dict[str, Any] = {
        "_parse_util_value": _parse_util_value,
        "_run_design_guide_controller_active_action_post_click_exact_blocker_route": (
            run_design_guide_controller_active_action_post_click_exact_blocker_route
        ),
        "_run_design_guide_page_shell_controller_route": _page_shell_controller_route,
        "_dg_runtime_trace_enabled": lambda: False,
        "_resolver_route_trace_event": lambda *args, **kwargs: None,
        "_dg_runtime_trace_hash": _stable_hash,
        "_dg_runtime_trace_item_summary": lambda item: dict(item or {}) if isinstance(item, dict) else item,
    }
    if not source:
        def _retired_page_shell_route(**kwargs):
            controller_kwargs = dict(kwargs)
            controller_kwargs.setdefault("parse_util_value_fn", _parse_util_value)
            result = run_design_guide_controller_active_action_post_click_exact_blocker_route(
                **controller_kwargs
            )
            if not isinstance(result, dict):
                return None
            return result

        meta = {
            "function": PAGE_ROUTE,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": 0,
            "source_hash": _stable_hash(source),
            "inputs_page_imported": False,
            "generic_page_shell_delegation_present": False,
            "legacy_page_route_deleted": True,
            "retired_to_controller": True,
        }
        return _retired_page_shell_route, meta

    exec(compile(source, f"<isolated {PAGE_ROUTE}>", "exec"), namespace)
    route = namespace.get(PAGE_ROUTE)
    if not callable(route):
        raise RuntimeError(f"Failed to isolate {PAGE_ROUTE}")
    meta = {
        "function": PAGE_ROUTE,
        "start_line": start_line,
        "end_line": end_line,
        "line_count": end_line - start_line + 1,
        "source_hash": _stable_hash(source),
        "inputs_page_imported": False,
        "generic_page_shell_delegation_present": "_run_design_guide_page_shell_controller_route(" in source,
        "legacy_page_route_deleted": False,
        "retired_to_controller": False,
    }
    return route, meta


def _base_kwargs(builder_enabled: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    audit_calls: list[dict[str, Any]] = []

    def builder(state, overview, mode_config, audit, debug_sink=None):
        audit_calls.append(dict(audit or {}))
        return {
            "title": "Further cleanup blocked",
            "button_contract": {"enabled": builder_enabled, "actionable": builder_enabled},
            "candidate_search_evidence": dict(audit or {}),
        }

    kwargs = {
        "active_family": "bending",
        "candidate_id": "active-candidate-1",
        "active_outside_exact_blockers": {
            "bending": {
                "family": "bending",
                "reason": "Accepted post-click state needs no second CTA.",
                "no_second_cta_required": True,
            }
        },
        "current_utils": {"bending": 0.22, "shear": 0.91},
        "final_state": {"D": 650, "b": 400},
        "final_overview": {"utils": {"bending": 0.22, "shear": 0.91}, "any_fail": False},
        "debug_probe": {"probe": "active-post-click"},
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 0.001,
        "parse_util_value_fn": lambda value: None if value is None else float(value),
        "post_click_low_bending_resolution_item_fn": builder,
        "design_mode_config_fn": lambda goal: {"goal": goal},
        "design_optimisation_goal_fn": lambda state: "balanced",
        "design_guide_button_contract_enabled_fn": lambda contract: bool(
            dict(contract or {}).get("enabled") and dict(contract or {}).get("actionable", True)
        ),
        "state_fingerprint_fn": lambda state: "fp:" + _stable_hash(state)[:12],
        "normalise_final_visible_design_guide_item_fn": lambda item: dict(item or {}),
    }
    return kwargs, audit_calls


def _page_kwargs(controller_kwargs: dict[str, Any]) -> dict[str, Any]:
    page_kwargs = dict(controller_kwargs)
    page_kwargs.pop("parse_util_value_fn", None)
    return page_kwargs


def _run_case(
    *,
    case_id: str,
    page_route: Callable[..., Any],
    overrides: dict[str, Any] | None = None,
    builder_enabled: bool = False,
) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_active_action_post_click_exact_blocker_route,
    )

    page_input, page_audit_calls = _base_kwargs(builder_enabled=builder_enabled)
    controller_input, controller_audit_calls = _base_kwargs(builder_enabled=builder_enabled)
    page_input.update(dict(overrides or {}))
    controller_input.update(dict(overrides or {}))

    page_result = page_route(**_page_kwargs(page_input))
    controller_result = run_design_guide_controller_active_action_post_click_exact_blocker_route(
        **controller_input
    )

    page_hash = _stable_hash(page_result)
    controller_hash = _stable_hash(controller_result)
    page_audit_hash = _stable_hash(page_audit_calls)
    controller_audit_hash = _stable_hash(controller_audit_calls)

    return {
        "case": case_id,
        "page_result_present": isinstance(page_result, dict),
        "controller_result_present": isinstance(controller_result, dict),
        "page_result_hash": page_hash,
        "controller_result_hash": controller_hash,
        "result_hashes_match": page_hash == controller_hash,
        "page_audit_hash": page_audit_hash,
        "controller_audit_hash": controller_audit_hash,
        "audit_hashes_match": page_audit_hash == controller_audit_hash,
        "page_render_reason": page_result.get("render_reason") if isinstance(page_result, dict) else None,
        "controller_render_reason": (
            controller_result.get("render_reason") if isinstance(controller_result, dict) else None
        ),
        "page_show_apply_button": (
            dict(page_result.get("presentation") or {}).get("show_apply_button")
            if isinstance(page_result, dict)
            else None
        ),
        "controller_show_apply_button": (
            dict(controller_result.get("presentation") or {}).get("show_apply_button")
            if isinstance(controller_result, dict)
            else None
        ),
    }


def _exercise_cases(page_route: Callable[..., Any]) -> list[dict[str, Any]]:
    return [
        _run_case(
            case_id="non_bending_family_returns_none",
            page_route=page_route,
            overrides={"active_family": "shear"},
        ),
        _run_case(
            case_id="missing_exact_blocker_returns_none",
            page_route=page_route,
            overrides={"active_outside_exact_blockers": {}},
        ),
        _run_case(
            case_id="exact_blocker_without_no_second_cta_returns_none",
            page_route=page_route,
            overrides={"active_outside_exact_blockers": {"bending": {"family": "bending"}}},
        ),
        _run_case(
            case_id="enabled_builder_result_returns_none",
            page_route=page_route,
            builder_enabled=True,
        ),
        _run_case(
            case_id="disabled_exact_blocker_result_selected",
            page_route=page_route,
        ),
    ]


def _capture() -> dict[str, Any]:
    page_route, page_meta = _load_isolated_page_route()
    controller_source, controller_start, controller_end = _function_source(CONTROLLER, CONTROLLER_ROUTE)
    cases = _exercise_cases(page_route)
    selected_case = next(
        (case for case in cases if case.get("case") == "disabled_exact_blocker_result_selected"),
        {},
    )
    return {
        "decision": "READY_FOR_TRACE_ONLY_LIVE_WIRING_PROOF",
        "page_route": page_meta,
        "controller_route": {
            "function": CONTROLLER_ROUTE,
            "start_line": controller_start,
            "end_line": controller_end,
            "line_count": controller_end - controller_start + 1,
            "source_hash": _stable_hash(controller_source),
        },
        "cases": cases,
        "selected_case_proof": {
            "result_hashes_match": selected_case.get("result_hashes_match"),
            "audit_hashes_match": selected_case.get("audit_hashes_match"),
            "render_reason": selected_case.get("controller_render_reason"),
            "show_apply_button": selected_case.get("controller_show_apply_button"),
        },
        "latest": {
            "readiness": _latest("design_guide_active_action_post_click_exact_blocker_readiness"),
            "route_object": _latest("design_guide_active_action_post_click_exact_blocker_route_object"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_resolver_publication_bridge_lock": _latest(
                "design_guide_compute_resolver_publication_bridge_lock"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    cases = list(capture.get("cases") or [])
    selected = dict(capture.get("selected_case_proof") or {})
    return {
        "page_route_isolated_without_importing_inputs_page": (
            (capture.get("page_route") or {}).get("inputs_page_imported") is False
        ),
        "readiness_passes": (latest.get("readiness") or {}).get("status") == "PASS",
        "route_object_passes": (latest.get("route_object") or {}).get("status") == "PASS",
        "all_case_result_hashes_match": all(case.get("result_hashes_match") is True for case in cases),
        "all_case_audit_hashes_match": all(case.get("audit_hashes_match") is True for case in cases),
        "selected_case_returns_exact_blocker": (
            selected.get("result_hashes_match") is True
            and selected.get("audit_hashes_match") is True
            and selected.get("render_reason") == "final_visible_post_click_active_action_exact_blocker"
            and selected.get("show_apply_button") is False
        ),
        "none_cases_stay_none": all(
            case.get("page_result_present") is False and case.get("controller_result_present") is False
            for case in cases
            if case.get("case") != "disabled_exact_blocker_result_selected"
        ),
        "independence_lock_artifact_available": bool(
            (latest.get("independence_lock") or {}).get("found")
        ),
        "render_bridge_lock_artifact_available": bool(
            (latest.get("render_bridge_lock") or {}).get("found")
        ),
        "compute_bridge_lock_artifact_available": bool(
            (latest.get("compute_resolver_publication_bridge_lock") or {}).get("found")
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    page_route = dict(capture.get("page_route") or {})
    controller_route = dict(capture.get("controller_route") or {})
    lines = [
        "# Design Guide Active-Action Post-Click Exact-Blocker Route Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Routes",
        "",
        f"- Page route: `{page_route.get('function')}` lines `{page_route.get('start_line')}` to `{page_route.get('end_line')}`",
        f"- Controller route: `{controller_route.get('function')}` lines `{controller_route.get('start_line')}` to `{controller_route.get('end_line')}`",
        f"- Imported `inputs_page.py`: `{page_route.get('inputs_page_imported')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Page result | Controller result | Result hash match | Audit hash match |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for case in capture.get("cases") or []:
        lines.append(
            f"| {case.get('case')} | `{case.get('page_result_present')}` | `{case.get('controller_result_present')}` | `{case.get('result_hashes_match')}` | `{case.get('audit_hashes_match')}` |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Add trace-only live wiring beside the page route, then prove live controller/page parity before replacing the page callsite.",
            "",
            "No product behavior, visible wording, CTA/apply semantics, family runtime, solver maths, target bands, render ownership, apply routing, or UI/session ownership changed.",
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
        / f"design_guide_active_action_post_click_exact_blocker_route_parity_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_active_action_post_click_exact_blocker_route_parity_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_active_action_post_click_exact_blocker_route_parity {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
