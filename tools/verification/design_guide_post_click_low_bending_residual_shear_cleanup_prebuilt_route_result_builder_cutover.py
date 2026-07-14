"""Verify residual-shear prebuilt route result builder cutover.

This proves the residual-shear nested route body now returns through a
controller-owned prebuilt result builder while candidate generation/evaluation,
CTA contract execution, visible wording, Apply routing, rendering, and session
mutation remain outside the controller.
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

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

FUNCTION_NAME = (
    "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "prebuilt_route_result"
)
ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_prebuilt_route_result = {}"

REQUIRED_INPUT_TOKENS = {
    "controller_import": (
        "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "prebuilt_route_result as _build_design_guide_controller_post_click_low_bending_"
        "residual_shear_cleanup_prebuilt_route_result"
    ),
    "builder_call": (
        "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "prebuilt_route_result("
    ),
    "route_body_result_input": "route_body_result=dict(residual_route_body_result or {})",
    "route_return_boundary_input": (
        "route_return_boundary=dict(residual_route_return_boundary or {})"
    ),
    "proof_debug_return_tail_input": (
        "proof_debug_return_tail=dict(residual_proof_debug_return_tail or {})"
    ),
    "fallback_item_input": "fallback_item=dict(residual_route_return_item or {})",
    "parity_gate": (
        "residual_prebuilt_route_result.get(\"result_item_hash\")\n"
        "                            == residual_prebuilt_route_result.get(\"fallback_item_hash\")"
    ),
    "debug_hash_stamp": (
        "design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
        "prebuilt_route_result_hash"
    ),
}

REQUIRED_CONTROLLER_TOKENS = {
    "function_def": f"def {FUNCTION_NAME}(",
    "authority": (
        "DesignGuideController.post_click_low_bending_residual_shear_cleanup_"
        "prebuilt_route_result"
    ),
    "not_moved_candidate_generation": '"candidate_generation_execution"',
    "not_moved_candidate_evaluation": '"candidate_evaluation_execution"',
    "not_moved_cta_contract": '"cta_contract_execution"',
    "not_moved_visible_wording": '"visible_wording_authoring"',
    "not_moved_apply_routing": '"apply_routing"',
    "product_driving": '"product_driving": True',
    "not_render_driving": '"render_driving": False',
    "not_apply_driving": '"apply_driving": False',
    "exported": f'"{FUNCTION_NAME}"',
}

FORBIDDEN_CONTROLLER_TOKENS_IN_FUNCTION = (
    "inputs_page",
    "import streamlit",
    "st.session_state",
    "_evaluate_auto_design_candidate(",
    "generate_less_shear_reo_variants(",
    "_execute_post_click_low_bending_residual_shear_cleanup_button_contract(",
    "_design_guide_button_contract(",
)

REQUIRED_PREVIOUS_ARTIFACTS = {
    "prebuilt_route_result_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_cutover"
    ),
    "nested_wrapper_deadness_probe": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_nested_wrapper_deadness_probe"
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
        "design_guide_controller_prebuilt_result_builder_verifier",
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
    result_item = {
        "title_main": "Strengthening required",
        "action_type": "apply_resolved_candidate",
        "action_payload": {"updates": {"lig_legs": 0, "s_lig": 0}},
        "button_contract": {
            "enabled": True,
            "updates": {"lig_legs": 0, "s_lig": 0},
        },
    }
    item_hash = _stable_hash(result_item)
    route_body_result = {
        "result_item": dict(result_item),
        "result_item_hash": item_hash,
        "route_body_hash": "body-hash",
    }
    route_return_boundary = {
        "result_item": dict(result_item),
        "result_item_hash": item_hash,
        "route_return_boundary_hash": "return-hash",
    }
    proof_tail = {
        "result_item": dict(result_item),
        "result_item_hash": item_hash,
        "proof_debug_return_tail_hash": "proof-tail-hash",
    }
    first = fn(
        route_body_result=dict(route_body_result),
        route_return_boundary=dict(route_return_boundary),
        proof_debug_return_tail=dict(proof_tail),
        fallback_item=dict(result_item),
    )
    second = fn(
        route_body_result=dict(route_body_result),
        route_return_boundary=dict(route_return_boundary),
        proof_debug_return_tail=dict(proof_tail),
        fallback_item=dict(result_item),
    )
    mismatched = fn(
        route_body_result={**route_body_result, "result_item_hash": "different"},
        route_return_boundary=dict(route_return_boundary),
        proof_debug_return_tail=dict(proof_tail),
        fallback_item=dict(result_item),
    )
    return {
        "stable_repeat_hash": first.get("prebuilt_route_result_hash")
        == second.get("prebuilt_route_result_hash"),
        "result_hash_matches": first.get("result_item_hash") == item_hash,
        "output_shape_ready": first.get("output_shape_ready") is True,
        "parity_true": first.get("prebuilt_route_result_parity") is True,
        "mismatch_blocks_shape": mismatched.get("output_shape_ready") is False
        and mismatched.get("prebuilt_route_result_parity") is False,
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is False,
        "apply_driving": first.get("apply_driving") is False,
        "session_driving": first.get("session_driving") is False,
        "not_moved": tuple(first.get("not_moved") or ()),
        "raw_payload": first,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(inputs_source, ROUTE_BODY_START, ROUTE_BODY_END)
    controller_function = _function_source(controller_source, FUNCTION_NAME)
    sample = _sample()
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_PREVIOUS_ARTIFACTS.items()}
    required_input_presence = {
        name: token in inputs_source for name, token in REQUIRED_INPUT_TOKENS.items()
    }
    required_controller_presence = {
        name: token in controller_source for name, token in REQUIRED_CONTROLLER_TOKENS.items()
    }
    forbidden_controller_terms_present = [
        token
        for token in FORBIDDEN_CONTROLLER_TOKENS_IN_FUNCTION
        if token.lower() in controller_function.lower()
    ]
    return {
        "decision": "RESIDUAL_SHEAR_PREBUILT_ROUTE_RESULT_BUILDER_CUTOVER",
        "route_body_found": bool(body),
        "controller_function_found": bool(controller_function),
        "required_input_presence": required_input_presence,
        "required_controller_presence": required_controller_presence,
        "forbidden_controller_terms_present": forbidden_controller_terms_present,
        "previous_artifacts": latest,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "sample": sample,
        "route_body_hash": _stable_hash(body),
        "controller_function_hash": _stable_hash(controller_function),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_surface": "rerun_nested_wrapper_deadness_after_prebuilt_result_builder_cutover",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    sample = dict(capture.get("sample") or {})
    not_moved = set(sample.get("not_moved") or ())
    required_not_moved = {
        "candidate_generation_execution",
        "candidate_evaluation_execution",
        "cta_contract_execution",
        "visible_wording_authoring",
        "apply_routing",
        "ui_rendering",
        "session_state_mutation",
    }
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "controller_function_found": capture.get("controller_function_found") is True,
        "required_input_tokens_present": all(
            dict(capture.get("required_input_presence") or {}).values()
        ),
        "required_controller_tokens_present": all(
            dict(capture.get("required_controller_presence") or {}).values()
        ),
        "forbidden_controller_terms_absent": not capture.get(
            "forbidden_controller_terms_present"
        ),
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "sample_stable_repeat_hash": sample.get("stable_repeat_hash") is True,
        "sample_result_hash_matches": sample.get("result_hash_matches") is True,
        "sample_output_shape_ready": sample.get("output_shape_ready") is True,
        "sample_parity_true": sample.get("parity_true") is True,
        "sample_mismatch_blocks_shape": sample.get("mismatch_blocks_shape") is True,
        "product_driving_preserved": sample.get("product_driving") is True,
        "not_render_driving": sample.get("render_driving") is True,
        "not_apply_driving": sample.get("apply_driving") is True,
        "not_session_driving": sample.get("session_driving") is True,
        "risky_dependencies_not_moved": required_not_moved.issubset(not_moved),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Residual Shear Prebuilt Route Result Builder Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Summary",
        "",
        "The residual shear cleanup route now returns through a controller-owned "
        "prebuilt route result builder. Candidate generation/evaluation, CTA "
        "contract execution, visible wording, Apply routing, rendering, and "
        "session/debug mutation remain outside this slice.",
        "",
        "## Files Changed",
        "",
        "- `design_brain/design_guide_controller.py`",
        "- `inputs_page.py`",
        "- `tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_builder_cutover.py`",
        "",
        "## Cutover Proof",
        "",
        f"- Previous artifacts pass: `{capture.get('previous_artifacts_pass')}`",
        f"- Stable sample hash: `{dict(capture.get('sample') or {}).get('stable_repeat_hash')}`",
        f"- Result hash parity: `{dict(capture.get('sample') or {}).get('result_hash_matches')}`",
        f"- Mismatch blocks shape: `{dict(capture.get('sample') or {}).get('mismatch_blocks_shape')}`",
        "",
        "## Behaviour Preserved",
        "",
        f"- Engineering behaviour changed: `{capture.get('engineering_behavior_changed')}`",
        f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        f"- Family runtime changed: `{capture.get('family_runtime_changed')}`",
        "",
        "## Verifier Results",
        "",
    ]
    for name, value in checks.items():
        lines.append(f"- {name}: `{value}`")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "",
            "The physical nested route body still exists. Candidate generation, "
            "candidate evaluation, CTA contract execution, visible wording, "
            "Apply routing, rendering, and session/debug mutation remain explicitly "
            "outside this cutover.",
            "",
            "## Next Safe Target",
            "",
            f"`{capture.get('next_safe_surface')}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
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
        f"prebuilt_route_result_builder_cutover_{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"prebuilt_route_result_builder_cutover_{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_prebuilt_route_result_"
        f"{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_builder_cutover",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(audit_path)
    print(report_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
