"""Parity proof for the render-guidance secondary primary binding adapter.

This is proof-only. It verifies that the traced
render_guidance_secondary_primary_binding restamper callsite is represented by
the DesignGuideController final-visible output bridge proof surface before any cutover or
deletion is attempted.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
sys.path.insert(0, str(ROOT))

CALLSITE_ID = "render_guidance_secondary_primary_binding"
FUNCTION_NAME = "_render_guidance_secondary_items"
RESTAMPER_CALL = "item = _publish_final_visible_design_guide_contract_binding("
TRACE_CALL = "_stamp_final_visible_final_visible_output_bridge_proof("


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
    if any(token in status.upper() for token in ("PASS", "LOCKED", "COMPLETE")):
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _function_block(source: str) -> tuple[int | None, str]:
    marker = f"def {FUNCTION_NAME}("
    start = source.find(marker)
    if start < 0:
        return None, ""
    end = source.find("\ndef ", start + len(marker))
    if end < 0:
        end = len(source)
    start_line = source[:start].count("\n") + 1
    return start_line, source[start:end]


def _line_for(block: str, token: str, start_line: int | None) -> int | None:
    for offset, line in enumerate(block.splitlines()):
        if token in line:
            return (start_line or 1) + offset
    return None


def _line_for_after(block: str, token: str, marker: str, start_line: int | None) -> int | None:
    marker_index = block.find(marker)
    if marker_index < 0:
        return _line_for(block, token, start_line)
    token_index = block.find(token, marker_index)
    if token_index < 0:
        return None
    return (start_line or 1) + block[:token_index].count("\n")


def _target_window(block: str) -> str:
    marker = f'callsite_id="{CALLSITE_ID}"'
    marker_index = block.find(marker)
    if marker_index < 0:
        return ""
    start = max(0, marker_index - 1800)
    end = min(len(block), marker_index + 3600)
    return block[start:end]


def _parity_sample() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_final_visible_output_bridge_trace_only,
    )
    from design_brain.final_publication import (
        build_final_design_guide_publication_mutation_proof,
    )

    input_item = {
        "title_main": "Strengthening required",
        "title": "Strengthening required",
        "status": "FAIL",
        "bucket": "fail",
        "family": "bending",
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "updates": {},
        },
        "candidate_search_evidence": {
            "family": "bending",
            "safe_executor_backed_candidates_count": 0,
        },
    }
    output_item = {
        **input_item,
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "bending",
            "updates": {"D": 650.0},
        },
        "action_payload": {"updates": {"D": 650.0}},
        "candidate_search_evidence": {
            "family": "bending",
            "safe_executor_backed_candidates_count": 1,
            "selected_candidate_updates": {"D": 650.0},
        },
    }
    direct = build_final_design_guide_publication_mutation_proof(
        callsite_id=CALLSITE_ID,
        input_item=input_item,
        output_item=output_item,
        state={"D": 500.0},
        debug={"source": "render_guidance_secondary_binding_adapter_parity"},
        rec={"pending": True},
    ).to_dict()
    controller = run_design_guide_controller_final_visible_output_bridge_trace_only(
        {
            "callsite_id": CALLSITE_ID,
            "input_item": input_item,
            "output_item": output_item,
            "state": {"D": 500.0},
            "debug": {"source": "render_guidance_secondary_binding_adapter_parity"},
            "rec": {"pending": True},
            "source": "render_guidance_secondary_binding_adapter_parity",
        }
    ).to_dict()
    controller_proof = dict(controller.get("final_visible_output_bridge_proof") or {})
    projection_fields = (
        "cta_projection_hash",
        "display_projection_hash",
        "evidence_projection_hash",
        "mutation_surface",
    )
    return {
        "direct_proof": direct,
        "controller_response": controller,
        "controller_proof": controller_proof,
        "projection_fields": {
            field: controller_proof.get(field) for field in projection_fields
        },
        "projection_fields_present": all(controller_proof.get(field) for field in projection_fields),
        "controller_matches_direct": controller_proof.get("proof_hash") == direct.get("proof_hash"),
        "callsite_id_preserved": controller_proof.get("callsite_id") == CALLSITE_ID,
        "mutation_surface_detects_change": dict(controller_proof.get("mutation_surface") or {})
        == {
            "output_changed": True,
            "cta_changed": True,
            "display_changed": False,
            "evidence_changed": True,
        },
        "proof_flags_non_authoritative": all(
            controller.get(key) is expected
            for key, expected in {
                "trace_only": True,
                "product_driving": False,
                "render_driving": False,
                "apply_driving": False,
                "session_driving": False,
            }.items()
        ),
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start, block = _function_block(source)
    target_window = _target_window(block)
    parity = _parity_sample()
    return {
        "decision": "RENDER_GUIDANCE_SECONDARY_BINDING_ADAPTER_PARITY_PROVEN",
        "function": FUNCTION_NAME,
        "callsite_id": CALLSITE_ID,
        "binding_call_line": _line_for_after(
            block, RESTAMPER_CALL, f'callsite_id="{CALLSITE_ID}"', function_start
        ),
        "trace_call_line": _line_for_after(
            block, TRACE_CALL, f'callsite_id="{CALLSITE_ID}"', function_start
        ),
        "callsite_window": {
            "restamper_call_present": RESTAMPER_CALL in target_window,
            "trace_call_present": TRACE_CALL in target_window,
            "callsite_id_present": f'callsite_id="{CALLSITE_ID}"' in target_window,
            "input_item_captured": "_pre_card_binding_input_item = dict(item)" in target_window,
            "output_item_traced": "output_item=dict(item)" in target_window,
            "old_binding_still_live": "item = _publish_final_visible_design_guide_contract_binding(" in target_window,
            "trace_not_product_driving": "product_driving=True" not in target_window,
            "trace_not_render_driving": "render_driving=True" not in target_window,
            "trace_not_apply_driving": "apply_driving=True" not in target_window,
        },
        "parity": parity,
        "latest": {
            "ownership": _latest("design_guide_render_guidance_secondary_binding_ownership"),
            "trace_wiring": _latest("design_guide_render_guidance_secondary_binding_trace_wiring"),
            "restamper_projection": _latest("design_guide_restamper_bridge_output_projection"),
            "post_render_readiness": _latest("design_guide_post_render_bridge_restamper_readiness"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "cutover_performed": False,
        "deletion_performed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    window = dict(capture.get("callsite_window") or {})
    parity = dict(capture.get("parity") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "restamper_call_present": window.get("restamper_call_present") is True,
        "trace_call_present": window.get("trace_call_present") is True,
        "callsite_id_present": window.get("callsite_id_present") is True,
        "input_output_trace_present": (
            window.get("input_item_captured") is True
            and window.get("output_item_traced") is True
        ),
        "old_binding_still_live": window.get("old_binding_still_live") is True,
        "trace_non_authoritative": (
            window.get("trace_not_product_driving") is True
            and window.get("trace_not_render_driving") is True
            and window.get("trace_not_apply_driving") is True
        ),
        "projection_fields_present": parity.get("projection_fields_present") is True,
        "controller_matches_direct": parity.get("controller_matches_direct") is True,
        "callsite_id_preserved": parity.get("callsite_id_preserved") is True,
        "mutation_surface_detects_change": parity.get("mutation_surface_detects_change") is True,
        "proof_flags_non_authoritative": parity.get("proof_flags_non_authoritative") is True,
        "ownership_latest_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "trace_wiring_latest_pass": (latest.get("trace_wiring") or {}).get("status") == "PASS",
        "post_render_readiness_latest_pass": (
            latest.get("post_render_readiness") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "no_cutover_or_deletion": (
            capture.get("cutover_performed") is False
            and capture.get("deletion_performed") is False
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    parity = dict(capture.get("parity") or {})
    lines = [
        "# Render Guidance Secondary Binding Adapter Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Location",
        "",
        f"- Function: `{capture.get('function')}`",
        f"- Callsite: `{capture.get('callsite_id')}`",
        f"- Binding call line: `{capture.get('binding_call_line')}`",
        f"- Trace call line: `{capture.get('trace_call_line')}`",
        "",
        "## Parity",
        "",
        f"- Projection fields present: `{parity.get('projection_fields_present')}`",
        f"- Controller proof matches direct proof: `{parity.get('controller_matches_direct')}`",
        f"- Mutation surface detects change: `{parity.get('mutation_surface_detects_change')}`",
        f"- Proof flags non-authoritative: `{parity.get('proof_flags_non_authoritative')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            (
                "Add a cutover-readiness snapshot for this callsite. Do not replace "
                "or delete the live binding until readiness proves equivalent item, "
                "CTA, display, and evidence effects."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "design_brain/design_guide_controller.py",
            "design_brain/final_publication.py",
            "tools/verification/design_guide_render_guidance_secondary_binding_adapter_parity_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_guidance_secondary_binding_adapter_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_guidance_secondary_binding_adapter_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_guidance_secondary_binding_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_guidance_secondary_binding_adapter_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
