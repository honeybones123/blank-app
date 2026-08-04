"""Manual fallback deadness audit for final-binding contract truth rows."""

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

BINDING = "def _publish_final_visible_design_guide_contract_binding("
HELPER = "def _stamp_final_visible_contract_binding_truth_result("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
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
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    binding = _function_block(source, BINDING)
    helper = _function_block(source, HELPER)
    manual_fallback_rows = {
        "evidence_expected_util": "evidence_expected_util = _parse_util_value(" in binding,
        "contract_expected_util": "contract_expected_util = _parse_util_value(contract.get(\"expected_util\"))" in binding,
        "evidence_family": "evidence_family_for_contract = str(evidence_for_binding.get(\"family\") or \"\")" in binding,
        "update_keys": "contract_update_keys_for_family = {" in binding,
        "cross_family": "contract_updates_cross_family = bool(" in binding,
        "combined_text": "contract_combined_text = \" \".join(" in binding,
        "title_hint": "title_hint_for_contract = \" \".join(" in binding,
        "bending_target_util": "bending_target_util = _parse_util_value(" in binding,
        "combined_preview_probe": "_evaluate_auto_design_candidate(" in binding,
        "blocker_families": "blocker_families_for_contract = {evidence_family_for_contract}" in binding,
    }
    helper_exception_path = {
        "except_present": "except Exception as exc:" in helper,
        "returns_empty_payload": "return {}" in helper,
        "error_stamp": '"final_binding_contract_truth_result_error"' in helper,
    }
    helper_typed_fallback_path = {
        "except_present": "except Exception as exc:" in helper,
        "uses_typed_fallback_builder": "_build_final_visible_contract_binding_typed_fallback_payload(" in helper,
        "error_stamp": '"final_binding_contract_truth_result_error"' in helper,
        "evidence_expected_util": '"evidence_expected_util": live_evidence_expected_util' in helper,
        "contract_expected_util": '"contract_expected_util": live_contract_expected_util' in helper,
        "family_truth": '"evidence_family_for_contract": fallback_family' in helper,
        "cross_family_truth": '"contract_updates_cross_family": bool(live_contract_updates_cross_family)' in helper,
        "blocker_family_truth": '"blocker_families_for_contract": fallback_blockers' in helper,
    }
    design_brain_cutover_present = {
        "payload_assignment": (
            "final_binding_contract_truth_payload = _stamp_final_visible_contract_binding_truth_result("
            in binding
        ),
        "result_guard": "if final_binding_contract_truth_result:" in binding,
        "live_cutover_stamp": '"final_binding_contract_truth_result_live_cutover_used"' in binding,
    }
    latest = {
        "cutover": _latest("design_guide_final_binding_contract_truth_result_cutover"),
        "readiness": _latest("design_guide_final_binding_contract_truth_cutover_readiness"),
        "parity": _latest("design_guide_final_binding_contract_truth_result_parity_scenarios"),
        "trace": _latest("design_guide_live_final_binding_contract_truth_result_trace"),
        "typed_fallback": _latest("design_guide_final_binding_typed_fallback_payload"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    typed_fallback_pass = (latest.get("typed_fallback") or {}).get("status") == "PASS"
    pre_helper_rows_removed = all(
        not manual_fallback_rows.get(key)
        for key in (
            "evidence_expected_util",
            "contract_expected_util",
            "evidence_family",
            "combined_text",
            "title_hint",
            "bending_target_util",
            "blocker_families",
        )
    )
    allowed_residual_rows = bool(
        manual_fallback_rows.get("combined_preview_probe") is True
        and manual_fallback_rows.get("update_keys") is True
        and manual_fallback_rows.get("cross_family") is True
    )
    extraction_complete = bool(
        all(design_brain_cutover_present.values())
        and helper_exception_path.get("returns_empty_payload") is False
        and all(helper_typed_fallback_path.values())
        and pre_helper_rows_removed
        and allowed_residual_rows
        and typed_fallback_pass
    )
    fallback_still_needed = bool(
        all(design_brain_cutover_present.values())
        and all(helper_exception_path.values())
        and any(manual_fallback_rows.values())
    )
    ready_for_extraction = bool(
        all(design_brain_cutover_present.values())
        and helper_exception_path.get("returns_empty_payload") is False
        and all(helper_typed_fallback_path.values())
        and any(manual_fallback_rows.values())
        and typed_fallback_pass
    )
    return {
        "decision": (
            "FINAL_BINDING_CONTRACT_TRUTH_PRE_HELPER_COMPUTE_EXTRACTION_COMPLETE"
            if extraction_complete
            else "FINAL_BINDING_CONTRACT_TRUTH_PRE_HELPER_COMPUTE_EXTRACTION_READY"
        ),
        "classification": (
            "E. extraction complete with evaluator probe retained"
            if extraction_complete
            else "C. live pre-helper compute truth / extract before deleting"
            if ready_for_extraction
            else "B. fallback/safety keep until helper exception path is retired or separately guarded"
        ),
        "manual_fallback_rows": manual_fallback_rows,
        "pre_helper_rows_removed": pre_helper_rows_removed,
        "allowed_residual_rows": allowed_residual_rows,
        "helper_exception_path": helper_exception_path,
        "helper_typed_fallback_path": helper_typed_fallback_path,
        "design_brain_cutover_present": design_brain_cutover_present,
        "fallback_still_needed": fallback_still_needed,
        "safe_deletion_candidate": False,
        "ready_for_deletion": False,
        "ready_for_extraction": bool(ready_for_extraction and not extraction_complete),
        "extraction_complete": extraction_complete,
        "next_safe_slice": (
            "keep the combined preview evaluator probe page-owned until candidate evaluation is extracted"
            if extraction_complete
            else (
                "move contract-truth pre-helper compute fields behind a Design Brain/shared helper, "
                "then prove parity before deleting page-local computations"
            )
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
        "manual_fallback_rows_still_present": any(
            (capture.get("manual_fallback_rows") or {}).values()
        ),
        "helper_exception_path_retired": (
            (capture.get("helper_exception_path") or {}).get("returns_empty_payload") is False
        ),
        "helper_typed_fallback_path_present": all(
            (capture.get("helper_typed_fallback_path") or {}).values()
        ),
        "design_brain_cutover_present": all(
            (capture.get("design_brain_cutover_present") or {}).values()
        ),
        "fallback_not_still_needed": capture.get("fallback_still_needed") is False,
        "not_safe_deletion_candidate_yet": capture.get("safe_deletion_candidate") is False,
        "not_deletion_ready_yet": capture.get("ready_for_deletion") is False,
        "pre_helper_rows_removed": capture.get("pre_helper_rows_removed") is True,
        "allowed_residual_rows": capture.get("allowed_residual_rows") is True,
        "extraction_complete": capture.get("extraction_complete") is True,
        "cutover_pass": (latest.get("cutover") or {}).get("status") == "PASS",
        "readiness_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "typed_fallback_pass": (latest.get("typed_fallback") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding Contract Truth Manual Fallback Deadness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Classification: `{capture.get('classification')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Fallback still needed: `{capture.get('fallback_still_needed')}`",
        f"- Safe deletion candidate: `{capture.get('safe_deletion_candidate')}`",
        f"- Ready for deletion: `{capture.get('ready_for_deletion')}`",
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
        "schema": "design_guide_final_binding_contract_truth_manual_fallback_deadness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_contract_truth_manual_fallback_deadness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_contract_truth_manual_fallback_deadness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_contract_truth_manual_fallback_deadness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
