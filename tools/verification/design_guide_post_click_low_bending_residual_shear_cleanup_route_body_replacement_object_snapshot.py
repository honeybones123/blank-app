"""Object snapshot for residual-shear cleanup route body replacement proof."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEPENDENCIES = (
    "route_entry_guard",
    "primary_executor_handoff",
    "primary_executor_dependency_boundary",
    "fallback_variant_generator_handoff",
    "fallback_variant_generator_dependency_boundary",
    "candidate_evaluator_handoff",
    "materiality_safety_handoff",
    "candidate_selector_handoff",
    "result_packaging_handoff",
    "evidence_merge_tail",
    "final_binding_tail",
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_block(source: str) -> str:
    start = source.find(
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement("
    )
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _fixture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement,
    )

    result_item = {
        "title": "Design is efficient",
        "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
        "action_type": "apply_resolved_candidate",
        "updates": {"lig_legs": 0, "s_lig": 0},
        "candidate_search_evidence": {
            "post_click_residual_shear_cleanup_after_bending_blocker": True,
            "no_second_cta_required": True,
        },
    }
    shell = {
        "route_shell_adapter_hash": "route-shell-fixture-hash",
        "result_item": dict(result_item),
        "result_item_hash": _stable_hash(result_item),
    }
    dependency_payloads = {
        name: {"name": name, "hash": f"{name}-hash", "proof_only": True}
        for name in DEPENDENCIES
    }
    page_live = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(
        route_shell_adapter=dict(shell),
        residual_promoted=dict(result_item),
        dependency_status={name: "page_live" for name in DEPENDENCIES},
        **dependency_payloads,
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(
        route_shell_adapter=dict(shell),
        residual_promoted=dict(result_item),
        dependency_status={name: "page_live" for name in DEPENDENCIES},
        **dependency_payloads,
    )
    controller_owned = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(
        route_shell_adapter=dict(shell),
        residual_promoted=dict(result_item),
        dependency_status={name: "controller_owned" for name in DEPENDENCIES},
        **dependency_payloads,
    )
    return {
        "result_item": result_item,
        "page_live": page_live,
        "repeat": repeat,
        "controller_owned": controller_owned,
    }


def _capture() -> dict[str, Any]:
    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    block = _function_block(source)
    fixture = _fixture()
    page_live = dict(fixture.get("page_live") or {})
    repeat = dict(fixture.get("repeat") or {})
    controller_owned = dict(fixture.get("controller_owned") or {})
    forbidden_terms = (
        "inputs_page",
        "streamlit",
        "st.session_state",
        "st.button",
        "render_html",
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_ROUTE_BODY_REPLACEMENT_OBJECT_PROVEN",
        "function_present": bool(block),
        "exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement"'
            in source
        ),
        "stable_repeat_hash": page_live.get("route_body_replacement_hash")
        == repeat.get("route_body_replacement_hash"),
        "result_item_hash_matches_input": page_live.get("result_item_hash")
        == _stable_hash(fixture.get("result_item")),
        "dependency_hashes_present": set(page_live.get("dependency_hashes") or {}) == set(DEPENDENCIES),
        "page_live_behavior_cutover_false": page_live.get("behavior_cutover_ready") is False,
        "controller_owned_behavior_cutover_true": controller_owned.get("behavior_cutover_ready")
        is True,
        "output_shape_ready": page_live.get("output_shape_ready") is True,
        "proof_only": page_live.get("proof_only") is True,
        "non_driving_flags": all(
            page_live.get(key) is False
            for key in ("product_driving", "render_driving", "apply_driving", "session_driving")
        ),
        "forbidden_page_terms_absent": not any(
            term.lower() in block.lower() for term in forbidden_terms
        ),
        "raw_page_live": page_live,
        "raw_controller_owned": controller_owned,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "result_item_hash_matches_input": capture.get("result_item_hash_matches_input") is True,
        "dependency_hashes_present": capture.get("dependency_hashes_present") is True,
        "page_live_behavior_cutover_false": capture.get("page_live_behavior_cutover_false") is True,
        "controller_owned_behavior_cutover_true": (
            capture.get("controller_owned_behavior_cutover_true") is True
        ),
        "output_shape_ready": capture.get("output_shape_ready") is True,
        "proof_only": capture.get("proof_only") is True,
        "non_driving_flags": capture.get("non_driving_flags") is True,
        "forbidden_page_terms_absent": capture.get("forbidden_page_terms_absent") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Body Replacement Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Stable repeat hash: `{capture.get('stable_repeat_hash')}`",
        f"- Output shape ready: `{capture.get('output_shape_ready')}`",
        f"- Page-live behavior cutover false: `{capture.get('page_live_behavior_cutover_false')}`",
        f"- Controller-owned behavior cutover true: `{capture.get('controller_owned_behavior_cutover_true')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Trace-wire this object beside the live route body before any cutover or deletion.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_object_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_object_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_object_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_body_replacement_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_replacement_object "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
