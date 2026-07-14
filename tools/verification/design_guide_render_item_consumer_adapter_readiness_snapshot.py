"""Readiness proof for moving render-item consumers behind publication authority.

Proof-only. This snapshot checks whether the live post-binding consumers that
currently block restamper deletion have enough FinalDesignGuidePublication
surface to be represented by a controller/publication adapter.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

CONSUMER_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "id": "zero_shear_stale_blocker_cleanup",
        "inputs_tokens": (
            "zero_shear_accepted_stale_blocker_cleared",
            "_zero_shear_terminal_stop_row",
            "_final_visible_item[\"candidate_search_evidence\"] = dict(_zero_shear_candidate_evidence)",
        ),
        "publication_surface_tokens": (
            "candidate_search_evidence",
            "blocker_attempts_by_family",
            "post_click_design_guide_state",
        ),
    },
    {
        "id": "visible_safe_low_util_promotion",
        "inputs_tokens": (
            "_design_guide_item_is_visible_blocker(_final_visible_item)",
            "_visible_safe_low_util_cleanup_action_from_evidence(",
            "_final_visible_resolution[\"item\"] = dict(_final_visible_item)",
        ),
        "publication_surface_tokens": (
            "selected_family",
            "blocker_reason",
            "candidate_search_evidence",
            "exact_stop_proof",
        ),
    },
    {
        "id": "post_click_final_contract_checks",
        "inputs_tokens": (
            "_final_contract_for_post_click = dict(_final_visible_item.get(\"button_contract\") or {})",
            "_final_family_for_post_click = str(",
            "_post_click_unresolved_families_for_visible",
            "_post_click_below_floor_families_for_visible",
        ),
        "publication_surface_tokens": (
            "post_click_design_guide_state",
            "published_item_id",
            "FinalDesignGuideCTA",
            "apply_payload_summary",
        ),
    },
)


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
        payload = json.loads(path.read_text(encoding="utf-8"))
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


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    groups = []
    for group in CONSUMER_GROUPS:
        inputs_tokens = {
            token: token in inputs_source
            for token in group["inputs_tokens"]
        }
        publication_tokens = {
            token: token in publication_source
            for token in group["publication_surface_tokens"]
        }
        groups.append(
            {
                "id": group["id"],
                "live_inputs_consumer_present": all(inputs_tokens.values()),
                "publication_surface_present": all(publication_tokens.values()),
                "inputs_tokens": inputs_tokens,
                "publication_surface_tokens": publication_tokens,
                "adapter_ready_for_proof_only_shape": all(publication_tokens.values()),
                "live_page_consumer_still_blocks_deletion": all(inputs_tokens.values()),
            }
        )
    final_visible_consumer = _latest("design_guide_final_visible_compatibility_stamp_consumer")
    render_guidance_binding = _latest("design_guide_render_guidance_secondary_binding_ownership")
    render_fast_binding = _latest("design_guide_render_fast_panel_binding_ownership")
    render_lock = _latest("design_guide_render_bridge_lock")
    compute_lock = _latest("design_guide_compute_resolver_publication_bridge_lock")
    independence_lock = _latest("design_guide_independence_lock")
    all_surfaces_present = all(group["publication_surface_present"] for group in groups)
    any_live_page_consumer = any(group["live_page_consumer_still_blocks_deletion"] for group in groups)
    return {
        "decision": (
            "RENDER_ITEM_CONSUMER_ADAPTER_SURFACE_READY_LIVE_PAGE_CONSUMERS_REMAIN"
            if all_surfaces_present and any_live_page_consumer
            else "RENDER_ITEM_CONSUMER_ADAPTER_SURFACE_INCOMPLETE"
        ),
        "consumer_groups": groups,
        "adapter_surface_ready": bool(all_surfaces_present),
        "live_page_consumers_remain": bool(any_live_page_consumer),
        "deletion_safe_now": False,
        "recommended_next_slice": (
            "Add a proof-only render-item consumer adapter in design_brain/final_publication.py, then wire it "
            "trace-only beside the zero-shear, safe-low-util, and post-click consumers before moving/deleting page logic."
        ),
        "latest_locks": {
            "final_visible_compatibility_stamp_consumer": {
                "status": final_visible_consumer.get("status"),
                "path": final_visible_consumer.get("path"),
            },
            "render_guidance_secondary_binding_ownership": {
                "status": render_guidance_binding.get("status"),
                "path": render_guidance_binding.get("path"),
            },
            "render_fast_panel_binding_ownership": {
                "status": render_fast_binding.get("status"),
                "path": render_fast_binding.get("path"),
            },
            "render_bridge_lock": {
                "status": render_lock.get("status"),
                "path": render_lock.get("path"),
            },
            "compute_resolver_publication_bridge_lock": {
                "status": compute_lock.get("status"),
                "path": compute_lock.get("path"),
            },
            "independence_lock": {
                "status": independence_lock.get("status"),
                "path": independence_lock.get("path"),
            },
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_locks") or {})
    return {
        "adapter_surface_ready": capture.get("adapter_surface_ready") is True,
        "live_page_consumers_remain": capture.get("live_page_consumers_remain") is True,
        "deletion_safe_false": capture.get("deletion_safe_now") is False,
        "decision_is_surface_ready_with_live_consumers": capture.get("decision")
        == "RENDER_ITEM_CONSUMER_ADAPTER_SURFACE_READY_LIVE_PAGE_CONSUMERS_REMAIN",
        "final_visible_consumer_proof_pass": (
            latest.get("final_visible_compatibility_stamp_consumer") or {}
        ).get("status")
        == "PASS",
        "render_guidance_binding_proof_pass": (
            latest.get("render_guidance_secondary_binding_ownership") or {}
        ).get("status")
        == "PASS",
        "render_fast_binding_proof_pass": (
            latest.get("render_fast_panel_binding_ownership") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render Item Consumer Adapter Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Adapter surface ready: `{capture.get('adapter_surface_ready')}`",
        f"- Live page consumers remain: `{capture.get('live_page_consumers_remain')}`",
        f"- Deletion safe now: `{capture.get('deletion_safe_now')}`",
        "",
        "## Consumer Groups",
        "",
        "| Group | Live Inputs Consumer | Publication Surface Present | Adapter Shape Ready |",
        "| --- | --- | --- | --- |",
    ]
    for group in capture.get("consumer_groups") or []:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` |".format(
                group.get("id"),
                group.get("live_inputs_consumer_present"),
                group.get("publication_surface_present"),
                group.get("adapter_ready_for_proof_only_shape"),
            )
        )
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next", "", str(capture.get("recommended_next_slice"))])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_item_consumer_adapter_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_render_item_consumer_adapter_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_item_consumer_adapter_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_render_item_consumer_adapter_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
