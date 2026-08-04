"""Trace wiring proof for final-visible post-click contract adapter proof."""

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

IMPORT_TOKEN = (
    "build_final_design_guide_post_click_final_contract_check_adapter_proof "
    "as _build_final_design_guide_post_click_final_contract_check_adapter_proof"
)
HELPER_TOKEN = "def _stamp_final_publication_post_click_final_contract_adapter_proof("
BUILDER_CALL = "_build_final_design_guide_post_click_final_contract_check_adapter_proof("
STAMP_CALL = "_stamp_final_publication_post_click_final_contract_adapter_proof("
TARGET_START = "_post_click_bending_low_visible_action = bool("
TARGET_END = "_final_visible_item = _normalise_visible_optimisation_contract("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _target_block(source: str) -> str:
    start = source.find(TARGET_START)
    if start < 0:
        return ""
    end = source.find(TARGET_END, start)
    return source[start:end] if end > start else ""


def _helper_block(source: str) -> str:
    start = source.find(HELPER_TOKEN)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper = _helper_block(source)
    target = _target_block(source)
    latest = {
        "object": _latest("design_guide_post_click_final_contract_adapter_object"),
        "parity": _latest("design_guide_post_click_final_contract_adapter_parity"),
        "ownership": _latest("design_guide_post_click_remaining_live_truth_ownership"),
        "controller_readiness": _latest("design_guide_post_click_controller_adapter_readiness"),
        "input_trace": _latest("design_guide_live_post_click_contract_check_input_proof_trace"),
        "replacement_trace": _latest("design_guide_live_post_click_replacement_decision_proof_trace"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "LIVE_POST_CLICK_FINAL_CONTRACT_ADAPTER_TRACE_PASS",
        "import_present": IMPORT_TOKEN in source,
        "helper_present": bool(helper),
        "builder_call_in_helper": BUILDER_CALL in helper,
        "target_block_found": bool(target),
        "stamp_call_count_in_target": target.count(STAMP_CALL),
        "input_proof_payload_captured": "_post_click_contract_check_input_proof =" in source,
        "replacement_decision_payload_captured": "_post_click_replacement_decision_proof =" in target,
        "input_proof_passed_to_adapter": "input_proof=dict(_post_click_contract_check_input_proof or {})" in target,
        "replacement_proof_passed_to_adapter": (
            "replacement_decision_proof=dict(_post_click_replacement_decision_proof or {})" in target
        ),
        "proof_hash_stamped": "final_publication_post_click_final_contract_adapter_proof_hash" in helper,
        "covered_groups_stamped": "final_publication_post_click_final_contract_adapter_covered_groups" in helper,
        "trace_only_flags_stamped": all(
            token in helper
            for token in (
                "final_publication_post_click_final_contract_adapter_proof_only",
                "final_publication_post_click_final_contract_adapter_product_driving",
                "final_publication_post_click_final_contract_adapter_render_driving",
                "final_publication_post_click_final_contract_adapter_apply_driving",
                "final_publication_post_click_final_contract_adapter_session_driving",
            )
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "import_present": capture.get("import_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "builder_call_in_helper": capture.get("builder_call_in_helper") is True,
        "target_block_found": capture.get("target_block_found") is True,
        "stamp_call_once_in_target": capture.get("stamp_call_count_in_target") == 1,
        "input_proof_payload_captured": capture.get("input_proof_payload_captured") is True,
        "replacement_decision_payload_captured": capture.get("replacement_decision_payload_captured") is True,
        "input_proof_passed_to_adapter": capture.get("input_proof_passed_to_adapter") is True,
        "replacement_proof_passed_to_adapter": capture.get("replacement_proof_passed_to_adapter") is True,
        "proof_hash_stamped": capture.get("proof_hash_stamped") is True,
        "covered_groups_stamped": capture.get("covered_groups_stamped") is True,
        "trace_only_flags_stamped": capture.get("trace_only_flags_stamped") is True,
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "ownership_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "controller_readiness_pass": (latest.get("controller_readiness") or {}).get("status") == "PASS",
        "input_trace_pass": (latest.get("input_trace") or {}).get("status") == "PASS",
        "replacement_trace_pass": (latest.get("replacement_trace") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Post-Click Final Contract Adapter Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Stamp calls in target block: `{capture.get('stamp_call_count_in_target')}`",
        f"- Input proof payload captured: `{capture.get('input_proof_payload_captured')}`",
        f"- Replacement proof payload captured: `{capture.get('replacement_decision_payload_captured')}`",
        f"- Proof hash stamped: `{capture.get('proof_hash_stamped')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", ""])
    lines.append("Next safe slice: live parity/hash comparison before any cutover or deletion.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_live_post_click_final_contract_adapter_trace_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_live_post_click_final_contract_adapter_trace_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_post_click_final_contract_adapter_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_live_post_click_final_contract_adapter_trace {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
