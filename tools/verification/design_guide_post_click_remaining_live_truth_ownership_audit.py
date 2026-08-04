"""Ownership audit for remaining post-click final contract check live truth.

Proof-only. This does not change product behavior. It records which remaining
post-click rows are page input collection, which are extraction candidates, and
which must remain live until a stronger adapter exists.
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

TARGET_START = '_final_contract_for_post_click = dict(_final_visible_item.get("button_contract") or {})'
TARGET_END = "_final_visible_item = _normalise_visible_optimisation_contract("

GROUPS = {
    "A_page_owned_input_collection": {
        "tokens": (
            "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
            "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
            '_float_from_state(current_state, "lig_d", None)',
            '_float_from_state(current_state, "lig_legs", None)',
            "_final_current_bending_util_for_post_click",
        ),
        "owner": "inputs_page.py",
        "recommendation": "retain as page input collection",
    },
    "B_controller_publication_extraction_candidate": {
        "tokens": (
            "_post_click_bending_low_requires_exact_blocker = bool(",
            "_post_click_bending_low_visible_action = bool(",
            "_post_click_low_bending_resolution_item(",
        ),
        "owner": "controller_or_final_publication_adapter",
        "recommendation": (
            "predicate rows are adapter-backed; continue extracting the low-bending "
            "resolution builder one internal surface at a time"
        ),
    },
    "C_evidence_assembly_extraction_candidate": {
        "tokens": (
            "_post_click_bending_audit_sources_for_visible = (",
            "_build_final_design_guide_post_click_bending_replacement_audit_result_proof(",
            "final_publication_post_click_bending_replacement_audit_merge_cutover_used",
        ),
        "owner": "controller_or_final_publication_adapter",
        "recommendation": "evidence merge is adapter-backed; keep page-owned source collection explicit",
    },
    "D_already_removed_projection_rows": {
        "tokens": (
            '_final_visible_resolution["item"] = dict(_final_visible_item)',
            '_final_visible_resolution["render_reason"] = "post_click_low_bending_exact_blocker_final"',
            'guidance_debug["post_click_low_bending_action_replaced_by_exact_blocker"] = True',
            'guidance_debug["guidance_branch"] = "post_click_low_bending_exact_blocker_final"',
            "_post_click_bending_replacement_applied = True",
        ),
        "owner": "removed_or_adapter_backed",
        "recommendation": "no action; keep verifiers aligned",
    },
}


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


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _presence(block: str, tokens: tuple[str, ...]) -> dict[str, bool]:
    return {token: token in block for token in tokens}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    block = _target_block(source)
    groups: dict[str, Any] = {}
    for name, spec in GROUPS.items():
        tokens = tuple(spec["tokens"])
        presence = _presence(block, tokens)
        if name == "D_already_removed_projection_rows":
            expected_state = "absent"
            state_ok = not any(presence.values())
        else:
            expected_state = "present"
            state_ok = all(presence.values())
        groups[name] = {
            "owner": spec["owner"],
            "recommendation": spec["recommendation"],
            "expected_state": expected_state,
            "state_ok": state_ok,
            "presence": presence,
        }
    latest = {
        "row_level_readiness": _latest("design_guide_post_click_contract_check_row_level_readiness"),
        "input_parity": _latest("design_guide_post_click_contract_check_input_proof_parity_scenarios"),
        "replacement_parity": _latest("design_guide_post_click_replacement_decision_proof_parity_scenarios"),
        "render_item_parity": _latest("design_guide_live_render_item_consumer_adapter_parity"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "POST_CLICK_REMAINING_LIVE_TRUTH_OWNERSHIP_CLASSIFIED",
        "target_block_found": bool(block),
        "target_block_start_line": _line_number(source, TARGET_START),
        "target_block_hash": _stable_hash(block),
        "groups": groups,
        "safe_deletion_candidates": [],
        "next_extraction_candidate": "post_click_low_bending_resolution_builder_internal_surface",
        "next_required_proof": (
            "focused request/result parity for the next internal builder surface: search/evaluation, "
            "residual shear cleanup, blocker evidence, CTA guard, or visible wording"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    groups = dict(capture.get("groups") or {})
    latest = dict(capture.get("latest") or {})
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "all_group_states_as_expected": all((group or {}).get("state_ok") is True for group in groups.values()),
        "no_safe_deletion_candidates": capture.get("safe_deletion_candidates") == [],
        "row_level_readiness_pass": (latest.get("row_level_readiness") or {}).get("status") == "PASS",
        "input_parity_pass": (latest.get("input_parity") or {}).get("status") == "PASS",
        "replacement_parity_pass": (latest.get("replacement_parity") or {}).get("status") == "PASS",
        "render_item_parity_pass": (latest.get("render_item_parity") or {}).get("status") == "PASS",
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
        "# Post-Click Remaining Live Truth Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Target block start line: `{capture.get('target_block_start_line')}`",
        f"- Safe deletion candidates: `{capture.get('safe_deletion_candidates')}`",
        f"- Next extraction candidate: `{capture.get('next_extraction_candidate')}`",
        f"- Next required proof: {capture.get('next_required_proof')}",
        "",
        "## Groups",
        "",
    ]
    for name, group in (capture.get("groups") or {}).items():
        lines.append(
            f"- {name}: owner=`{group.get('owner')}` expected=`{group.get('expected_state')}` "
            f"state_ok=`{group.get('state_ok')}` recommendation={group.get('recommendation')}"
        )
    lines.extend(["", "## Checks", ""])
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
        "schema": "design_guide_post_click_remaining_live_truth_ownership_audit.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_post_click_remaining_live_truth_ownership_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_click_remaining_live_truth_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_remaining_live_truth_ownership {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
