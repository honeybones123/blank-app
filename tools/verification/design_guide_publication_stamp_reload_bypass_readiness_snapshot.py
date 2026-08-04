"""Readiness proof for reload-stable publication stamp bypass state.

The browser/live smoothness profile counts repeated publication stamp rebuilds
when stable reloads rebuild a fresh debug bundle. This snapshot proves whether
those rebuilds are only debug/compatibility stamp work and can be guarded by a
session-side publication-hash state without touching publication truth, CTA,
display, apply routing, visible wording, or family runtimes.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_CANDIDATES = {
    "duplicate_debug_session_publication_stamps",
    "repeated_verifier_debug_payload_stamping",
}


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": "UNREADABLE", "payload": {}, "error": str(exc)}
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _iter_publication_stamp_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in list(profile.get("scenarios") or []):
        counters = dict(scenario.get("counters") or {})
        for wrapper in list(counters.get("publication_stamp_decisions") or []):
            if not isinstance(wrapper, dict):
                continue
            candidate = str(wrapper.get("candidate") or "")
            nested = dict(wrapper.get(candidate) or {})
            if nested:
                row = dict(nested)
                row["scenario_id"] = scenario.get("scenario_id")
                rows.append(row)
    return rows


def _line_numbers(source: str, token: str) -> list[int]:
    return [
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if token in line
    ][:12]


def _build() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    profile_artifact = _latest("design_guide_browser_live_smoothness_profile")
    profile = dict(profile_artifact.get("payload") or {})
    rows = _iter_publication_stamp_rows(profile)
    target_rows = [row for row in rows if row.get("candidate_id") in TARGET_CANDIDATES]
    stable_rows = [row for row in target_rows if str(row.get("scenario_id") or "").startswith("stable_no_input")]
    safe_surface_rows = [
        row for row in target_rows
        if row.get("affects_final_publication") is False
        and row.get("affects_cta") is False
        and row.get("affects_display") is False
        and row.get("affects_apply_payload") is False
        and row.get("affects_visible_wording") is False
    ]
    stable_rebuilds_same_hash = bool(stable_rows) and len({row.get("publication_hash") for row in stable_rows}) == 1
    stable_rebuild_reasons = sorted({str(row.get("reason") or "") for row in stable_rows})
    source_checks = {
        "approved_candidates_constant_present": all(candidate in source for candidate in TARGET_CANDIDATES),
        "debug_force_rebuild_guard_present": "_final_publication_duplicate_stamp_debug_force_rebuild" in source,
        "existing_bypass_decision_helper_present": "def _final_publication_duplicate_stamp_bypass_decision" in source,
        "existing_rebuild_state_writer_present": "def _record_final_publication_duplicate_stamp_rebuild" in source,
        "current_state_is_debug_sink_local": 'debug_sink["final_publication_duplicate_stamp_bypass_state"]' in source,
        "no_product_surface_terms_in_candidate_rows": all(
            token in source
            for token in (
                "affects_final_publication",
                "affects_cta",
                "affects_display",
                "affects_apply_payload",
                "affects_visible_wording",
            )
        ),
    }
    readiness = {
        "latest_profile_found": bool(profile_artifact.get("found")),
        "latest_profile_status": profile_artifact.get("status"),
        "target_rows_found": len(target_rows),
        "stable_target_rows_found": len(stable_rows),
        "all_target_rows_safe_surface": len(target_rows) > 0 and len(target_rows) == len(safe_surface_rows),
        "stable_rebuilds_same_hash": stable_rebuilds_same_hash,
        "stable_rebuilds_are_missing_state_or_stamp": bool(stable_rows)
        and set(stable_rebuild_reasons).issubset({"missing_existing_stamp", "missing_previous_publication_hash"}),
        "ready_for_session_side_bypass_state": False,
    }
    readiness["ready_for_session_side_bypass_state"] = bool(
        readiness["latest_profile_found"]
        and len(stable_rows) >= 2
        and readiness["all_target_rows_safe_surface"]
        and readiness["stable_rebuilds_same_hash"]
        and readiness["stable_rebuilds_are_missing_state_or_stamp"]
        and all(source_checks.values())
    )
    errors: list[str] = []
    if not readiness["ready_for_session_side_bypass_state"]:
        errors.append("reload_stable_bypass_readiness_not_proven")
    payload = {
        "schema": "design_guide_publication_stamp_reload_bypass_readiness.v1",
        "status": "PASS" if not errors else "FAIL",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behavior_changed": False,
        "profile_artifact": {k: v for k, v in profile_artifact.items() if k != "payload"},
        "readiness": readiness,
        "stable_rebuild_reasons": stable_rebuild_reasons,
        "target_rows": target_rows,
        "source_checks": source_checks,
        "source_locations": {
            "bypass_decision_helper": _line_numbers(source, "def _final_publication_duplicate_stamp_bypass_decision"),
            "rebuild_state_writer": _line_numbers(source, "def _record_final_publication_duplicate_stamp_rebuild"),
            "target_candidate_ids": {
                candidate: _line_numbers(source, candidate)
                for candidate in sorted(TARGET_CANDIDATES)
            },
        },
        "next_slice": (
            "Implement a session-side, publication-hash keyed bypass state for only the two target "
            "debug/compatibility stamp candidates; keep debug-force, stale/missing hash, and missing "
            "stamp rebuild guards."
        ),
        "errors": errors,
    }
    return payload


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_publication_stamp_reload_bypass_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_publication_stamp_reload_bypass_readiness_{stamp}.md"
    lines = [
        "# Design Guide Publication Stamp Reload Bypass Readiness",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Readiness",
        "",
    ]
    for key, value in payload["readiness"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Stable Rebuild Reasons", ""])
    for reason in payload["stable_rebuild_reasons"]:
        lines.append(f"- `{reason}`")
    lines.extend(["", "## Next Slice", "", payload["next_slice"], ""])
    if payload["errors"]:
        lines.extend(["## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_publication_stamp_reload_bypass_readiness {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["errors"]:
        print("errors=" + json.dumps(payload["errors"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
