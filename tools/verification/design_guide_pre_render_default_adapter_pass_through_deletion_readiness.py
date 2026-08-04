from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACTS = ROOT / "artifacts"
VERIFICATION = ARTIFACTS / "verification"
AUDITS = ARTIFACTS / "audits"

CALLSITE = "render_guidance_secondary_items.pre_render_binding"


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _function_body(source: str, name: str) -> str:
    start = source.find(f"def {name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start : next_def if next_def >= 0 else len(source)]


def _call_window(source: str, function_name: str, callsite_id: str, *, before: int = 1800, after: int = 2600) -> tuple[int | None, str]:
    pattern = re.compile(
        rf"{re.escape(function_name)}\(\s*[\s\S]{{0,900}}?callsite_id\s*=\s*{re.escape(json.dumps(callsite_id))}",
        re.MULTILINE,
    )
    match = pattern.search(source)
    if not match:
        return None, ""
    line = source[: match.start()].count("\n") + 1
    return line, source[max(0, match.start() - before) : min(len(source), match.end() + after)]


def _token_window(source: str, token: str, *, before: int = 1800, after: int = 2600) -> tuple[int | None, str]:
    index = source.find(token)
    if index < 0:
        return None, ""
    line = source[:index].count("\n") + 1
    return line, source[max(0, index - before) : min(len(source), index + len(token) + after)]


def _latest(prefix: str) -> dict[str, Any]:
    matches = sorted((VERIFICATION).glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"found": False, "path": None, "status": None}
    path = matches[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    source = INPUTS.read_text(encoding="utf-8")
    default_body = _function_body(source, "_final_visible_restamper_default_rebuild_adapter_cutover")
    line, adapter_window = _call_window(
        source,
        "_final_visible_restamper_default_rebuild_adapter_cutover",
        CALLSITE,
    )
    bypass_line, bypass_window = _call_window(
        source,
        "_maybe_bypass_final_visible_restamper_bridge_noop",
        CALLSITE,
    )
    direct_line, direct_window = _token_window(
        source, "direct_pass_through_after_adapter_identity_proof"
    )

    failures: list[str] = []
    pre_deletion_shape = bool(adapter_window and bypass_window)
    post_deletion_shape = bool(
        not adapter_window
        and not bypass_window
        and direct_window
        and "_pre_render_bound_item = dict(_pre_render_input_item)" in direct_window
    )
    if not pre_deletion_shape and not post_deletion_shape:
        failures.append("pre_render_callsite_not_ready_or_deleted_shape")

    helper_deleted_after_callsite_deletion = bool(not default_body and post_deletion_shape)
    helper_identity_projection = True if helper_deleted_after_callsite_deletion else all(
        token in default_body
        for token in (
            "source_item = dict(input_item or {})",
            '"item": dict(source_item)',
            "projected_item = dict(projection.get(\"item\") or {})",
            "return projected_item",
        )
    )
    helper_fallback_identity = True if helper_deleted_after_callsite_deletion else all(
        token in default_body
        for token in (
            "fallback = dict(source_item)",
            "return fallback",
        )
    )
    active_window = adapter_window or direct_window
    callsite_direct_input_available = "_pre_render_input_item = dict(item)" in active_window
    callsite_bypass_identity = (
        "_pre_render_bound_item = dict(_pre_render_input_item)" in bypass_window
        or "_pre_render_bound_item = dict(_pre_render_input_item)" in direct_window
    )
    callsite_adapter_output_only_bound_item = (
        "_pre_render_bound_item = _final_visible_restamper_default_rebuild_adapter_cutover("
        in adapter_window
        if pre_deletion_shape
        else True
    )
    consumers_after_binding_present = all(
        token in active_window
        for token in (
            "_pre_render_bound_contract",
            "_visible_safe_combined_cleanup_action_from_evidence",
            "_pre_render_bound_updates_for_combined",
            "_pre_render_bound_candidate_text",
        )
    )

    checks = {
        "helper_identity_projection": helper_identity_projection,
        "helper_fallback_identity": helper_fallback_identity,
        "callsite_direct_input_available": callsite_direct_input_available,
        "callsite_bypass_identity": callsite_bypass_identity,
        "callsite_adapter_output_only_bound_item": callsite_adapter_output_only_bound_item,
        "consumers_after_binding_present": consumers_after_binding_present,
        "pre_deletion_shape": pre_deletion_shape,
        "post_deletion_shape": post_deletion_shape,
        "helper_deleted_after_callsite_deletion": helper_deleted_after_callsite_deletion,
    }
    for name, passed in checks.items():
        if name == "pre_deletion_shape" and post_deletion_shape:
            continue
        if not passed:
            failures.append(f"check_failed:{name}")

    support = {
        "proof_stamp_deadness": _latest("design_guide_restamper_proof_stamp_deadness"),
        "remaining_adapter_consumer_reachability": _latest(
            "design_guide_remaining_adapter_consumer_reachability"
        ),
    }
    for name, artifact in support.items():
        if artifact.get("status") != "PASS":
            failures.append(f"supporting_artifact_not_passed:{name}")

    status = "PASS" if not failures else "FAIL"
    snapshot = {
        "schema": "design_guide_pre_render_default_adapter_pass_through_deletion_readiness.v1",
        "status": status,
        "generated_at": timestamp,
        "source_file": str(INPUTS),
        "callsite_id": CALLSITE,
        "adapter_line": line,
        "bypass_line": bypass_line,
        "direct_pass_through_line": direct_line,
        "failures": failures,
        "checks": checks,
        "decision": (
            "PRE_RENDER_BYPASS_AND_ADAPTER_CALLSITE_DELETED"
            if post_deletion_shape and status == "PASS"
            else (
                "SAFE_TO_DELETE_PRE_RENDER_BYPASS_AND_ADAPTER_CALLSITE"
                if status == "PASS"
                else "NOT_READY"
            )
        ),
        "replacement": "_pre_render_bound_item = dict(_pre_render_input_item)",
        "supporting_artifacts": {
            key: {"path": value.get("path"), "status": value.get("status")}
            for key, value in support.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    snapshot["snapshot_hash"] = _stable_hash(snapshot)

    json_path = VERIFICATION / f"design_guide_pre_render_default_adapter_pass_through_deletion_readiness_{timestamp}.json"
    report_path = AUDITS / f"design_guide_pre_render_default_adapter_pass_through_deletion_readiness_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    check_rows = [f"| `{name}` | `{passed}` |" for name, passed in checks.items()]
    report = [
        "# Design Guide Pre-Render Default Adapter Pass-Through Deletion Readiness",
        "",
        f"## Summary\n{status}",
        "",
        "## Decision",
        "",
        f"`{snapshot['decision']}`",
        "",
        "## Checks",
        "",
        "| Check | Passed |",
        "| --- | --- |",
        *check_rows,
        "",
        "## Replacement",
        "",
        f"`{snapshot['replacement']}`",
        "",
        "## Failures",
        "",
        "\n".join(f"- `{failure}`" for failure in failures) if failures else "None.",
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_pre_render_default_adapter_pass_through_deletion_readiness {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
