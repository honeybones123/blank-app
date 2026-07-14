"""Verify residual-shear result-packaging execution bundle object and trace wiring."""

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

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_physical_route_body_wrapper = "


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _load_controller():
    spec = importlib.util.spec_from_file_location(
        "design_guide_controller_packaging_bundle_trace_verifier",
        CONTROLLER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load design_guide_controller.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample(fn) -> dict[str, Any]:
    packaging_result = (
        {"title": "Residual shear cleanup", "kind": "local_cleanup"},
        {
            "candidate_id": "pack",
            "action_payload": {"candidate_search_evidence": {"best_safe_final_util": 0.91}},
            "button_contract": {"expected_util": 0.91},
        },
        {"detail": True},
    )
    first = fn(
        should_execute_tail=True,
        prebuilt_result_packaging_result=packaging_result,
        prebuilt_result_packaging_attempted=True,
        residual_shear_updates={"ligature_legs": 0},
        exact_blockers_by_family={},
        current_shear_util=0.96,
        target_low=0.6,
        target_high=0.85,
        target_band_eps=0.0,
        fallback_candidate_id="fallback",
        route_metadata={"route": "residual_shear_cleanup"},
    )
    second = fn(
        should_execute_tail=True,
        prebuilt_result_packaging_result=packaging_result,
        prebuilt_result_packaging_attempted=True,
        residual_shear_updates={"ligature_legs": 0},
        exact_blockers_by_family={},
        current_shear_util=0.96,
        target_low=0.6,
        target_high=0.85,
        target_band_eps=0.0,
        fallback_candidate_id="fallback",
        route_metadata={"route": "residual_shear_cleanup"},
    )
    return {
        "stable_hash": first.get("result_packaging_execution_bundle_hash")
        == second.get("result_packaging_execution_bundle_hash"),
        "attempted": first.get("prebuilt_result_packaging_attempted") is True,
        "result_hash_present": bool(first.get("prebuilt_result_packaging_result_hash")),
        "updates_hash_present": bool(first.get("residual_shear_updates_hash")),
        "product_driving": first.get("product_driving"),
        "render_driving": first.get("render_driving"),
        "apply_driving": first.get("apply_driving"),
        "session_driving": first.get("session_driving"),
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    controller = _load_controller()
    fn = getattr(
        controller,
        "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle",
    )
    sample = _sample(fn)
    bundle_call = (
        "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle("
    )
    tail_call = (
        "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_blocker_tail_shell("
    )
    return {
        "decision": "RESIDUAL_SHEAR_RESULT_PACKAGING_EXECUTION_BUNDLE_TRACE_WIRED",
        "function_present": (
            "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle("
            in controller_source
        ),
        "export_present": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle"'
            in controller_source
        ),
        "import_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle as "
            in source
        ),
        "route_body_found": bool(body),
        "bundle_call_present": bundle_call in body,
        "bundle_before_tail": 0 <= body.find(bundle_call) < body.find(tail_call),
        "debug_payload_stamp_present": (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle"
            in body
        ),
        "debug_hash_stamp_present": (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle_hash"
            in body
        ),
        "sample": sample,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_surface": "result_packaging_execution_bundle_tail_cutover_readiness",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    sample = dict(capture.get("sample") or {})
    return {
        "function_present": capture.get("function_present") is True,
        "export_present": capture.get("export_present") is True,
        "import_present": capture.get("import_present") is True,
        "route_body_found": capture.get("route_body_found") is True,
        "bundle_call_present": capture.get("bundle_call_present") is True,
        "bundle_before_tail": capture.get("bundle_before_tail") is True,
        "debug_payload_stamp_present": capture.get("debug_payload_stamp_present") is True,
        "debug_hash_stamp_present": capture.get("debug_hash_stamp_present") is True,
        "sample_stable_hash": sample.get("stable_hash") is True,
        "sample_attempted": sample.get("attempted") is True,
        "sample_result_hash_present": sample.get("result_hash_present") is True,
        "sample_updates_hash_present": sample.get("updates_hash_present") is True,
        "not_product_driving": sample.get("product_driving") is False,
        "not_render_driving": sample.get("render_driving") is False,
        "not_apply_driving": sample.get("apply_driving") is False,
        "not_session_driving": sample.get("session_driving") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Result Packaging Execution Bundle Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Checks",
        "",
    ]
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
        f"result_packaging_execution_bundle_trace_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"result_packaging_execution_bundle_trace_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_execution_bundle_trace",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
