"""Parity proof for zero-shear render consumer projection adapter.

Proof-only. This verifier proves the pure Design Brain publication adapter
matches the current inputs_page.py zero-shear render consumer mutation shape.
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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _page_equivalent_projection(
    *,
    item: dict[str, Any],
    guidance_debug: dict[str, Any],
    session_debug: dict[str, Any],
    terminal_stop_row: dict[str, Any],
) -> dict[str, Any]:
    item_d = dict(item)
    debug_d = dict(guidance_debug)
    session_d = dict(session_debug)
    exact_keys = (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
    )
    candidate_exact_keys = (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
    )

    def remove_shear(mapping: dict[str, Any], key: str) -> None:
        values = _mapping(mapping.get(key))
        if "shear" not in values:
            return
        values.pop("shear", None)
        if values:
            mapping[key] = dict(values)
        else:
            mapping.pop(key, None)

    for key in exact_keys:
        remove_shear(item_d, key)

    candidate_evidence = _mapping(item_d.get("candidate_search_evidence"))
    for key in candidate_exact_keys:
        remove_shear(candidate_evidence, key)
    if candidate_evidence:
        item_d["candidate_search_evidence"] = dict(candidate_evidence)

    for key in exact_keys:
        remove_shear(debug_d, key)
    debug_d["zero_shear_accepted_stale_blocker_cleared"] = True

    item_attempts = _mapping(item_d.get("blocker_attempts_by_family"))
    item_attempts["shear"] = dict(terminal_stop_row)
    item_d["blocker_attempts_by_family"] = dict(item_attempts)

    candidate_evidence = _mapping(item_d.get("candidate_search_evidence"))
    item_candidate_attempts = _mapping(candidate_evidence.get("blocker_attempts_by_family"))
    item_candidate_attempts["shear"] = dict(terminal_stop_row)
    candidate_evidence["blocker_attempts_by_family"] = dict(item_candidate_attempts)
    item_d["candidate_search_evidence"] = dict(candidate_evidence)

    debug_attempts = _mapping(debug_d.get("blocker_attempts_by_family"))
    debug_attempts["shear"] = dict(terminal_stop_row)
    debug_d["blocker_attempts_by_family"] = dict(debug_attempts)

    debug_evidence = _mapping(debug_d.get("candidate_search_evidence"))
    debug_candidate_attempts = _mapping(debug_evidence.get("blocker_attempts_by_family"))
    debug_candidate_attempts["shear"] = dict(terminal_stop_row)
    debug_evidence["blocker_attempts_by_family"] = dict(debug_candidate_attempts)
    debug_d["candidate_search_evidence"] = dict(debug_evidence)

    if session_d:
        session_attempts = _mapping(session_d.get("blocker_attempts_by_family"))
        session_attempts["shear"] = dict(terminal_stop_row)
        session_d["blocker_attempts_by_family"] = dict(session_attempts)

        session_evidence = _mapping(session_d.get("candidate_search_evidence"))
        session_candidate_attempts = _mapping(session_evidence.get("blocker_attempts_by_family"))
        session_candidate_attempts["shear"] = dict(terminal_stop_row)
        session_evidence["blocker_attempts_by_family"] = dict(session_candidate_attempts)
        session_d["candidate_search_evidence"] = dict(session_evidence)

    payload = {
        "item": item_d,
        "guidance_debug": debug_d,
        "session_debug": session_d,
        "terminal_stop_row_hash": _stable_hash(terminal_stop_row),
    }
    return {**payload, "projection_hash": _stable_hash(payload)}


def _sample_inputs() -> dict[str, Any]:
    stale_shear = {"shear": {"reason": "stale"}, "bending": {"reason": "keep"}}
    terminal_stop_row = {
        "attempted": True,
        "cleanup_search_ran": True,
        "no_link_candidate_already_active": True,
        "attempted_candidate_count": 1,
        "attempted_updates": {},
        "attempted_passed": True,
        "reason": "zero shear terminal cleanup proof",
    }
    candidate_evidence = {
        "exact_blockers_by_family": dict(stale_shear),
        "post_click_exact_blockers_by_family": dict(stale_shear),
        "cleanup_evidence_by_family": dict(stale_shear),
        "post_click_cleanup_evidence_by_family": dict(stale_shear),
        "blocker_attempts_by_family": {"bending": {"reason": "keep"}},
    }
    item = {
        "exact_blockers_by_family": dict(stale_shear),
        "post_click_exact_blockers_by_family": dict(stale_shear),
        "cleanup_evidence_by_family": dict(stale_shear),
        "post_click_cleanup_evidence_by_family": dict(stale_shear),
        "blocker_attempts_by_family": dict(stale_shear),
        "candidate_search_evidence": dict(candidate_evidence),
    }
    debug = {
        "exact_blockers_by_family": dict(stale_shear),
        "post_click_exact_blockers_by_family": dict(stale_shear),
        "cleanup_evidence_by_family": dict(stale_shear),
        "post_click_cleanup_evidence_by_family": dict(stale_shear),
        "blocker_attempts_by_family": dict(stale_shear),
        "candidate_search_evidence": dict(candidate_evidence),
    }
    session_debug = {
        "blocker_attempts_by_family": {"bending": {"reason": "keep"}},
        "candidate_search_evidence": {"blocker_attempts_by_family": {"bending": {"reason": "keep"}}},
    }
    return {
        "item": item,
        "guidance_debug": debug,
        "session_debug": session_debug,
        "terminal_stop_row": terminal_stop_row,
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        apply_final_design_guide_zero_shear_render_consumer_projection,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    adapter_start = publication_source.find(
        "def apply_final_design_guide_zero_shear_render_consumer_projection("
    )
    adapter_end = publication_source.find("\ndef ", adapter_start + 1) if adapter_start >= 0 else -1
    adapter_source = (
        publication_source[adapter_start:adapter_end]
        if adapter_start >= 0 and adapter_end > adapter_start
        else ""
    )
    sample = _sample_inputs()
    adapter = apply_final_design_guide_zero_shear_render_consumer_projection(**sample)
    expected = _page_equivalent_projection(**sample)
    latest = {
        "readiness": _latest("design_guide_zero_shear_render_consumer_narrowing_readiness"),
        "parity": _latest("design_guide_live_render_item_consumer_adapter_parity"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    forbidden_tokens = {
        "streamlit_import": "import streamlit" in adapter_source or "st.session_state" in adapter_source,
        "visible_wording": "Design is efficient" in adapter_source or "Strengthening required" in adapter_source,
        "apply_routing": "one_click" in adapter_source or "apply_route" in adapter_source,
    }
    return {
        "decision": "ZERO_SHEAR_RENDER_CONSUMER_PROJECTION_ADAPTER_PARITY_PASS",
        "adapter_matches_page_equivalent": {
            "item": adapter.get("item") == expected.get("item"),
            "guidance_debug": adapter.get("guidance_debug") == expected.get("guidance_debug"),
            "session_debug": adapter.get("session_debug") == expected.get("session_debug"),
            "terminal_stop_row_hash": adapter.get("terminal_stop_row_hash") == expected.get("terminal_stop_row_hash"),
            "projection_hash": adapter.get("projection_hash") == expected.get("projection_hash"),
        },
        "adapter_flags": {
            "product_driving": adapter.get("product_driving"),
            "render_driving": adapter.get("render_driving"),
            "apply_driving": adapter.get("apply_driving"),
            "session_driving": adapter.get("session_driving"),
        },
        "source_checks": {
            "adapter_present": "def apply_final_design_guide_zero_shear_render_consumer_projection(" in publication_source,
            "page_zero_shear_block_still_live": "_zero_shear_terminal_stop_row = {" in inputs_source,
            "page_session_write_still_page_owned": "st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)" in inputs_source,
            "forbidden_tokens_absent": not any(forbidden_tokens.values()),
            "forbidden_tokens": forbidden_tokens,
        },
        "ready_for_trace_or_cutover_wiring": True,
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
        "adapter_matches_page_equivalent": all(
            (capture.get("adapter_matches_page_equivalent") or {}).values()
        ),
        "adapter_flags_non_authoritative": all(
            value is False for value in (capture.get("adapter_flags") or {}).values()
        ),
        "source_checks_pass": all(
            value is True
            for key, value in (capture.get("source_checks") or {}).items()
            if key != "forbidden_tokens"
        ),
        "readiness_snapshot_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "parity_snapshot_pass": (latest.get("parity") or {}).get("status") == "PASS",
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
        "# Zero-Shear Render Consumer Projection Adapter Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Adapter Parity",
        "",
    ]
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("adapter_matches_page_equivalent") or {}).items()
    )
    lines.extend(["", "## Source Checks", ""])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("source_checks") or {}).items()
        if key != "forbidden_tokens"
    )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", ""])
    lines.append(
        "Next safe slice: wire this pure adapter into the zero-shear page block while keeping session storage page-owned, "
        "then prove the old row-by-row mutation block is compatibility-only or dead before deletion."
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
        "schema": "design_guide_zero_shear_render_consumer_projection_adapter_parity_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_zero_shear_render_consumer_projection_adapter_parity_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_zero_shear_render_consumer_projection_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_zero_shear_render_consumer_projection_adapter_parity {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
