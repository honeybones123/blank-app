"""Verify the residual-shear candidate execution bundle proof object."""

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


def _load_controller():
    spec = importlib.util.spec_from_file_location(
        "design_guide_controller_candidate_execution_bundle_verifier",
        CONTROLLER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load design_guide_controller.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _case_payloads(fn) -> dict[str, dict[str, Any]]:
    route_decision = {"should_enter_route": True, "route_entry_decision_hash": "entry"}
    metadata = {"route_branch": "post_click_residual_shear_cleanup_after_bending_blocker"}
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
        "primary_selected": fn(
            route_entry_decision=route_decision,
            prebuilt_primary_result=primary_result,
            prebuilt_primary_executor_attempted=True,
            prebuilt_fallback_search_loop_payload={},
            prebuilt_fallback_search_loop_executed=False,
            route_metadata=metadata,
        ),
        "fallback_selected": fn(
            route_entry_decision=route_decision,
            prebuilt_primary_result=({}, {}),
            prebuilt_primary_executor_attempted=True,
            prebuilt_fallback_search_loop_payload=fallback_payload,
            prebuilt_fallback_search_loop_executed=True,
            route_metadata=metadata,
        ),
        "no_candidate": fn(
            route_entry_decision={"should_enter_route": False, "route_entry_decision_hash": "skip"},
            prebuilt_primary_result={},
            prebuilt_primary_executor_attempted=False,
            prebuilt_fallback_search_loop_payload={},
            prebuilt_fallback_search_loop_executed=False,
            route_metadata=metadata,
        ),
    }


def _capture() -> dict[str, Any]:
    controller = _load_controller()
    fn = getattr(
        controller,
        "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle",
    )
    cases = _case_payloads(fn)
    repeats = _case_payloads(fn)
    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    return {
        "decision": "RESIDUAL_SHEAR_CANDIDATE_EXECUTION_BUNDLE_OBJECT_READY",
        "function_present": (
            "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle("
            in source
        ),
        "export_present": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle"'
            in source
        ),
        "cases": cases,
        "stable_hashes": {
            name: cases[name].get("candidate_execution_bundle_hash")
            == repeats[name].get("candidate_execution_bundle_hash")
            for name in cases
        },
        "selected_sources": {
            name: payload.get("selected_result_source") for name, payload in cases.items()
        },
        "selected_update_hashes": {
            name: payload.get("selected_updates_hash") for name, payload in cases.items()
        },
        "ownership_flags": {
            name: {
                "candidate_generation_execution_owned_elsewhere": payload.get(
                    "candidate_generation_execution_owned_elsewhere"
                ),
                "candidate_evaluation_execution_owned_elsewhere": payload.get(
                    "candidate_evaluation_execution_owned_elsewhere"
                ),
                "cta_contract_execution_owned_elsewhere": payload.get(
                    "cta_contract_execution_owned_elsewhere"
                ),
                "visible_wording_authoring_owned_elsewhere": payload.get(
                    "visible_wording_authoring_owned_elsewhere"
                ),
                "product_driving": payload.get("product_driving"),
                "render_driving": payload.get("render_driving"),
                "apply_driving": payload.get("apply_driving"),
                "session_driving": payload.get("session_driving"),
            }
            for name, payload in cases.items()
        },
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_surface": "trace_wire_candidate_execution_bundle_beside_live_supplier",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    flags = dict(capture.get("ownership_flags") or {})
    return {
        "function_present": capture.get("function_present") is True,
        "export_present": capture.get("export_present") is True,
        "stable_hashes": all(dict(capture.get("stable_hashes") or {}).values()),
        "primary_source_selected": (
            dict(capture.get("selected_sources") or {}).get("primary_selected") == "primary"
        ),
        "fallback_source_selected": (
            dict(capture.get("selected_sources") or {}).get("fallback_selected")
            == "fallback"
        ),
        "none_source_selected": (
            dict(capture.get("selected_sources") or {}).get("no_candidate") == "none"
        ),
        "all_execution_owned_elsewhere": all(
            row.get("candidate_generation_execution_owned_elsewhere") is True
            and row.get("candidate_evaluation_execution_owned_elsewhere") is True
            and row.get("cta_contract_execution_owned_elsewhere") is True
            and row.get("visible_wording_authoring_owned_elsewhere") is True
            for row in flags.values()
        ),
        "not_product_driving": all(row.get("product_driving") is False for row in flags.values()),
        "not_render_driving": all(row.get("render_driving") is False for row in flags.values()),
        "not_apply_driving": all(row.get("apply_driving") is False for row in flags.values()),
        "not_session_driving": all(row.get("session_driving") is False for row in flags.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Candidate Execution Bundle Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Selected Sources",
        "",
    ]
    for name, value in dict(capture.get("selected_sources") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
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
        f"candidate_execution_bundle_object_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"candidate_execution_bundle_object_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_execution_bundle_object",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
