from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

FOCUSED_PREFIXES: tuple[str, ...] = (
    "design_guide_cta_apply_binding_bypass_implementation",
    "design_guide_cta_apply_binding_bypass_live_impact",
    "design_guide_duplicate_publication_stamp_bypass_implementation",
    "design_guide_duplicate_publication_stamp_bypass_live_impact",
    "design_guide_card_render_model_bypass_implementation",
    "design_guide_card_render_model_bypass_live_impact",
    "design_guide_stable_publication_summary_render_reuse_readiness",
    "design_guide_stable_publication_summary_render_reuse_implementation",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _status_from_payload(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status"):
        value = payload.get(key)
        if isinstance(value, str):
            upper = value.upper()
            if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
                return "PASS"
            if "PARTIAL" in upper:
                return "PARTIAL"
            if "FAIL" in upper or "BLOCKED" in upper:
                return "FAIL"
            return upper
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return "UNKNOWN"


def _latest_payload(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": "MISSING"}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "payload": payload, "status": _status_from_payload(payload)}


def _source_checks() -> dict[str, bool]:
    inputs_source = _read(INPUTS_PAGE)
    final_source = _read(FINAL_PUBLICATION)
    summary_start = inputs_source.find('_summary_html_cache_key = "_final_publication_summary_card_html_cache"')
    summary_end = inputs_source.find('ux_probe_record(\n            "summary.card_html_build_reuse"', summary_start)
    summary_block = inputs_source[summary_start:summary_end] if summary_start >= 0 and summary_end > summary_start else ""
    return {
        "stable_hash_helper_imported": "stable_final_publication_hash as _stable_final_publication_hash" in inputs_source,
        "final_publication_hash_helper_exists": "def stable_final_publication_hash(" in final_source,
        "cta_apply_bypass_key_includes_cta_payload_state": (
            "FinalDesignGuidePublication.cta_hash+apply_payload_hash+state_fingerprint" in inputs_source
        ),
        "cta_apply_rebuilds_on_missing_current_hashes": all(
            token in inputs_source
            for token in (
                "missing_current_cta_hash",
                "missing_current_payload_hash",
                "missing_current_state_fingerprint",
            )
        ),
        "cta_apply_rebuilds_on_stale_hashes": all(
            token in inputs_source
            for token in (
                "stale_or_changed_cta_hash",
                "stale_or_changed_payload_hash",
                "stale_or_changed_state_fingerprint",
            )
        ),
        "cta_apply_rebuilds_on_debug_or_apply_in_flight": (
            "debug_force_rebuild" in inputs_source and "post_click_or_apply_in_flight" in inputs_source
        ),
        "duplicate_stamp_bypass_keyed_by_publication_hash": (
            "publication_hash_unchanged" in inputs_source
            and "missing_current_publication_hash" in inputs_source
            and "stale_or_changed_publication_hash" in inputs_source
        ),
        "card_render_model_bypass_keyed_by_display_hash": (
            "card_render_model_bypassed" in inputs_source
            and "missing_current_display_hash" in inputs_source
            and "stale_or_changed_display_hash" in inputs_source
        ),
        "summary_html_reuse_keyed_by_result_summary_state": (
            "_final_publication_summary_card_html_cache" in summary_block
            and "summary_action_fp" in summary_block
            and "result_cache_hash" in summary_block
            and "RESULT_CACHE_KEY" in summary_block
            and "show_landing" in summary_block
        ),
        "summary_html_reuse_excludes_transient_design_guide_fingerprints": (
            '"state_fingerprint": str(' not in summary_block
            and '"panel_baseline_fingerprint": str(' not in summary_block
            and "final_publication_authority_hash" not in summary_block
            and "final_publication_display_hash" not in summary_block
        ),
        "summary_html_reuse_keeps_visible_render_path": "summary.card_html_build_reuse" in inputs_source
        and "st.markdown(f'<div class=\"summary-card-stack\">{summary_cards_html}</div>'" in inputs_source,
        "apply_in_flight_guard_available": "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY" in inputs_source,
        "design_brain_no_streamlit_cache_import": "streamlit" not in final_source and "st." not in final_source,
    }


def _guarded_case_checks(payload: dict[str, Any]) -> dict[str, bool]:
    checks = dict(payload.get("checks") or {})
    scenario_rows = payload.get("scenario_rows") or payload.get("scenarios") or payload.get("scenario_decisions") or []
    if checks:
        return {str(key): bool(value) for key, value in checks.items()}
    if payload.get("ready_for_non_debug_bypass") is True:
        contract = dict(payload.get("bypass_contract") or {})
        rebuild_when = set(str(item) for item in contract.get("rebuild_when") or [])
        return {
            "stable_skip_case_seen": True,
            "all_expected_guarded_cases_met": {
                "debug_force_rebuild",
                "missing_current_publication_hash",
                "missing_previous_publication_hash",
                "stale_or_changed_publication_hash",
            }
            <= rebuild_when,
        }
    if "stable_non_debug_bypass_hits" in payload or "rerun_without_input_changes_bypass_hits" in payload:
        return {
            "stable_skip_case_seen": int(payload.get("stable_non_debug_bypass_hits") or 0) > 0
            and int(payload.get("rerun_without_input_changes_bypass_hits") or 0) > 0,
            "all_expected_guarded_cases_met": int(payload.get("forced_rebuilds_in_guarded_cases") or 0) > 0
            and not bool(payload.get("failures")),
        }
    guarded_ok = True
    stable_skip_seen = False
    def _visit(row: Any) -> None:
        nonlocal guarded_ok, stable_skip_seen
        if isinstance(row, dict):
            expected_met = row.get("expected_met")
            if expected_met is False:
                guarded_ok = False
            decision = str(row.get("decision") or "")
            if "SKIP" in decision:
                stable_skip_seen = True
            for child in row.values():
                _visit(child)
        elif isinstance(row, list):
            for child in row:
                _visit(child)
    _visit(scenario_rows)
    return {
        "stable_skip_case_seen": stable_skip_seen,
        "all_expected_guarded_cases_met": guarded_ok,
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Shared Publication Hash / Cache Reuse Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This lock covers guarded reuse/bypass surfaces keyed by FinalDesignGuidePublication publication/display/CTA hashes, Apply payload hash, and state fingerprints.",
        "",
        "## Ownership",
        "",
        "- FinalDesignGuidePublication owns stable hash material.",
        "- Page shell may reuse render/debug/cache products only when identical fingerprints are proven.",
        "- Debug, missing, stale, changed, post-click, and apply-in-flight states must rebuild.",
        "",
        "## Source Checks",
        "",
    ]
    for key, value in snapshot.get("source_checks", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Focused Artifacts", ""])
    for prefix, row in (snapshot.get("focused_artifacts") or {}).items():
        lines.append(f"- `{prefix}`: `{row.get('status')}` at `{row.get('path')}`")
    if snapshot.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in snapshot["blockers"])
    lines.extend(
        [
            "",
            "## Result",
            "",
            "The component is lockable only when every reuse surface has focused stale-state proof and current source guards.",
            "",
            f"JSON: `{snapshot['artifact']}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    focused = {prefix: _latest_payload(prefix) for prefix in FOCUSED_PREFIXES}
    source_checks = _source_checks()

    blockers: list[str] = []
    for key, passed in source_checks.items():
        if not passed:
            blockers.append(f"source check failed: {key}")
    for prefix, row in focused.items():
        if row.get("status") != "PASS":
            blockers.append(f"focused artifact is not PASS: {prefix}")
        guard_checks = _guarded_case_checks(dict(row.get("payload") or {}))
        failed_guards = sorted(key for key, passed in guard_checks.items() if not passed)
        if failed_guards:
            blockers.append(f"guarded-case checks failed for {prefix}: {', '.join(failed_guards)}")

    status = "LOCKED" if not blockers else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_shared_publication_hash_cache_reuse_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_publication_hash_cache_reuse_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_publication_hash_cache_reuse_lock.v1",
        "status": status,
        "lock_status": status,
        "component": "publication hashes/cache reuse",
        "source_checks": source_checks,
        "focused_artifacts": {
            prefix: {"status": row.get("status"), "path": row.get("path")}
            for prefix, row in focused.items()
        },
        "guarded_case_checks": {
            prefix: _guarded_case_checks(dict(row.get("payload") or {}))
            for prefix, row in focused.items()
        },
        "blockers": list(dict.fromkeys(blockers)),
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_shared_publication_hash_cache_reuse_lock {status}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    if blockers:
        print("blockers=" + "; ".join(snapshot["blockers"]))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
