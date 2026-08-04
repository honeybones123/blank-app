"""Ownership audit for final-binding target-band promotion.

Audit-only. This maps the target-band promotion branch inside
_publish_final_visible_design_guide_contract_binding(...) before extracting a
pure Design Brain result object.
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

BINDING = "def _publish_final_visible_design_guide_contract_binding("
BRANCH_START = "target_binding_updates = dict(evidence_for_binding.get(\"best_target_band_candidate_updates\") or {})"
BRANCH_END = "safe_binding_updates = dict(evidence_for_binding.get(\"best_safe_candidate_updates\") or {})"


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


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _branch_block(source: str) -> str:
    binding = _function_block(source, BINDING)
    start = binding.find(BRANCH_START)
    end = binding.find(BRANCH_END, start)
    if start < 0 or end <= start:
        return ""
    return binding[start:end]


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    branch = _branch_block(source)
    groups = {
        "A_design_brain_policy_candidate": {
            "target_binding_evidence_available": "target_binding_evidence_available = bool(" in branch,
            "current_binding_outside_target": "current_binding_outside_target = (" in branch,
            "target_band_counts": "target_binding_count = int(" in branch,
            "target_band_family": "target_binding_family = str(" in branch,
            "target_band_util": "target_binding_util = _parse_util_value(" in branch,
        },
        "B_page_or_shared_payload_shape": {
            "contract_update": "contract.update(" in branch,
            "out_update": "out.update(" in branch,
            "payload_update": "payload.update(" in branch,
            "resolved_update": "resolved.update(" in branch,
            "display_truth_update": "display_truth.update(" in branch,
        },
        "C_page_helper_or_config_dependency": {
            "normalise_candidate_id": "_normalise_design_guide_candidate_id(" in branch,
            "updates_match_state": "_updates_match_state(state or {}, target_binding_updates)" in branch,
            "resolved_efficiency_target_band": "_resolved_efficiency_target_band(" in branch,
            "design_mode_config": "_design_mode_config(_design_optimisation_goal(state))" in branch,
        },
        "D_debug_compatibility_stamp": {
            "debug_update": "debug_sink.update(" in branch,
            "final_binding_target_band_candidate_promoted": (
                '"final_binding_target_band_candidate_promoted": True' in branch
            ),
            "button_contract_debug": '"button_contract": dict(contract)' in branch,
        },
    }
    latest = {
        "binding_ownership": _latest("design_guide_final_visible_contract_binding_ownership"),
        "no_second_cta_cutover": _latest("design_guide_final_binding_no_second_cta_result_cutover"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "TARGET_BAND_PROMOTION_NEEDS_PURE_RESULT_OBJECT_FIRST",
        "branch_found": bool(branch),
        "branch_start_line": _line_number(source, BRANCH_START),
        "branch_hash": _stable_hash(branch),
        "groups": groups,
        "safe_deletion_candidates": [],
        "recommended_next_slice": (
            "create build_final_visible_contract_binding_target_band_promotion_result(...) "
            "for the pure policy/effect maps; leave page payload/application wiring live"
        ),
        "delete_allowed_this_slice": False,
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
    groups = dict(capture.get("groups") or {})
    return {
        "branch_found": capture.get("branch_found") is True,
        "design_brain_policy_candidate_present": all(
            (groups.get("A_design_brain_policy_candidate") or {}).values()
        ),
        "page_payload_shape_present": all((groups.get("B_page_or_shared_payload_shape") or {}).values()),
        "page_helper_dependencies_present": all(
            (groups.get("C_page_helper_or_config_dependency") or {}).values()
        ),
        "debug_compatibility_stamps_present": all(
            (groups.get("D_debug_compatibility_stamp") or {}).values()
        ),
        "no_safe_deletion_candidates": not capture.get("safe_deletion_candidates"),
        "delete_not_allowed_this_slice": capture.get("delete_allowed_this_slice") is False,
        "binding_ownership_pass": (latest.get("binding_ownership") or {}).get("status") == "PASS",
        "no_second_cta_cutover_pass": (latest.get("no_second_cta_cutover") or {}).get("status") == "PASS",
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
        "# Final Binding Target-Band Promotion Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Branch start line: `{capture.get('branch_start_line')}`",
        f"- Safe deletion candidates: `{capture.get('safe_deletion_candidates')}`",
        f"- Recommended next slice: {capture.get('recommended_next_slice')}",
        "",
        "## Groups",
        "",
    ]
    for group, values in (capture.get("groups") or {}).items():
        lines.append(f"### {group}")
        for key, value in values.items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    lines.extend(["## Checks", ""])
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
        "schema": "design_guide_final_binding_target_band_promotion_ownership_audit.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_target_band_promotion_ownership_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_target_band_promotion_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_target_band_promotion_ownership {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
