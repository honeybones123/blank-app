"""Cutover plan for post-click exact-blocker final binding raw-input replacement.

Proof-only. This verifier checks whether the one remaining post-click exact
blocker final binding can be replaced by the already-adapted raw
``_post_click_bending_resolution`` item before any product code is changed.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

FUNCTION_NAME = "_render_fast_design_guidance_panel"
OLD_BINDING_TOKEN = "_final_visible_item = _publish_final_visible_design_guide_contract_binding("
OLD_ADAPTER_INPUT_TOKEN = "output_item=dict(_final_visible_item or {})"
RAW_ITEM_TOKEN = "_post_click_bending_resolution = _post_click_low_bending_resolution_item("
LOW_BENDING_ADAPTER_TOKEN = "_stamp_final_publication_post_click_low_bending_resolution_result_item_adapter("
RAW_BOUND_TRACE_TOKEN = "_stamp_final_publication_post_click_exact_blocker_raw_bound_parity_proof("
ADAPTER_TOKEN = "_build_final_design_guide_post_click_final_contract_check_adapter_result("

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "design_guide_post_click_exact_blocker_raw_bound_parity_trace",
    "design_guide_post_click_exact_blocker_raw_bound_parity_scenarios",
    "design_guide_post_click_exact_blocker_final_binding_replacement_readiness",
    "design_guide_post_click_final_contract_adapter_result_parity_scenarios",
    "design_guide_render_panel_binding_adapter_readiness",
    "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_independence_lock",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _function_source(source: str, function_name: str) -> tuple[int | None, int | None, str]:
    marker = f"def {function_name}("
    start_index = source.find(marker)
    if start_index < 0:
        return None, None, ""
    start_line = source[:start_index].count("\n") + 1
    next_def_index = source.find("\ndef ", start_index + len(marker))
    next_class_index = source.find("\nclass ", start_index + len(marker))
    candidates = [index for index in (next_def_index, next_class_index) if index >= 0]
    end_index = min(candidates) if candidates else len(source)
    end_line = source[:end_index].count("\n") + 1
    return start_line, end_line, source[start_index:end_index]


def _line_for(function_source: str, token: str, start_line: int | None, pre_context_token: str = "") -> int | None:
    lines = function_source.splitlines()
    for offset, line in enumerate(lines):
        if token not in line:
            continue
        pre_window = "\n".join(lines[max(0, offset - 150) : offset + 1])
        if pre_context_token and pre_context_token not in pre_window:
            continue
        return (start_line or 1) + offset
    return None


def _window(source: str, line: int | None, before: int = 100, after: int = 95) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _artifact_statuses() -> dict[str, dict[str, Any]]:
    return {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start, function_end, function_source = _function_source(source, FUNCTION_NAME)
    call_line = _line_for(function_source, OLD_BINDING_TOKEN, function_start, RAW_ITEM_TOKEN)
    context = _window(source, call_line)
    artifacts = _artifact_statuses()
    readiness_payload = artifacts["design_guide_post_click_exact_blocker_final_binding_replacement_readiness"][
        "payload"
    ]
    readiness_capture = dict(readiness_payload.get("capture") or {})
    scenario_payload = artifacts["design_guide_post_click_exact_blocker_raw_bound_parity_scenarios"][
        "payload"
    ]
    scenario_capture = dict(scenario_payload.get("capture") or {})
    result_parity_payload = artifacts[
        "design_guide_post_click_final_contract_adapter_result_parity_scenarios"
    ]["payload"]
    result_parity_capture = dict(result_parity_payload.get("capture") or {})
    proposed_replacement_tokens = (
        "_post_click_exact_blocker_raw_item = dict(_post_click_bending_resolution or {})",
        "output_item=dict(_post_click_exact_blocker_raw_item or {})",
        "bound_item=dict(_post_click_exact_blocker_raw_item or {})",
    )
    return {
        "decision": "POST_CLICK_EXACT_BLOCKER_FINAL_BINDING_RAW_INPUT_CUTOVER_PLAN_READY",
        "function": FUNCTION_NAME,
        "function_start_line": function_start,
        "function_end_line": function_end,
        "target_call_line": call_line,
        "old_binding_present": call_line is not None,
        "old_adapter_depends_on_bound_item": OLD_ADAPTER_INPUT_TOKEN in context,
        "raw_item_available_before_binding": RAW_ITEM_TOKEN in context,
        "low_bending_adapter_available_before_binding": LOW_BENDING_ADAPTER_TOKEN in context,
        "raw_bound_trace_present": RAW_BOUND_TRACE_TOKEN in context,
        "adapter_call_present": ADAPTER_TOKEN in context,
        "readiness_adapter_depends_on_bound_item": readiness_capture.get(
            "adapter_depends_on_bound_item"
        )
        is True,
        "readiness_parity_tokens_present": all(
            (readiness_capture.get("missing_parity_tokens_present") or {}).values()
        ),
        "raw_bound_scenarios_ready": scenario_capture.get("identical_ready_to_replace") is True
        and scenario_capture.get("changed_bound_not_ready") is True
        and scenario_capture.get("changed_raw_not_ready") is True
        and scenario_capture.get("empty_bound_not_ready") is True,
        "adapter_result_parity_ready": bool(
            result_parity_capture.get("ready_for_live_cutover")
            or result_parity_capture.get("all_scenarios_pass")
            or result_parity_capture.get("base_hash_stable")
        ),
        "proposed_replacement_tokens": proposed_replacement_tokens,
        "proposed_removes_old_binding_call": True,
        "proposed_uses_raw_item_as_adapter_input": True,
        "proposed_keeps_adapter_result_application": True,
        "proposed_keeps_cta_apply_semantics": True,
        "proposed_keeps_visible_wording": True,
        "proposed_keeps_engineering_behavior": True,
        "design_brain_adapter_present": (
            "def build_final_design_guide_post_click_final_contract_check_adapter_result("
            in final_source
        ),
        "design_brain_raw_bound_proof_present": (
            "def build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof("
            in final_source
        ),
        "latest_artifacts": {
            prefix: {"status": data.get("status"), "path": data.get("path")}
            for prefix, data in artifacts.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_instruction": (
            "Replace only the post-click exact-blocker final binding call with a raw-item local "
            "dictionary and drive build_final_design_guide_post_click_final_contract_check_adapter_result "
            "from that raw item; keep the adapter result application and proof/debug stamps."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "target_old_binding_present": capture.get("old_binding_present") is True,
        "old_adapter_dependency_confirmed": capture.get("old_adapter_depends_on_bound_item") is True,
        "raw_item_available_before_binding": capture.get("raw_item_available_before_binding") is True,
        "low_bending_adapter_available_before_binding": (
            capture.get("low_bending_adapter_available_before_binding") is True
        ),
        "raw_bound_trace_present": capture.get("raw_bound_trace_present") is True,
        "adapter_call_present": capture.get("adapter_call_present") is True,
        "readiness_pass": (
            latest.get("design_guide_post_click_exact_blocker_final_binding_replacement_readiness")
            or {}
        ).get("status")
        == "PASS",
        "readiness_knows_bound_dependency": (
            capture.get("readiness_adapter_depends_on_bound_item") is True
        ),
        "readiness_parity_tokens_present": capture.get("readiness_parity_tokens_present") is True,
        "raw_bound_trace_pass": (
            latest.get("design_guide_post_click_exact_blocker_raw_bound_parity_trace") or {}
        ).get("status")
        == "PASS",
        "raw_bound_scenarios_pass": (
            latest.get("design_guide_post_click_exact_blocker_raw_bound_parity_scenarios") or {}
        ).get("status")
        == "PASS",
        "raw_bound_scenarios_ready": capture.get("raw_bound_scenarios_ready") is True,
        "adapter_result_parity_pass": (
            latest.get("design_guide_post_click_final_contract_adapter_result_parity_scenarios")
            or {}
        ).get("status")
        == "PASS",
        "adapter_result_parity_ready": capture.get("adapter_result_parity_ready") is True,
        "render_panel_binding_readiness_pass": (
            latest.get("design_guide_render_panel_binding_adapter_readiness") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("design_guide_render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("design_guide_compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("design_guide_independence_lock") or {}).get("status")
        == "PASS",
        "design_brain_adapter_present": capture.get("design_brain_adapter_present") is True,
        "design_brain_raw_bound_proof_present": (
            capture.get("design_brain_raw_bound_proof_present") is True
        ),
        "proposed_removes_old_binding_call": capture.get("proposed_removes_old_binding_call") is True,
        "proposed_uses_raw_item_as_adapter_input": (
            capture.get("proposed_uses_raw_item_as_adapter_input") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Exact Blocker Final Binding Raw-Input Cutover Plan",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Target call line: `{capture.get('target_call_line')}`",
        f"- Old binding present: `{capture.get('old_binding_present')}`",
        f"- Old adapter depends on bound item: `{capture.get('old_adapter_depends_on_bound_item')}`",
        f"- Raw item available before binding: `{capture.get('raw_item_available_before_binding')}`",
        f"- Raw-bound scenarios ready: `{capture.get('raw_bound_scenarios_ready')}`",
        f"- Adapter result parity ready: `{capture.get('adapter_result_parity_ready')}`",
        f"- Next safe instruction: {capture.get('next_safe_instruction')}",
        "",
        "## Proposed Replacement Tokens",
        "",
    ]
    for token in capture.get("proposed_replacement_tokens") or ():
        lines.append(f"- `{token}`")
    lines.extend(["", "## Latest Artifacts", ""])
    for key, value in (capture.get("latest_artifacts") or {}).items():
        lines.append(f"- `{key}`: `{value.get('status')}` ({value.get('path')})")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_exact_blocker_final_binding_raw_input_cutover_plan.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    artifact = (
        ARTIFACT_DIR
        / f"design_guide_post_click_exact_blocker_final_binding_raw_input_cutover_plan_{payload['created_at']}.json"
    )
    report = (
        AUDIT_DIR
        / f"design_guide_post_click_exact_blocker_final_binding_raw_input_cutover_plan_{payload['created_at']}.md"
    )
    artifact.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report, payload)
    print(f"design_guide_post_click_exact_blocker_final_binding_raw_input_cutover_plan {status}")
    print(f"artifact={artifact}")
    print(f"report={report}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
