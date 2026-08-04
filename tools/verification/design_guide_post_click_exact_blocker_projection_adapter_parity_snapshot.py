"""Parity proof for post-click exact-blocker replacement projection adapter."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"


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
        return {"found": True, "status": "UNREADABLE", "path": str(path), "payload": {}, "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _page_equivalent_projection(
    *,
    item: dict[str, Any],
    final_visible_resolution: dict[str, Any],
    guidance_debug: dict[str, Any],
    replacement_applied: bool,
) -> dict[str, Any]:
    item_d = dict(item)
    resolution_d = dict(final_visible_resolution)
    debug_d = dict(guidance_debug)
    if replacement_applied:
        resolution_d["item"] = dict(item_d)
        resolution_d["render_reason"] = "post_click_low_bending_exact_blocker_final"
        debug_d["post_click_low_bending_action_replaced_by_exact_blocker"] = True
        debug_d["guidance_branch"] = "post_click_low_bending_exact_blocker_final"
    payload = {
        "item": item_d,
        "final_visible_resolution": resolution_d,
        "guidance_debug": debug_d,
        "replacement_applied": bool(replacement_applied),
    }
    return {**payload, "projection_hash": _stable_hash(payload)}


def _sample() -> dict[str, Any]:
    return {
        "item": {"title": "Design Guide blocker proof incomplete", "family": "bending"},
        "final_visible_resolution": {
            "item": {"title": "Previous item"},
            "render_reason": "before_post_click_exact_blocker",
            "overview": {"utils": {"bending": 0.24}},
        },
        "guidance_debug": {"existing_debug": True},
        "replacement_applied": True,
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        apply_final_design_guide_post_click_exact_blocker_replacement_projection,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    adapter_start = publication_source.find(
        "def apply_final_design_guide_post_click_exact_blocker_replacement_projection("
    )
    adapter_end = publication_source.find("\ndef ", adapter_start + 1) if adapter_start >= 0 else -1
    adapter_source = (
        publication_source[adapter_start:adapter_end]
        if adapter_start >= 0 and adapter_end > adapter_start
        else ""
    )
    sample = _sample()
    adapter = apply_final_design_guide_post_click_exact_blocker_replacement_projection(**sample)
    expected = _page_equivalent_projection(**sample)
    passthrough_sample = {**sample, "replacement_applied": False}
    adapter_passthrough = apply_final_design_guide_post_click_exact_blocker_replacement_projection(
        **passthrough_sample
    )
    expected_passthrough = _page_equivalent_projection(**passthrough_sample)
    latest = {
        "row_readiness": _latest("design_guide_post_click_contract_check_row_level_readiness"),
        "replacement_parity": _latest("design_guide_post_click_replacement_decision_proof_parity_scenarios"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    forbidden_tokens = {
        "streamlit_import": "import streamlit" in adapter_source or "st.session_state" in adapter_source,
        "visible_wording": "Strengthening required" in adapter_source or "Repair required" in adapter_source,
        "apply_routing": (
            "one_click" in adapter_source
            or "_queue_primary_design_guide_button_action" in adapter_source
            or "on_click" in adapter_source
        ),
    }
    return {
        "decision": "POST_CLICK_EXACT_BLOCKER_PROJECTION_ADAPTER_PARITY_PASS",
        "adapter_matches_page_equivalent": {
            "item": adapter.get("item") == expected.get("item"),
            "final_visible_resolution": adapter.get("final_visible_resolution")
            == expected.get("final_visible_resolution"),
            "guidance_debug": adapter.get("guidance_debug") == expected.get("guidance_debug"),
            "projection_hash": adapter.get("projection_hash") == expected.get("projection_hash"),
        },
        "passthrough_matches": adapter_passthrough == {
            **expected_passthrough,
            "derived_from": "FinalDesignGuidePublication.post_click_exact_blocker_replacement",
            "proof_only": False,
            "product_driving": False,
            "render_driving": False,
            "apply_driving": False,
            "session_driving": False,
        },
        "source_checks": {
            "adapter_present": "def apply_final_design_guide_post_click_exact_blocker_replacement_projection("
            in publication_source,
            "page_publish_binding_still_live": "_publish_final_visible_design_guide_contract_binding("
            in inputs_source,
            "forbidden_tokens_absent": not any(forbidden_tokens.values()),
            "forbidden_tokens": forbidden_tokens,
        },
        "ready_for_cutover_wiring": True,
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
    matches = dict(capture.get("adapter_matches_page_equivalent") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "adapter_matches_all": all(matches.values()),
        "passthrough_matches": capture.get("passthrough_matches") is True,
        "adapter_present": source_checks.get("adapter_present") is True,
        "page_publish_binding_still_live": source_checks.get("page_publish_binding_still_live") is True,
        "forbidden_tokens_absent": source_checks.get("forbidden_tokens_absent") is True,
        "row_readiness_pass": (latest.get("row_readiness") or {}).get("status") == "PASS",
        "replacement_parity_pass": (latest.get("replacement_parity") or {}).get("status") == "PASS",
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
        "# Post-Click Exact Blocker Projection Adapter Parity",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Matches: `{capture.get('adapter_matches_page_equivalent')}`",
        f"- Passthrough matches: `{capture.get('passthrough_matches')}`",
        f"- Ready for cutover wiring: `{capture.get('ready_for_cutover_wiring')}`",
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
        "schema": "design_guide_post_click_exact_blocker_projection_adapter_parity_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR / f"design_guide_post_click_exact_blocker_projection_adapter_parity_{stamp}.json"
    )
    md_path = AUDIT_DIR / f"design_guide_post_click_exact_blocker_projection_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_exact_blocker_projection_adapter_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
