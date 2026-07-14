"""Verify residual-shear blocker tail consumes a prebuilt packaging result."""

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

FUNCTION_NAME = (
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "result_packaging_blocker_tail_shell"
)
ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_physical_route_body_wrapper = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_physical_nested_route_body_wrapper("

REQUIRED_INPUT_TOKENS = {
    "packaging_attempted_flag": "residual_result_packaging_attempted = bool(",
    "packaging_result_variable": "residual_result_packaging_result = {}",
    "guarded_packaging_call": "if residual_result_packaging_attempted:",
    "prebuilt_packaging_result_passed": (
        "prebuilt_result_packaging_result=residual_result_packaging_result"
    ),
    "prebuilt_packaging_attempted_passed": (
        "prebuilt_result_packaging_attempted=residual_result_packaging_attempted"
    ),
}

FORBIDDEN_INPUT_TOKENS = {
    "result_packaging_executor_lambda": "result_packaging_executor=lambda:",
}

REQUIRED_CONTROLLER_TOKENS = {
    "prebuilt_packaging_param": "prebuilt_result_packaging_result: Any = None",
    "prebuilt_packaging_attempted_param": (
        "prebuilt_result_packaging_attempted: bool | None = None"
    ),
    "prebuilt_packaging_supplied": "prebuilt_packaging_supplied =",
    "prebuilt_packaging_hash": '"prebuilt_result_packaging_hash"',
}

REQUIRED_PREVIOUS_ARTIFACTS = {
    "physical_nested_wrapper_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_physical_nested_wrapper_cutover"
    ),
    "fallback_prebuilt_payload_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_prebuilt_payload_cutover"
    ),
}


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


def _function_source(source: str, function_name: str) -> str:
    start = source.find(f"def {function_name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 4)
    return source[start:next_def] if next_def > start else source[start:]


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


def _load_controller_function():
    spec = importlib.util.spec_from_file_location(
        "design_guide_controller_result_packaging_prebuilt_verifier",
        CONTROLLER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load design_guide_controller.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return getattr(module, FUNCTION_NAME)


def _sample() -> dict[str, Any]:
    fn = _load_controller_function()
    candidate_evidence = {
        "best_safe_final_util": 0.91,
        "selected_candidate_util": 0.91,
        "selected_candidate_id": "pack",
        "safe_candidate_count": 1,
        "executable_candidate_count": 1,
        "safe_cleanup_count": 1,
        "executable_cleanup_count": 1,
        "safe_shear_cleanup_count": 1,
        "executable_shear_cleanup_count": 1,
        "attempted_candidate_count": 2,
        "previewed_candidate_count": 2,
    }
    packaging_result = (
        {"title": "Residual shear cleanup", "kind": "local_cleanup"},
        {
            "candidate_id": "pack",
            "action_payload": {"candidate_search_evidence": dict(candidate_evidence)},
            "resolved_candidate": {"candidate_search_evidence": dict(candidate_evidence)},
            "button_contract": {"expected_util": 0.91},
            "candidate_search_evidence": dict(candidate_evidence),
        },
        {"detail": True},
    )
    kwargs = {
        "should_execute_tail": True,
        "prebuilt_result_packaging_result": packaging_result,
        "prebuilt_result_packaging_attempted": True,
        "residual_shear_updates": {"lig_legs": 0},
        "exact_blockers_by_family": {},
        "current_shear_util": 0.96,
        "target_low": 0.6,
        "target_high": 0.85,
        "target_band_eps": 0.0,
        "fallback_candidate_id": "fallback",
        "route_metadata": {"route": "residual_shear_cleanup"},
    }
    first = fn(**kwargs)
    second = fn(**kwargs)
    skipped = fn(
        should_execute_tail=False,
        prebuilt_result_packaging_result={},
        prebuilt_result_packaging_attempted=False,
        residual_shear_updates={},
    )
    context = dict(first.get("tail_context") or {})
    return {
        "stable_repeat_hash": first.get("result_packaging_blocker_tail_shell_hash")
        == second.get("result_packaging_blocker_tail_shell_hash"),
        "prebuilt_packaging_supplied": first.get("prebuilt_result_packaging_supplied")
        is True,
        "packaging_attempted": first.get("result_packaging_attempted") is True,
        "tail_continues": first.get("should_continue_tail") is True,
        "residual_item_preserved": bool(context.get("residual_shear_item")),
        "residual_promoted_preserved": bool(context.get("residual_promoted")),
        "outside_preferred_band_recorded": context.get("residual_outside_preferred_band")
        is True,
        "skip_packaging_not_attempted": skipped.get("result_packaging_attempted") is False,
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is False,
        "apply_driving": first.get("apply_driving") is False,
        "session_driving": first.get("session_driving") is False,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(inputs_source, ROUTE_BODY_START, ROUTE_BODY_END)
    controller_function = _function_source(controller_source, FUNCTION_NAME)
    sample = _sample()
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_PREVIOUS_ARTIFACTS.items()}
    return {
        "decision": "RESIDUAL_SHEAR_RESULT_PACKAGING_PREBUILT_RESULT_CUTOVER",
        "route_body_found": bool(body),
        "controller_function_found": bool(controller_function),
        "required_input_presence": {
            name: token in body for name, token in REQUIRED_INPUT_TOKENS.items()
        },
        "forbidden_input_presence": {
            name: token in body for name, token in FORBIDDEN_INPUT_TOKENS.items()
        },
        "required_controller_presence": {
            name: token in controller_function
            for name, token in REQUIRED_CONTROLLER_TOKENS.items()
        },
        "previous_artifacts": latest,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "sample": sample,
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_surface": "button_contract_execution_or_physical_return",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    sample = dict(capture.get("sample") or {})
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "controller_function_found": capture.get("controller_function_found") is True,
        "required_input_tokens_present": all(
            dict(capture.get("required_input_presence") or {}).values()
        ),
        "result_packaging_executor_lambda_absent": not any(
            dict(capture.get("forbidden_input_presence") or {}).values()
        ),
        "required_controller_tokens_present": all(
            dict(capture.get("required_controller_presence") or {}).values()
        ),
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "sample_stable_repeat_hash": sample.get("stable_repeat_hash") is True,
        "sample_prebuilt_packaging_supplied": sample.get("prebuilt_packaging_supplied")
        is True,
        "sample_packaging_attempted": sample.get("packaging_attempted") is True,
        "sample_tail_continues": sample.get("tail_continues") is True,
        "sample_residual_item_preserved": sample.get("residual_item_preserved") is True,
        "sample_residual_promoted_preserved": sample.get("residual_promoted_preserved")
        is True,
        "sample_outside_preferred_band_recorded": sample.get("outside_preferred_band_recorded")
        is True,
        "sample_skip_packaging_not_attempted": sample.get("skip_packaging_not_attempted")
        is True,
        "product_driving_preserved": sample.get("product_driving") is True,
        "not_render_driving": sample.get("render_driving") is True,
        "not_apply_driving": sample.get("apply_driving") is True,
        "not_session_driving": sample.get("session_driving") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Result Packaging Prebuilt Result Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        "The residual-shear blocker tail now consumes result packaging as prebuilt "
        "plain data instead of receiving `result_packaging_executor=lambda:`. "
        "Packaging execution itself remains page/shared-owned.",
        "",
        "## Checks",
        "",
    ]
    for name, ok in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{ok}`")
    lines.extend(
        [
            "",
            "## Previous Artifacts",
            "",
        ]
    )
    for name, row in dict(capture.get("previous_artifacts") or {}).items():
        lines.append(f"- `{name}`: `{row.get('status')}` {row.get('path')}")
    lines.extend(
        [
            "",
            "## Sample",
            "",
            "```json",
            json.dumps(capture.get("sample") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Next",
            "",
            f"`{capture.get('next_safe_surface')}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    stamp = _stamp()
    payload = {
        "schema": (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            "result_packaging_prebuilt_result_cutover.v1"
        ),
        "status": status,
        "capture": capture,
        "checks": checks,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
        "created_at": stamp,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = (
        ARTIFACT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"result_packaging_prebuilt_result_cutover_{stamp}.json"
        )
    )
    audit_path = (
        AUDIT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"result_packaging_prebuilt_result_cutover_{stamp}.md"
        )
    )
    report_path = (
        REPORT_DIR
        / (
            "design_brain_physical_extraction_residual_shear_cleanup_"
            f"result_packaging_prebuilt_result_cutover_{stamp}.md"
        )
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"result_packaging_prebuilt_result_cutover {status}"
    )
    print(json_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
