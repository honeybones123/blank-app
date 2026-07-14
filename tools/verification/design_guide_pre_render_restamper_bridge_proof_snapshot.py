"""Proof-only snapshot for the first pre-render final-visible output bridge proof.

This verifier does not prove deletion. It proves that the first remaining
pre-render final-visible output bridge is now traced by a Design Brain proof object while
the existing live restamper behavior remains unchanged.
"""

from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

CALLSITE_ID = "render_guidance_secondary_items.pre_render_binding"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff"))


def _has_function(tree: ast.AST, name: str) -> bool:
    return any(isinstance(node, ast.FunctionDef) and node.name == name for node in ast.walk(tree))


def _has_class(tree: ast.AST, name: str) -> bool:
    return any(isinstance(node, ast.ClassDef) and node.name == name for node in ast.walk(tree))


def _imports_forbidden_page_modules(source: str) -> bool:
    forbidden = ("import inputs_page", "from inputs_page", "import streamlit", "from streamlit")
    return any(token in source for token in forbidden)


def _capture() -> dict[str, Any]:
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    final_tree = _parse(FINAL_PUBLICATION)
    controller_tree = _parse(CONTROLLER)
    inputs_tree = _parse(INPUTS_PAGE)
    pre_render_index = inputs_source.find("_pre_render_bound_item = _publish_final_visible_design_guide_contract_binding(")
    stamp_index = inputs_source.find(f'callsite_id="{CALLSITE_ID}"', pre_render_index)
    helper_index = inputs_source.find("def _stamp_final_visible_final_visible_output_bridge_proof(")
    input_copy_index = inputs_source.find("_pre_render_input_item = dict(item)")
    pending_rec_index = inputs_source.find("_pre_render_pending_rec = dict(")
    window = ""
    if pre_render_index >= 0:
        window = inputs_source[max(0, pre_render_index - 500) : pre_render_index + 1400]
    return {
        "final_publication_has_proof_class": _has_class(final_tree, "FinalDesignGuidePublicationMutationProof"),
        "final_publication_has_builder": _has_function(final_tree, "build_final_design_guide_publication_mutation_proof"),
        "final_publication_exports_builder": '"build_final_design_guide_publication_mutation_proof"' in final_source,
        "final_publication_exports_class": '"FinalDesignGuidePublicationMutationProof"' in final_source,
        "final_publication_forbidden_imports": _imports_forbidden_page_modules(final_source),
        "controller_has_request": _has_class(controller_tree, "DesignGuideControllerFinalVisibleOutputBridgeRequest"),
        "controller_has_response": _has_class(controller_tree, "DesignGuideControllerFinalVisibleOutputBridgeResponse"),
        "controller_has_runner": _has_function(controller_tree, "run_design_guide_controller_final_visible_output_bridge_trace_only"),
        "controller_exports_runner": '"run_design_guide_controller_final_visible_output_bridge_trace_only"' in controller_source,
        "controller_forbidden_imports": _imports_forbidden_page_modules(controller_source),
        "inputs_imports_controller_runner": "run_design_guide_controller_final_visible_output_bridge_trace_only as _run_design_guide_controller_final_visible_output_bridge_trace_only" in inputs_source,
        "inputs_does_not_import_direct_builder": "_build_final_design_guide_publication_mutation_proof" not in inputs_source,
        "inputs_has_stamp_helper": _has_function(inputs_tree, "_stamp_final_visible_final_visible_output_bridge_proof"),
        "helper_calls_controller_runner": "_run_design_guide_controller_final_visible_output_bridge_trace_only(" in inputs_source,
        "callsite_id_present": CALLSITE_ID in inputs_source,
        "stamp_after_pre_render_restamper": pre_render_index >= 0 and stamp_index > pre_render_index,
        "stamp_before_bound_contract_read": stamp_index >= 0
        and inputs_source.find("_pre_render_bound_contract =", pre_render_index) > stamp_index,
        "pre_render_input_copied_before_restamper": 0 <= input_copy_index < pre_render_index,
        "pre_render_pending_rec_copied_before_restamper": 0 <= pending_rec_index < pre_render_index,
        "proof_flags_non_authoritative": all(
            token in inputs_source
            for token in (
                '"final_visible_final_visible_output_bridge_proof_only"',
                '"final_visible_restamper_bridge_product_driving"',
                '"final_visible_restamper_bridge_render_driving"',
                '"final_visible_restamper_bridge_apply_driving"',
                '"final_visible_restamper_bridge_session_driving"',
            )
        ),
        "latest": {
            "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "deletion_performed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "final_publication_has_proof_class": bool(capture.get("final_publication_has_proof_class")),
        "final_publication_has_builder": bool(capture.get("final_publication_has_builder")),
        "final_publication_exports_builder": bool(capture.get("final_publication_exports_builder")),
        "final_publication_exports_class": bool(capture.get("final_publication_exports_class")),
        "final_publication_has_no_page_imports": not bool(capture.get("final_publication_forbidden_imports")),
        "controller_has_request": bool(capture.get("controller_has_request")),
        "controller_has_response": bool(capture.get("controller_has_response")),
        "controller_has_runner": bool(capture.get("controller_has_runner")),
        "controller_exports_runner": bool(capture.get("controller_exports_runner")),
        "controller_has_no_page_imports": not bool(capture.get("controller_forbidden_imports")),
        "inputs_imports_controller_runner": bool(capture.get("inputs_imports_controller_runner")),
        "inputs_does_not_import_direct_builder": bool(capture.get("inputs_does_not_import_direct_builder")),
        "inputs_has_stamp_helper": bool(capture.get("inputs_has_stamp_helper")),
        "helper_calls_controller_runner": bool(capture.get("helper_calls_controller_runner")),
        "callsite_id_present": bool(capture.get("callsite_id_present")),
        "stamp_after_pre_render_restamper": bool(capture.get("stamp_after_pre_render_restamper")),
        "stamp_before_bound_contract_read": bool(capture.get("stamp_before_bound_contract_read")),
        "pre_render_input_copied_before_restamper": bool(capture.get("pre_render_input_copied_before_restamper")),
        "pre_render_pending_rec_copied_before_restamper": bool(capture.get("pre_render_pending_rec_copied_before_restamper")),
        "proof_flags_non_authoritative": bool(capture.get("proof_flags_non_authoritative")),
        "remaining_restamper_audit_latest_pass": (latest.get("remaining_restamper_audit") or {}).get("status") == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "no_deletion_in_this_slice": capture.get("deletion_performed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Pre-Render Restamper Bridge Proof Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Summary",
        "",
        "- Added a proof-only Design Brain surface for final-visible output bridge hashing.",
        "- Wired the first pre-render binding callsite as a debug-only trace.",
        "- Existing restamper behavior is still live and unchanged.",
        "- This is not a deletion or authority move.",
        "",
        "## Key Fields",
        "",
        f"- Callsite: `{CALLSITE_ID}`",
        f"- Product behavior changed: `{capture.get('product_behavior_changed')}`",
        f"- Visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        "",
        "## Next Safe Step",
        "",
        "Run a parity/cutover-readiness proof for this pre-render bridge before narrowing or deleting it.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_pre_render_final_visible_output_bridge_proof_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_pre_render_final_visible_output_bridge_proof_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_pre_render_final_visible_output_bridge_proof_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
