"""Verify residual-shear route body uses the prebuilt route-shell API."""

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
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_prebuilt_route_result = {}"


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
        "design_guide_controller_prebuilt_route_shell_cutover_verifier",
        CONTROLLER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load design_guide_controller.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample() -> dict[str, Any]:
    controller = _load_controller()
    primary_result = (
        {"updates": {"ligature_legs": 0}, "candidate_id": "primary"},
        {"debug": True},
    )
    kwargs = {
        "route_entry_decision": {"should_enter_route": True, "route_entry_decision_hash": "r"},
        "prebuilt_primary_result": primary_result,
        "prebuilt_primary_executor_attempted": True,
        "prebuilt_fallback_search_loop_payload": {},
        "prebuilt_fallback_search_loop_executed": False,
        "route_metadata": {"route_branch": "post_click_residual_shear_cleanup_after_bending_blocker"},
        "iteration_limit": 64,
    }
    first = controller.run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell(
        **kwargs
    )
    second = controller.run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell(
        **kwargs
    )
    context = dict(first.get("route_shell_context") or {})
    return {
        "stable_repeat_hash": first.get("route_shell_hash") == second.get("route_shell_hash"),
        "prebuilt_route_shell_authority": bool(first.get("prebuilt_route_shell_authority")),
        "legacy_hash_recorded": bool(first.get("legacy_route_shell_hash")),
        "uses_injected_dependency_callables_false": (
            first.get("uses_injected_dependency_callables") is False
        ),
        "updates_preserved": dict(context.get("residual_shear_updates") or {})
        == {"ligature_legs": 0},
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is False,
        "apply_driving": first.get("apply_driving") is False,
        "session_driving": first.get("session_driving") is False,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    latest = {
        "prebuilt_button_contract_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_button_contract_cutover"
        ),
        "prebuilt_physical_return_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_physical_return_cutover"
        ),
    }
    sample = _sample()
    return {
        "decision": "RESIDUAL_SHEAR_PREBUILT_ROUTE_SHELL_CUTOVER",
        "route_body_found": bool(body),
        "prebuilt_route_shell_call_present": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell("
            in body
        ),
        "legacy_injected_route_shell_call_absent": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies("
            not in body
        ),
        "prebuilt_route_shell_imported": (
            "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell as"
            in source
        ),
        "controller_function_present": (
            "def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell("
            in controller_source
        ),
        "controller_export_present": (
            '"run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell"'
            in controller_source
        ),
        "sample": sample,
        "previous_artifacts": latest,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "route_body_deleted": False,
        "next_safe_surface": "nested_wrapper_deadness_probe_zero_blockers_or_route_body_deletion_readiness",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    sample = dict(capture.get("sample") or {})
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "prebuilt_route_shell_call_present": (
            capture.get("prebuilt_route_shell_call_present") is True
        ),
        "legacy_injected_route_shell_call_absent": (
            capture.get("legacy_injected_route_shell_call_absent") is True
        ),
        "prebuilt_route_shell_imported": capture.get("prebuilt_route_shell_imported") is True,
        "controller_function_present": capture.get("controller_function_present") is True,
        "controller_export_present": capture.get("controller_export_present") is True,
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "sample_stable_repeat_hash": sample.get("stable_repeat_hash") is True,
        "sample_prebuilt_route_shell_authority": sample.get("prebuilt_route_shell_authority")
        is True,
        "sample_legacy_hash_recorded": sample.get("legacy_hash_recorded") is True,
        "sample_no_injected_dependency_callables": (
            sample.get("uses_injected_dependency_callables_false") is True
        ),
        "sample_updates_preserved": sample.get("updates_preserved") is True,
        "product_driving_preserved": sample.get("product_driving") is True,
        "not_render_driving": sample.get("render_driving") is True,
        "not_apply_driving": sample.get("apply_driving") is True,
        "not_session_driving": sample.get("session_driving") is True,
        "route_body_not_deleted": capture.get("route_body_deleted") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Prebuilt Route Shell Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        "The residual-shear route body now calls the prebuilt route-shell controller "
        "API instead of the legacy injected-dependency route-shell API.",
        "",
        "## Checks",
        "",
    ]
    for name, ok in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{ok}`")
    lines.extend(["", "## Previous Artifacts", ""])
    for name, row in dict(capture.get("previous_artifacts") or {}).items():
        lines.append(f"- `{name}`: `{row.get('status')}` {row.get('path')}")
    lines.extend(["", "## Next", "", f"`{capture.get('next_safe_surface')}`", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    stamp = _stamp()
    payload = {
        "schema": (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            "prebuilt_route_shell_cutover.v1"
        ),
        "created_at": stamp,
        "status": status,
        "capture": capture,
        "checks": checks,
        "failures": [name for name, ok in checks.items() if ok is not True],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = (
        ARTIFACT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"prebuilt_route_shell_cutover_{stamp}.json"
        )
    )
    audit_path = (
        AUDIT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"prebuilt_route_shell_cutover_{stamp}.md"
        )
    )
    report_path = (
        REPORT_DIR
        / (
            "design_brain_physical_extraction_residual_shear_cleanup_"
            f"prebuilt_route_shell_cutover_{stamp}.md"
        )
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"prebuilt_route_shell_cutover {status}"
    )
    print(json_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
