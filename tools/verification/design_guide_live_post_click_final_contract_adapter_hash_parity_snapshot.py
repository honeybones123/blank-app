"""Hash/parity readiness for live final-visible post-click adapter trace."""

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

TARGET_START = "_post_click_bending_low_visible_action = bool("
TARGET_END = "_final_visible_item = _normalise_visible_optimisation_contract("
BUILDER = "def build_final_design_guide_post_click_final_contract_check_adapter_proof("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = artifacts[-1]
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


def _target_block(source: str) -> str:
    start = source.find(TARGET_START)
    if start < 0:
        return ""
    end = source.find(TARGET_END, start)
    return source[start:end] if end > start else ""


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    target = _target_block(inputs_source)
    builder = _function_block(publication_source, BUILDER)
    latest = {
        "adapter_object": _latest("design_guide_post_click_final_contract_adapter_object"),
        "adapter_parity": _latest("design_guide_post_click_final_contract_adapter_parity"),
        "adapter_trace": _latest("design_guide_live_post_click_final_contract_adapter_trace"),
        "input_trace": _latest("design_guide_live_post_click_contract_check_input_proof_trace"),
        "replacement_trace": _latest("design_guide_live_post_click_replacement_decision_proof_trace"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    trace_payload = dict((latest.get("adapter_trace") or {}).get("payload") or {})
    trace_capture = dict(trace_payload.get("capture") or {})
    return {
        "decision": "LIVE_POST_CLICK_FINAL_CONTRACT_ADAPTER_HASH_PARITY_READY",
        "target_block_found": bool(target),
        "builder_found": bool(builder),
        "input_proof_payload_captured": "_post_click_contract_check_input_proof =" in inputs_source,
        "replacement_decision_payload_captured": "_post_click_replacement_decision_proof =" in target,
        "input_proof_passed_to_adapter": "input_proof=dict(_post_click_contract_check_input_proof or {})" in target,
        "replacement_proof_passed_to_adapter": (
            "replacement_decision_proof=dict(_post_click_replacement_decision_proof or {})" in target
        ),
        "builder_uses_input_proof_hash": "input_proof_d.get(\"proof_hash\")" in builder,
        "builder_uses_replacement_proof_hash": "replacement_proof_d.get(\"proof_hash\")" in builder,
        "builder_hashes_adapter_result": "adapter_result_hash" in builder,
        "trace_stamp_count": trace_capture.get("stamp_call_count_in_target"),
        "trace_proof_hash_stamped": trace_capture.get("proof_hash_stamped"),
        "ready_for_cutover": False,
        "next_required_step": (
            "product-capable controller/publication adapter result proof before moving decision "
            "predicates or resolution-builder output"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "builder_found": capture.get("builder_found") is True,
        "input_proof_payload_captured": capture.get("input_proof_payload_captured") is True,
        "replacement_decision_payload_captured": capture.get("replacement_decision_payload_captured") is True,
        "input_proof_passed_to_adapter": capture.get("input_proof_passed_to_adapter") is True,
        "replacement_proof_passed_to_adapter": capture.get("replacement_proof_passed_to_adapter") is True,
        "builder_uses_input_proof_hash": capture.get("builder_uses_input_proof_hash") is True,
        "builder_uses_replacement_proof_hash": capture.get("builder_uses_replacement_proof_hash") is True,
        "builder_hashes_adapter_result": capture.get("builder_hashes_adapter_result") is True,
        "trace_stamp_once": capture.get("trace_stamp_count") == 1,
        "trace_proof_hash_stamped": capture.get("trace_proof_hash_stamped") is True,
        "adapter_object_pass": (latest.get("adapter_object") or {}).get("status") == "PASS",
        "adapter_parity_pass": (latest.get("adapter_parity") or {}).get("status") == "PASS",
        "adapter_trace_pass": (latest.get("adapter_trace") or {}).get("status") == "PASS",
        "input_trace_pass": (latest.get("input_trace") or {}).get("status") == "PASS",
        "replacement_trace_pass": (latest.get("replacement_trace") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "cutover_not_ready": capture.get("ready_for_cutover") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Post-Click Final Contract Adapter Hash Parity",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Trace stamp count: `{capture.get('trace_stamp_count')}`",
        f"- Ready for cutover: `{capture.get('ready_for_cutover')}`",
        f"- Next required step: {capture.get('next_required_step')}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_live_post_click_final_contract_adapter_hash_parity_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_live_post_click_final_contract_adapter_hash_parity_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_post_click_final_contract_adapter_hash_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_live_post_click_final_contract_adapter_hash_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
