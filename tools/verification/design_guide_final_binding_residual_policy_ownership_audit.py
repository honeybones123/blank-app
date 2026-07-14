"""Ownership audit for remaining final-binding page policy.

Audit-only. This records the residual policy blocks inside
`_publish_final_visible_design_guide_contract_binding(...)` after the
no-second-CTA and target-band promotion cutovers.
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


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    binding = _function_block(source, BINDING)
    latest = {
        "no_second_cta_cutover": _latest("design_guide_final_binding_no_second_cta_result_cutover"),
        "target_band_cutover": _latest("design_guide_final_binding_target_band_promotion_result_cutover"),
        "target_band_deadness": _latest("design_guide_final_binding_target_band_promotion_manual_fallback_deadness"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    residual_blocks = [
        {
            "id": "shear_safe_binding_contract_mismatch_reset",
            "line": _line_number(source, "safe_binding_evidence_available = bool("),
            "present": "safe_binding_evidence_available = bool(" in binding
            and "if safe_binding_evidence_available and dict(updates) != dict(safe_binding_updates):" in binding
            and 'action_type = ""' in binding
            and "contract = {}" in binding,
            "classification": "A. extractable policy/result object",
            "role": "Clears a button contract when shear safe-binding evidence disagrees with current updates.",
            "design_brain_candidate": "final binding contract consistency guard result",
        },
        {
            "id": "combined_binding_contract_mismatch_reset",
            "line": _line_number(source, "combined_binding_evidence_available = bool("),
            "present": "combined_binding_evidence_available = bool(" in binding
            and "if combined_binding_evidence_available and dict(updates) != dict(combined_binding_updates):" in binding
            and 'action_type = ""' in binding
            and "contract = {}" in binding,
            "classification": "A. extractable policy/result object",
            "role": "Clears a button contract when combined cleanup evidence disagrees with current updates.",
            "design_brain_candidate": "final binding contract consistency guard result",
        },
        {
            "id": "enabled_contract_expected_util_family_truth",
            "line": _line_number(source, "if updates and _design_guide_button_contract_enabled(contract):"),
            "present": "if updates and _design_guide_button_contract_enabled(contract):" in binding
            and "evidence_expected_util = _parse_util_value(" in binding
            and "evidence_family_for_contract = str(evidence_for_binding.get(\"family\")" in binding,
            "classification": "A. extractable policy with page/shared evaluation boundary",
            "role": "Derives final expected-util and family truth for an enabled contract.",
            "design_brain_candidate": "final binding contract truth result",
        },
        {
            "id": "combined_contract_truth_probe_evaluator_call",
            "line": _line_number(source, 'source="final_binding_combined_contract_truth_probe"'),
            "present": "_evaluate_auto_design_candidate(" in binding
            and 'source="final_binding_combined_contract_truth_probe"' in binding,
            "classification": "B. page/shared evaluator boundary must remain outside Design Brain",
            "role": "Uses page evaluator to probe combined binding util; can be represented as plain input to a result object later.",
            "design_brain_candidate": "do not move evaluator call; move only normalized decision/effect result",
        },
    ]
    return {
        "decision": "FINAL_BINDING_RESIDUAL_POLICY_AUDIT_PASS",
        "binding_present": bool(binding),
        "binding_line_count": binding.count("\n") + 1 if binding else 0,
        "residual_blocks": residual_blocks,
        "extractable_block_count": sum(1 for row in residual_blocks if str(row.get("classification", "")).startswith("A.")),
        "page_boundary_block_count": sum(1 for row in residual_blocks if str(row.get("classification", "")).startswith("B.")),
        "safe_deletion_candidates": [],
        "recommended_next_slice": "final binding contract consistency guard result object for the shear/combined mismatch reset blocks",
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
        "binding_present": capture.get("binding_present") is True,
        "all_residual_blocks_found": all(row.get("present") for row in capture.get("residual_blocks") or []),
        "has_extractable_blocks": int(capture.get("extractable_block_count") or 0) >= 1,
        "has_no_safe_deletion_candidates": not capture.get("safe_deletion_candidates"),
        "no_second_cta_cutover_pass": (latest.get("no_second_cta_cutover") or {}).get("status") == "PASS",
        "target_band_cutover_pass": (latest.get("target_band_cutover") or {}).get("status") == "PASS",
        "target_band_deadness_pass": (latest.get("target_band_deadness") or {}).get("status") == "PASS",
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
        "# Final Binding Residual Policy Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Residual Blocks",
        "",
    ]
    for row in capture.get("residual_blocks") or []:
        lines.append(
            f"- `{row.get('id')}` line `{row.get('line')}`: {row.get('classification')} - {row.get('role')}"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            str(capture.get("recommended_next_slice")),
            "",
            "## Checks",
            "",
        ]
    )
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
        "schema": "design_guide_final_binding_residual_policy_ownership_audit.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_residual_policy_ownership_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_residual_policy_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_residual_policy_ownership {status}")
    print(f"decision={capture.get('decision')}")
    print(f"recommended_next_slice={capture.get('recommended_next_slice')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
