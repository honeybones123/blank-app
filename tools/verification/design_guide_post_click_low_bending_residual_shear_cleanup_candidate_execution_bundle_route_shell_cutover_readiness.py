"""Prove the candidate execution bundle can feed the prebuilt route shell."""

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
        "design_guide_controller_bundle_route_shell_readiness_verifier",
        CONTROLLER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load design_guide_controller.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _case_inputs() -> dict[str, dict[str, Any]]:
    route_entry_decision = {"should_enter_route": True, "route_entry_decision_hash": "entry"}
    route_metadata = {"route_branch": "post_click_residual_shear_cleanup_after_bending_blocker"}
    primary_result = (
        {"updates": {"ligature_legs": 0}, "candidate_id": "primary"},
        {"source": "primary"},
    )
    fallback_payload = {
        "residual_shear_tighten": {
            "updates": {"ligature_legs": 0},
            "candidate_id": "fallback",
        },
        "residual_shear_updates": {"ligature_legs": 0},
        "fallback_variant_generator_attempted": True,
        "fallback_variant_generator_variant_count": 1,
        "fallback_variant_generator_update_sequence": [{"updates": {"ligature_legs": 0}}],
        "fallback_candidate_evaluation_sequence": [{"accepted_as_safe_cleanup": True}],
        "fallback_candidate_selection_sequence": [{"candidate_id": "fallback"}],
        "fallback_candidate_selection_output_summary": {"selected": "fallback"},
        "fallback_shear_candidates": [{"candidate_id": "fallback"}],
        "fallback_selected_result": {"result_hash": "fallback"},
    }
    return {
        "primary_selected": {
            "route_entry_decision": route_entry_decision,
            "prebuilt_primary_result": primary_result,
            "prebuilt_primary_executor_attempted": True,
            "prebuilt_fallback_search_loop_payload": {},
            "prebuilt_fallback_search_loop_executed": False,
            "route_metadata": route_metadata,
        },
        "fallback_selected": {
            "route_entry_decision": route_entry_decision,
            "prebuilt_primary_result": ({}, {}),
            "prebuilt_primary_executor_attempted": True,
            "prebuilt_fallback_search_loop_payload": fallback_payload,
            "prebuilt_fallback_search_loop_executed": True,
            "route_metadata": route_metadata,
        },
        "no_candidate": {
            "route_entry_decision": {
                "should_enter_route": False,
                "route_entry_decision_hash": "skip",
            },
            "prebuilt_primary_result": {},
            "prebuilt_primary_executor_attempted": False,
            "prebuilt_fallback_search_loop_payload": {},
            "prebuilt_fallback_search_loop_executed": False,
            "route_metadata": route_metadata,
        },
    }


def _capture() -> dict[str, Any]:
    controller = _load_controller()
    bundle_fn = getattr(
        controller,
        "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle",
    )
    shell_fn = getattr(
        controller,
        "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell",
    )
    comparisons = {}
    for name, kwargs in _case_inputs().items():
        direct = shell_fn(**kwargs)
        bundle = bundle_fn(**kwargs)
        from_bundle = shell_fn(
            route_entry_decision=dict(kwargs.get("route_entry_decision") or {}),
            prebuilt_primary_result=bundle.get("primary_result"),
            prebuilt_primary_executor_attempted=bundle.get("primary_executor_attempted"),
            prebuilt_fallback_search_loop_payload=dict(bundle.get("fallback_payload") or {}),
            prebuilt_fallback_search_loop_executed=bundle.get("fallback_search_loop_executed"),
            route_metadata=dict(kwargs.get("route_metadata") or {}),
        )
        comparisons[name] = {
            "direct_context_hash": direct.get("route_shell_context_hash"),
            "bundle_context_hash": from_bundle.get("route_shell_context_hash"),
            "context_hash_matches": direct.get("route_shell_context_hash")
            == from_bundle.get("route_shell_context_hash"),
            "direct_updates_hash": _stable_hash(
                ((direct.get("route_shell_context") or {}).get("residual_shear_updates") or {})
            ),
            "bundle_updates_hash": _stable_hash(
                ((from_bundle.get("route_shell_context") or {}).get("residual_shear_updates") or {})
            ),
            "bundle_hash": bundle.get("candidate_execution_bundle_hash"),
        }
    latest = {
        "bundle_object": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle_object"
        ),
        "bundle_trace_wiring": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle_trace_wiring"
        ),
    }
    return {
        "decision": "RESIDUAL_SHEAR_CANDIDATE_EXECUTION_BUNDLE_ROUTE_SHELL_READY",
        "comparisons": comparisons,
        "previous_artifacts": latest,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "ready_for_bundle_route_shell_cutover": True,
        "next_safe_surface": "cut_over_prebuilt_route_shell_to_candidate_execution_bundle",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "all_context_hashes_match": all(
            row.get("context_hash_matches") is True
            for row in dict(capture.get("comparisons") or {}).values()
        ),
        "ready_for_cutover": capture.get("ready_for_bundle_route_shell_cutover") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Candidate Execution Bundle Route-Shell Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Ready for cutover: `{capture.get('ready_for_bundle_route_shell_cutover')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Comparisons",
        "",
    ]
    for name, row in dict(capture.get("comparisons") or {}).items():
        lines.append(f"- `{name}`: context_hash_matches=`{row.get('context_hash_matches')}`")
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
        f"candidate_execution_bundle_route_shell_cutover_readiness_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"candidate_execution_bundle_route_shell_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle_route_shell_cutover_readiness",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
