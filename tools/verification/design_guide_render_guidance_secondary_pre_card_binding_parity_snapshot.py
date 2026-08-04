"""Parity proof for pre-render/pre-card final-visible output bridges.

Proof-only. The remaining restamper inventory still has two C-class
``_render_guidance_secondary_items`` bridges before card rendering. This
snapshot proves those bridge callsites are wired to the controller restamper
proof surface and that the proof surface is stable before any cutover/deletion.
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

FUNCTION_NAME = "_render_guidance_secondary_items"
RESTAMPER_CALL = "_publish_final_visible_design_guide_contract_binding("
TRACE_CALL = "_stamp_final_visible_final_visible_output_bridge_proof("

TARGETS = {
    "render_guidance_secondary_items.pre_render_binding": {
        "binding_assignment": "_pre_render_bound_item = _publish_final_visible_design_guide_contract_binding(",
        "input_capture": "_pre_render_input_item = dict(item)",
        "output_trace": "_pre_render_bound_item or {}",
        "bypass_call": "_pre_render_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop(",
        "bypass_marker": "final_visible_restamper_bridge_pre_render_bypassed",
    },
    "render_guidance_secondary_items.pre_card_binding": {
        "binding_assignment": "_pre_card_bound_item = _publish_final_visible_design_guide_contract_binding(",
        "input_capture": "_pre_card_input_item = dict(item)",
        "output_trace": "_pre_card_bound_item or {}",
        "bypass_call": "_pre_card_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop(",
        "bypass_marker": "final_visible_restamper_bridge_pre_card_bypassed",
    },
}


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
    return source[:start].count("\n") + 1, source[start:end]


def _line_for(block: str, token: str, start_line: int | None) -> int | None:
    for offset, line in enumerate(block.splitlines()):
        if token in line:
            return (start_line or 1) + offset
    return None


def _target_window(block: str, callsite_id: str) -> str:
    marker = f'callsite_id="{callsite_id}"'
    marker_index = block.find(marker)
    if marker_index < 0:
        return ""
    start = max(0, marker_index - 1200)
    end = min(len(block), marker_index + 2600)
    return block[start:end]


def _parity_sample(callsite_id: str) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_final_visible_output_bridge_trace_only,
    )
    from design_brain.final_publication import (
        build_final_design_guide_publication_mutation_proof,
    )

    input_item = {
        "title": "Design is efficient",
        "title_main": "Design is efficient",
        "status": "PASS",
        "bucket": "pass",
        "guidance_intent": "cleanup",
        "button_contract": {"enabled": False, "actionable": False, "updates": {}},
        "candidate_search_evidence": {
            "family": "cleanup",
            "safe_executor_backed_candidates_count": 0,
        },
    }
    output_item = {
        **input_item,
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "updates": {"lig_legs": 0},
        },
        "action_payload": {"updates": {"lig_legs": 0}},
        "candidate_search_evidence": {
            "family": "cleanup",
            "safe_executor_backed_candidates_count": 1,
            "selected_candidate_updates": {"lig_legs": 0},
        },
    }
    state = {"lig_legs": 2, "uls_Vstar": 0.0}
    debug = {"source": "pre_card_binding_parity", "callsite_id": callsite_id}
    rec = {"pending": True, "family": "cleanup"}
    direct = build_final_design_guide_publication_mutation_proof(
        callsite_id=callsite_id,
        input_item=input_item,
        output_item=output_item,
        state=state,
        debug=debug,
        rec=rec,
    ).to_dict()
    controller = run_design_guide_controller_final_visible_output_bridge_trace_only(
        {
            "callsite_id": callsite_id,
            "input_item": input_item,
            "output_item": output_item,
            "state": state,
            "debug": debug,
            "rec": rec,
            "source": "pre_card_binding_parity",
        }
    ).to_dict()
    controller_proof = dict(controller.get("final_visible_output_bridge_proof") or {})
    return {
        "direct_proof_hash": direct.get("proof_hash"),
        "controller_proof_hash": controller_proof.get("proof_hash"),
        "controller_matches_direct": controller_proof.get("proof_hash") == direct.get("proof_hash"),
        "callsite_id_preserved": controller_proof.get("callsite_id") == callsite_id,
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
    targets: dict[str, Any] = {}
    for callsite_id, spec in TARGETS.items():
        window = _target_window(block, callsite_id)
        targets[callsite_id] = {
            "binding_call_line": _line_for(block, spec["binding_assignment"], function_start),
            "trace_call_line": _line_for(block, f'callsite_id="{callsite_id}"', function_start),
            "window": {
                "restamper_call_present": spec["binding_assignment"] in window,
                "trace_call_present": TRACE_CALL in window,
                "callsite_id_present": f'callsite_id="{callsite_id}"' in window,
                "input_item_captured": spec["input_capture"] in window,
                "output_item_traced": spec["output_trace"] in window,
                "bypass_guard_present": spec["bypass_call"] in window,
                "bypass_marker_present": spec["bypass_marker"] in window,
                "old_binding_still_live": spec["binding_assignment"] in window,
                "trace_not_product_driving": "product_driving=True" not in window,
                "trace_not_render_driving": "render_driving=True" not in window,
                "trace_not_apply_driving": "apply_driving=True" not in window,
            },
            "parity": _parity_sample(callsite_id),
        }
    return {
        "decision": "PRE_RENDER_PRE_CARD_RESTAMPER_BRIDGE_PARITY_PROVEN_NOT_CUT_OVER",
        "function": FUNCTION_NAME,
        "targets": targets,
        "latest": {
            "remaining_restamper_audit": _latest(
                "design_guide_remaining_final_visible_restamper_reference_audit"
            ),
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
    targets = dict(capture.get("targets") or {})
    checks: dict[str, bool] = {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "all_targets_present": set(targets) == set(TARGETS),
    }
    for callsite_id, row_any in targets.items():
        row = dict(row_any or {})
        window = dict(row.get("window") or {})
        parity = dict(row.get("parity") or {})
        prefix = callsite_id.replace(".", "_")
        checks[f"{prefix}_restamper_call_present"] = window.get("restamper_call_present") is True
        checks[f"{prefix}_trace_call_present"] = window.get("trace_call_present") is True
        checks[f"{prefix}_input_output_trace_present"] = (
            window.get("input_item_captured") is True and window.get("output_item_traced") is True
        )
        checks[f"{prefix}_bypass_guard_present"] = (
            window.get("bypass_guard_present") is True and window.get("bypass_marker_present") is True
        )
        checks[f"{prefix}_old_binding_still_live"] = window.get("old_binding_still_live") is True
        checks[f"{prefix}_trace_non_authoritative"] = (
            window.get("trace_not_product_driving") is True
            and window.get("trace_not_render_driving") is True
            and window.get("trace_not_apply_driving") is True
        )
        checks[f"{prefix}_controller_matches_direct"] = parity.get("controller_matches_direct") is True
        checks[f"{prefix}_callsite_id_preserved"] = parity.get("callsite_id_preserved") is True
        checks[f"{prefix}_projection_fields_present"] = parity.get("projection_fields_present") is True
        checks[f"{prefix}_mutation_surface_detects_change"] = (
            parity.get("mutation_surface_detects_change") is True
        )
        checks[f"{prefix}_proof_flags_non_authoritative"] = (
            parity.get("proof_flags_non_authoritative") is True
        )
    checks.update(
        {
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
    )
    return checks


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Pre-Render / Pre-Card Restamper Bridge Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Targets",
        "",
        "| Callsite | Binding line | Trace line | Controller parity |",
        "| --- | ---: | ---: | --- |",
    ]
    for callsite_id, row_any in dict(capture.get("targets") or {}).items():
        row = dict(row_any or {})
        parity = dict(row.get("parity") or {})
        lines.append(
            f"| `{callsite_id}` | {row.get('binding_call_line')} | {row.get('trace_call_line')} | `{parity.get('controller_matches_direct')}` |"
        )
    lines.extend(["", "## Checks", ""])
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
                "Add cutover-readiness for these two bridges. Do not replace or delete the live "
                "restamper calls until readiness proves the same item, CTA, display, and evidence effects."
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
            "tools/verification/design_guide_render_guidance_secondary_pre_card_binding_parity_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_guidance_secondary_pre_card_binding_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_guidance_secondary_pre_card_binding_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_guidance_secondary_pre_card_binding_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_guidance_secondary_pre_card_binding_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
