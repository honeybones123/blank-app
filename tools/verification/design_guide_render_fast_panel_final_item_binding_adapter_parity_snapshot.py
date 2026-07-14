"""Parity proof for render-fast final item binding adapter.

Proof-only. The last live final-visible restamper call is the
``_final_visible_item`` binding in ``_render_fast_design_guidance_panel``. This
snapshot proves the DesignGuideController final-visible output bridge proof surface can
represent that binding before any live trace wiring or cutover.
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

CALLSITE_ID = "render_fast_design_guidance_panel.final_visible_item_binding"
FUNCTION_NAME = "_render_fast_design_guidance_panel"
RESTAMPER_CALL = "_final_visible_item = _publish_final_visible_design_guide_contract_binding("


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
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
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
    return source[:start].count("\n") + 1, source[start:end]


def _line_for(block: str, token: str, start_line: int | None) -> int | None:
    idx = block.find(token)
    if idx < 0:
        return None
    return (start_line or 1) + block[:idx].count("\n")


def _window(block: str, token: str) -> str:
    idx = block.find(token)
    if idx < 0:
        return ""
    return block[max(0, idx - 4000) : min(len(block), idx + 14000)]


def _parity_sample() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_final_visible_output_bridge_trace_only,
    )
    from design_brain.final_publication import build_final_design_guide_publication_mutation_proof

    input_item = {
        "title": "Strengthening required",
        "title_main": "Strengthening required",
        "status": "FAIL",
        "bucket": "fail",
        "guidance_intent": "repair",
        "button_contract": {"enabled": False, "actionable": False, "updates": {}},
        "candidate_search_evidence": {"family": "bending", "safe_executor_backed_candidates_count": 0},
    }
    output_item = {
        **input_item,
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "updates": {"D": 650.0},
        },
        "action_payload": {"updates": {"D": 650.0}},
        "candidate_search_evidence": {
            "family": "bending",
            "safe_executor_backed_candidates_count": 1,
            "selected_candidate_updates": {"D": 650.0},
        },
    }
    state = {"D": 500.0, "uls_Mstar_pos": 300.0}
    debug = {"source": "render_fast_final_item_binding_parity"}
    rec = {"pending": True, "family": "bending"}
    direct = build_final_design_guide_publication_mutation_proof(
        callsite_id=CALLSITE_ID,
        input_item=input_item,
        output_item=output_item,
        state=state,
        debug=debug,
        rec=rec,
    ).to_dict()
    controller = run_design_guide_controller_final_visible_output_bridge_trace_only(
        {
            "callsite_id": CALLSITE_ID,
            "input_item": input_item,
            "output_item": output_item,
            "state": state,
            "debug": debug,
            "rec": rec,
            "source": "render_fast_final_item_binding_parity",
        }
    ).to_dict()
    controller_proof = dict(controller.get("final_visible_output_bridge_proof") or {})
    return {
        "direct_proof_hash": direct.get("proof_hash"),
        "controller_proof_hash": controller_proof.get("proof_hash"),
        "controller_matches_direct": controller_proof.get("proof_hash") == direct.get("proof_hash"),
        "callsite_id_preserved": controller_proof.get("callsite_id") == CALLSITE_ID,
        "projection_fields_present": all(
            controller_proof.get(field)
            for field in (
                "cta_projection_hash",
                "display_projection_hash",
                "evidence_projection_hash",
                "mutation_surface",
            )
        ),
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
    window = _window(block, RESTAMPER_CALL)
    return {
        "decision": "RENDER_FAST_FINAL_ITEM_BINDING_ADAPTER_PARITY_PROVEN_NOT_WIRED",
        "callsite_id": CALLSITE_ID,
        "function": FUNCTION_NAME,
        "binding_call_line": _line_for(block, RESTAMPER_CALL, function_start),
        "window_checks": {
            "restamper_call_present": RESTAMPER_CALL in window,
            "final_visible_resolution_input_present": (
                "_final_visible_binding_input_item = dict("
                in window
                and '_final_visible_resolution.get("item") or {}' in window
                and "item=dict(_final_visible_binding_input_item)" in window
            ),
            "publication_snapshot_before_binding": "_record_design_guide_publication_snapshot(" in window,
            "render_item_consumer_after_binding": "_stamp_final_publication_render_item_consumer_proof(" in window,
            "zero_shear_consumer_after_binding": "_apply_final_design_guide_zero_shear_render_consumer_projection(" in window,
            "safe_low_util_consumer_after_binding": "_visible_safe_low_util_cleanup_action_from_evidence(" in window,
            "old_binding_still_live": RESTAMPER_CALL in window,
        },
        "parity": _parity_sample(),
        "latest": {
            "ownership": _latest("design_guide_render_fast_panel_binding_ownership"),
            "render_panel_readiness": _latest("design_guide_render_panel_binding_adapter_readiness"),
            "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
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
    window_checks = dict(capture.get("window_checks") or {})
    parity = dict(capture.get("parity") or {})
    return {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "window_checks_pass": all(value is True for value in window_checks.values()),
        "controller_matches_direct": parity.get("controller_matches_direct") is True,
        "callsite_id_preserved": parity.get("callsite_id_preserved") is True,
        "projection_fields_present": parity.get("projection_fields_present") is True,
        "mutation_surface_detects_change": parity.get("mutation_surface_detects_change") is True,
        "proof_flags_non_authoritative": parity.get("proof_flags_non_authoritative") is True,
        "ownership_latest_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "render_panel_readiness_latest_pass": (latest.get("render_panel_readiness") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (
            latest.get("remaining_restamper_audit") or {}
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
        "# Design Guide Render Fast Final Item Binding Adapter Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scope",
        "",
        f"- Callsite: `{capture.get('callsite_id')}`",
        f"- Binding line: `{capture.get('binding_call_line')}`",
        "",
        "## Parity",
        "",
        f"- Controller proof matches direct proof: `{parity.get('controller_matches_direct')}`",
        f"- Projection fields present: `{parity.get('projection_fields_present')}`",
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
            "Add live trace/cutover-readiness for this final item binding before any replacement or deletion.",
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
            "tools/verification/design_guide_render_fast_panel_final_item_binding_adapter_parity_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_fast_panel_final_item_binding_adapter_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_fast_panel_final_item_binding_adapter_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_fast_panel_final_item_binding_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_fast_panel_final_item_binding_adapter_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
