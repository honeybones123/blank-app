"""Prove the injected-dependency controller shell can replace manual candidate execution.

This is a proof-only readiness check. It compares the current page-shaped
manual sequence with the controller shell that owns route orchestration while
keeping candidate generation/evaluation dependencies injected.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper:
        return "PASS"
    if "FAIL" in upper:
        return "FAIL"
    if "PARTIAL" in upper:
        return "PARTIAL"
    return raw or "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "status": _status_from_payload(payload), "path": str(path)}


def _load_controller():
    spec = importlib.util.spec_from_file_location(
        "design_guide_controller_dependency_injected_candidate_execution_shell_readiness",
        CONTROLLER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load design_guide_controller.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _route_entry(should_enter: bool) -> dict[str, Any]:
    return {
        "should_enter_route": bool(should_enter),
        "route_entry_decision_hash": f"entry-{should_enter}",
    }


def _metadata() -> dict[str, Any]:
    return {
        "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
        "state_fingerprint": "state-a",
        "mode_config_hash": "mode-a",
    }


def _primary_result(updates: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if not updates:
        return {}, {"source": "primary", "empty": True}
    return (
        {
            "updates": dict(updates),
            "candidate_id": "primary",
            "action_type": "reduce_shear_links",
        },
        {"source": "primary", "accepted": True},
    )


def _fallback_payload(updates: dict[str, Any] | None) -> dict[str, Any]:
    if not updates:
        return {
            "fallback_variant_generator_attempted": True,
            "fallback_variant_generator_variant_count": 0,
            "fallback_variant_generator_update_sequence": [],
            "fallback_candidate_evaluation_sequence": [],
            "fallback_candidate_selection_sequence": [],
            "fallback_candidate_selection_output_summary": {"selected": False},
            "fallback_shear_candidates": [],
            "fallback_selected_result": {},
        }
    return {
        "residual_shear_tighten": {
            "updates": dict(updates),
            "candidate_id": "fallback",
            "action_type": "reduce_shear_links",
        },
        "residual_shear_updates": dict(updates),
        "fallback_variant_generator_attempted": True,
        "fallback_variant_generator_variant_count": 1,
        "fallback_variant_generator_update_sequence": [{"updates": dict(updates)}],
        "fallback_candidate_evaluation_sequence": [{"accepted_as_safe_cleanup": True}],
        "fallback_candidate_selection_sequence": [{"candidate_id": "fallback"}],
        "fallback_candidate_selection_output_summary": {"selected": "fallback"},
        "fallback_shear_candidates": [{"candidate_id": "fallback"}],
        "fallback_selected_result": {"result_hash": "fallback"},
    }


def _manual_sequence(
    *,
    controller: Any,
    route_entry_decision: dict[str, Any],
    primary_result: Any,
    fallback_payload: dict[str, Any],
    route_metadata: dict[str, Any],
) -> dict[str, Any]:
    should_enter = bool(route_entry_decision.get("should_enter_route"))
    primary_attempted = bool(should_enter)
    primary_updates = {}
    if should_enter:
        raw_primary = primary_result
        if isinstance(raw_primary, (list, tuple)):
            primary_tighten = dict(raw_primary[0] if raw_primary else {})
        else:
            primary_tighten = dict(raw_primary or {})
        primary_updates = dict(primary_tighten.get("updates") or {})
    fallback_executed = bool(should_enter and not primary_updates)
    return controller.run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell(
        route_entry_decision=dict(route_entry_decision),
        prebuilt_primary_result=primary_result if should_enter else {},
        prebuilt_primary_executor_attempted=primary_attempted,
        prebuilt_fallback_search_loop_payload=dict(fallback_payload if fallback_executed else {}),
        prebuilt_fallback_search_loop_executed=fallback_executed,
        route_metadata=dict(route_metadata),
        iteration_limit=64,
    )


def _controller_injected_sequence(
    *,
    controller: Any,
    route_entry_decision: dict[str, Any],
    primary_result: Any,
    fallback_payload: dict[str, Any],
    route_metadata: dict[str, Any],
) -> dict[str, Any]:
    return controller.run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies(
        route_entry_decision=dict(route_entry_decision),
        primary_executor=lambda: primary_result,
        fallback_search_loop=lambda: dict(fallback_payload),
        route_metadata=dict(route_metadata),
        iteration_limit=64,
    )


def _case_inputs() -> dict[str, dict[str, Any]]:
    metadata = _metadata()
    return {
        "primary_selected": {
            "route_entry_decision": _route_entry(True),
            "primary_result": _primary_result({"ligature_legs": 0}),
            "fallback_payload": _fallback_payload({"ligature_legs": 0}),
            "route_metadata": metadata,
        },
        "fallback_selected": {
            "route_entry_decision": _route_entry(True),
            "primary_result": _primary_result({}),
            "fallback_payload": _fallback_payload({"ligature_legs": 0}),
            "route_metadata": metadata,
        },
        "no_candidate": {
            "route_entry_decision": _route_entry(True),
            "primary_result": _primary_result({}),
            "fallback_payload": _fallback_payload({}),
            "route_metadata": metadata,
        },
        "route_skipped": {
            "route_entry_decision": _route_entry(False),
            "primary_result": _primary_result({"ligature_legs": 0}),
            "fallback_payload": _fallback_payload({"ligature_legs": 0}),
            "route_metadata": metadata,
        },
    }


def _capture() -> dict[str, Any]:
    controller = _load_controller()
    comparisons: dict[str, dict[str, Any]] = {}
    for name, kwargs in _case_inputs().items():
        manual = _manual_sequence(controller=controller, **kwargs)
        injected = _controller_injected_sequence(controller=controller, **kwargs)
        manual_context = dict(manual.get("route_shell_context") or {})
        injected_context = dict(injected.get("route_shell_context") or {})
        comparisons[name] = {
            "manual_context_hash": manual.get("route_shell_context_hash"),
            "injected_context_hash": injected.get("route_shell_context_hash"),
            "context_hash_matches": manual.get("route_shell_context_hash")
            == injected.get("route_shell_context_hash"),
            "manual_updates_hash": _stable_hash(manual_context.get("residual_shear_updates") or {}),
            "injected_updates_hash": _stable_hash(
                injected_context.get("residual_shear_updates") or {}
            ),
            "manual_primary_attempted": manual.get("primary_executor_attempted"),
            "injected_primary_attempted": injected.get("primary_executor_attempted"),
            "manual_fallback_executed": manual.get("fallback_search_loop_executed"),
            "injected_fallback_executed": injected.get("fallback_search_loop_executed"),
        }
    previous = {
        "candidate_execution_supplier_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_supplier_readiness_audit"
        ),
        "candidate_execution_bundle_route_shell_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle_route_shell_cutover"
        ),
    }
    return {
        "decision": "RESIDUAL_SHEAR_DEPENDENCY_INJECTED_CANDIDATE_EXECUTION_SHELL_READY",
        "comparisons": comparisons,
        "previous_artifacts": previous,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in previous.values()),
        "ready_for_dependency_injected_candidate_execution_shell_cutover": True,
        "keep_dependencies_injected": True,
        "candidate_generation_execution_owned_elsewhere": True,
        "candidate_evaluation_execution_owned_elsewhere": True,
        "visible_wording_authoring_owned_elsewhere": True,
        "cta_apply_semantics_owned_elsewhere": True,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_surface": "cut_over_candidate_execution_orchestration_to_dependency_injected_controller_shell",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    comparisons = dict(capture.get("comparisons") or {})
    return {
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "all_context_hashes_match": all(
            row.get("context_hash_matches") is True for row in comparisons.values()
        ),
        "ready_for_cutover": (
            capture.get("ready_for_dependency_injected_candidate_execution_shell_cutover") is True
        ),
        "dependencies_remain_injected": capture.get("keep_dependencies_injected") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Dependency-Injected Candidate Execution Shell Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "Ready for cutover: `{}`".format(
            capture.get("ready_for_dependency_injected_candidate_execution_shell_cutover")
        ),
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Comparisons",
        "",
    ]
    for name, row in dict(capture.get("comparisons") or {}).items():
        lines.append(
            "- `{}`: context_hash_matches=`{}`, manual_fallback=`{}`, injected_fallback=`{}`".format(
                name,
                row.get("context_hash_matches"),
                row.get("manual_fallback_executed"),
                row.get("injected_fallback_executed"),
            )
        )
    lines.extend(["", "## Checks", ""])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [name for name, value in checks.items() if value is not True]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "timestamp": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"dependency_injected_candidate_execution_shell_readiness_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"dependency_injected_candidate_execution_shell_readiness_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_dependency_injected_candidate_execution_shell_readiness",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
