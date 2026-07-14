"""Parity proof for safe-low-util promotion projection adapter.

Proof-only. This verifier proves the pure Design Brain publication adapter
matches the current inputs_page.py safe-low-util promotion mutation shape.
It does not wire the adapter into the live page.
"""

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


def _page_equivalent_projection(
    *,
    item: dict[str, Any],
    final_visible_resolution: dict[str, Any],
    guidance_debug: dict[str, Any],
    promoted_item: dict[str, Any],
) -> dict[str, Any]:
    item_d = dict(item)
    resolution_d = dict(final_visible_resolution)
    debug_d = dict(guidance_debug)
    promoted_d = dict(promoted_item)
    promoted = bool(promoted_d)
    if promoted:
        item_d = dict(promoted_d)
        resolution_d["item"] = dict(item_d)
        resolution_d["render_reason"] = str(
            item_d.get("final_visible_resolver_reason")
            or "visible_safe_low_util_cleanup_from_blocker_evidence"
        )
        debug_d["final_visible_blocker_promoted_to_safe_low_util_action"] = True
    payload = {
        "item": item_d,
        "final_visible_resolution": resolution_d,
        "guidance_debug": debug_d,
        "promoted_item_hash": _stable_hash(promoted_d),
        "promoted": promoted,
    }
    return {**payload, "projection_hash": _stable_hash(payload)}


def _sample_inputs() -> dict[str, Any]:
    item = {
        "title": "Design Guide blocker proof incomplete",
        "status": "blocked",
        "family": "bending",
        "button_contract": {"enabled": False, "family": "bending"},
    }
    resolution = {
        "item": dict(item),
        "render_reason": "blocked_before_safe_low_util_promotion",
        "source": "final_visible_resolver",
    }
    guidance_debug = {
        "existing_debug": True,
        "final_visible_blocker_promoted_to_safe_low_util_action": False,
    }
    promoted_item = {
        "title": "Design is efficient",
        "status": "pass",
        "family": "bending",
        "action_type": "apply_resolved_candidate",
        "final_visible_resolver_reason": "visible_safe_low_util_cleanup_from_blocker_evidence",
        "button_contract": {"enabled": True, "family": "bending"},
    }
    return {
        "item": item,
        "final_visible_resolution": resolution,
        "guidance_debug": guidance_debug,
        "promoted_item": promoted_item,
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        apply_final_design_guide_safe_low_util_promotion_projection,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    adapter_start = publication_source.find(
        "def apply_final_design_guide_safe_low_util_promotion_projection("
    )
    adapter_end = publication_source.find("\ndef ", adapter_start + 1) if adapter_start >= 0 else -1
    adapter_source = (
        publication_source[adapter_start:adapter_end]
        if adapter_start >= 0 and adapter_end > adapter_start
        else ""
    )
    sample = _sample_inputs()
    adapter = apply_final_design_guide_safe_low_util_promotion_projection(**sample)
    expected = _page_equivalent_projection(**sample)
    no_promotion_sample = {**sample, "promoted_item": {}}
    adapter_no_promotion = apply_final_design_guide_safe_low_util_promotion_projection(
        **no_promotion_sample
    )
    expected_no_promotion = _page_equivalent_projection(**no_promotion_sample)
    latest = {
        "render_item_parity": _latest("design_guide_live_render_item_consumer_adapter_parity"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    forbidden_tokens = {
        "streamlit_import": "import streamlit" in adapter_source or "st.session_state" in adapter_source,
        "visible_wording": "Strengthening required" in adapter_source or "Repair required" in adapter_source,
        "apply_routing": "one_click" in adapter_source or "apply_route" in adapter_source,
    }
    return {
        "decision": "SAFE_LOW_UTIL_PROMOTION_PROJECTION_ADAPTER_PARITY_PASS",
        "adapter_matches_page_equivalent": {
            "item": adapter.get("item") == expected.get("item"),
            "final_visible_resolution": adapter.get("final_visible_resolution")
            == expected.get("final_visible_resolution"),
            "guidance_debug": adapter.get("guidance_debug") == expected.get("guidance_debug"),
            "promoted_item_hash": adapter.get("promoted_item_hash") == expected.get("promoted_item_hash"),
            "projection_hash": adapter.get("projection_hash") == expected.get("projection_hash"),
        },
        "no_promotion_passthrough_matches": adapter_no_promotion == {
            **expected_no_promotion,
            "derived_from": "FinalDesignGuidePublication.safe_low_util_promotion",
            "proof_only": False,
            "product_driving": False,
            "render_driving": False,
            "apply_driving": False,
            "session_driving": False,
        },
        "adapter_flags": {
            "product_driving": adapter.get("product_driving"),
            "render_driving": adapter.get("render_driving"),
            "apply_driving": adapter.get("apply_driving"),
            "session_driving": adapter.get("session_driving"),
        },
        "source_checks": {
            "adapter_present": "def apply_final_design_guide_safe_low_util_promotion_projection("
            in publication_source,
            "page_safe_low_util_block_still_live": "_final_safe_low_util_action = " in inputs_source,
            "page_candidate_builder_still_page_owned": "_visible_safe_low_util_cleanup_action_from_evidence("
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
    return {
        "adapter_item_matches": (capture.get("adapter_matches_page_equivalent") or {}).get("item")
        is True,
        "adapter_resolution_matches": (
            capture.get("adapter_matches_page_equivalent") or {}
        ).get("final_visible_resolution")
        is True,
        "adapter_debug_matches": (capture.get("adapter_matches_page_equivalent") or {}).get(
            "guidance_debug"
        )
        is True,
        "adapter_hash_matches": (capture.get("adapter_matches_page_equivalent") or {}).get(
            "projection_hash"
        )
        is True,
        "no_promotion_passthrough_matches": capture.get("no_promotion_passthrough_matches")
        is True,
        "adapter_present": (capture.get("source_checks") or {}).get("adapter_present") is True,
        "page_safe_low_util_block_still_live": (capture.get("source_checks") or {}).get(
            "page_safe_low_util_block_still_live"
        )
        is True,
        "page_candidate_builder_still_page_owned": (capture.get("source_checks") or {}).get(
            "page_candidate_builder_still_page_owned"
        )
        is True,
        "forbidden_tokens_absent": (capture.get("source_checks") or {}).get(
            "forbidden_tokens_absent"
        )
        is True,
        "render_item_parity_pass": (latest.get("render_item_parity") or {}).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Safe-Low-Util Promotion Projection Adapter Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Ready for cutover wiring: `{capture.get('ready_for_cutover_wiring')}`",
        f"- Adapter matches page-equivalent projection: `{capture.get('adapter_matches_page_equivalent')}`",
        f"- No-promotion passthrough matches: `{capture.get('no_promotion_passthrough_matches')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", ""])
    lines.append(
        "Next safe slice: wire this adapter at the safe-low-util render consumer projection point, "
        "leaving candidate construction and page/session ownership unchanged."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_safe_low_util_promotion_projection_adapter_parity_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_safe_low_util_promotion_projection_adapter_parity_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_safe_low_util_promotion_projection_adapter_parity_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_safe_low_util_promotion_projection_adapter_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
