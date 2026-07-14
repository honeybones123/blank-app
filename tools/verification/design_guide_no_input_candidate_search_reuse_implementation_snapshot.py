"""Stable no-input candidate-search reuse implementation snapshot.

Verifies the narrow live implementation of the candidate-search reuse cache.
The cache is allowed to skip repeated candidate evaluation/search only when the
Design Guide runtime fingerprint is unchanged and no guarded post-click/debug
or stale payload state is active.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

REQUIRED_LOCKS = {
    "adapter_readiness": "design_guide_no_input_candidate_search_reuse_adapter_readiness",
    "post_click_guard": "design_guide_post_click_candidate_search_reuse_guard",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "design_guide_independence_lock": "design_guide_independence_lock",
}

REQUIRED_FORCE_REBUILD_REASONS = (
    "missing_runtime_fingerprint",
    "debug_mode_enabled",
    "post_click_apply_in_flight",
    "post_click_cleanup_acceptance_enabled",
    "post_click_cleanup_acceptance_fingerprint_present",
    "stale_apply_payload_or_state_fingerprint_mismatch",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = paths[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot_status": snapshot.get("status"),
        "snapshot_hash": snapshot.get("snapshot_hash") or snapshot.get("profile_hash"),
        "passed": snapshot.get("status") == "PASS",
    }


def _slice_between(source: str, start_token: str, end_token: str | None = None) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    if end_token is None:
        return source[start:]
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        return source[start:]
    return source[start:end]


def _source_guards(input_source: str, final_source: str) -> dict[str, bool]:
    compute_body = _slice_between(
        input_source,
        "def _compute_design_guidance_items(",
        "def _design_guide_guidance_compute_inputs(",
    )
    get_helper = _slice_between(
        input_source,
        "def _design_guide_candidate_search_reuse_get(",
        "def _design_guide_candidate_search_reuse_store(",
    )
    store_helper = _slice_between(
        input_source,
        "def _design_guide_candidate_search_reuse_store(",
        "def _finalize_compute_design_guidance_items_output(",
    )
    disabled_helper = _slice_between(
        input_source,
        "def _design_guide_candidate_search_reuse_disabled_reason(",
        "def _design_guide_candidate_search_reuse_get(",
    )
    finalize_body = _slice_between(
        input_source,
        "def _finalize_compute_design_guidance_items_output(",
        "def _resolve_compute_design_guidance_publication_handoff(",
    )
    return {
        "cache_key_constant_exists": "_DESIGN_GUIDE_CANDIDATE_SEARCH_REUSE_CACHE_KEY" in input_source,
        "cache_limit_exists": "_DESIGN_GUIDE_CANDIDATE_SEARCH_REUSE_CACHE_LIMIT" in input_source,
        "key_hash_helper_exists": "def _design_guide_candidate_search_reuse_key_hash(" in input_source,
        "disabled_reason_helper_exists": "def _design_guide_candidate_search_reuse_disabled_reason(" in input_source,
        "get_helper_exists": "def _design_guide_candidate_search_reuse_get(" in input_source,
        "store_helper_exists": "def _design_guide_candidate_search_reuse_store(" in input_source,
        "all_force_rebuild_guards_present": all(
            reason in input_source for reason in REQUIRED_FORCE_REBUILD_REASONS
        ),
        "stale_apply_guard_uses_state_fingerprint": (
            "_design_guide_primary_apply_state_fingerprint(_shared_state_snapshot())" in input_source
            and "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY" in input_source
        ),
        "get_path_records_reuse_hit": "candidate_search_reuse_decision" in get_helper
        and "REUSE_HIT" in get_helper,
        "get_path_records_force_rebuild": "FORCE_REBUILD" in get_helper,
        "get_path_deep_copies_payload": "copy.deepcopy(payload)" in get_helper,
        "store_path_deep_copies_payload": "copy.deepcopy(payload)" in store_helper,
        "store_path_bounded": "_DESIGN_GUIDE_CANDIDATE_SEARCH_REUSE_CACHE_LIMIT" in store_helper,
        "compute_reads_reuse_before_rerun_cache": (
            compute_body.find("_design_guide_candidate_search_reuse_get(") >= 0
            and compute_body.find('get_rerun_pure_cache(\n        "compute_design_guidance_items"') >= 0
            and compute_body.find("_design_guide_candidate_search_reuse_get(")
            < compute_body.find('get_rerun_pure_cache(\n        "compute_design_guidance_items"')
        ),
        "reuse_hit_returns_boundary_attached_output": (
            "stable_no_input_candidate_search_reuse_hit" in compute_body
            and "_attach_design_brain_result_boundary(" in compute_body
        ),
        "coherence_return_stores_reuse": "coherence_blocked_return" in compute_body
        and "_design_guide_candidate_search_reuse_store(guidance_runtime_fp, out)" in compute_body,
        "early_dispatch_return_stores_reuse": (
            "_design_guide_candidate_search_reuse_store(guidance_runtime_fp, early_dispatch_out)" in compute_body
        ),
        "not_started_return_stores_reuse": "not_started_return" in compute_body
        and "_design_guide_candidate_search_reuse_store(guidance_runtime_fp, out)" in compute_body,
        "final_output_stores_reuse": "_design_guide_candidate_search_reuse_store(guidance_runtime_fp, out)" in finalize_body,
        "speed_diag_counters_exist": all(
            token in input_source
            for token in (
                "candidate_search_reuse_hit_count",
                "candidate_search_reuse_miss_count",
                "candidate_search_reuse_force_rebuild_count",
                "candidate_search_reuse_last_decision",
            )
        ),
        "speed_diag_note_helper_exists": "def _dg_speed_diag_note_candidate_search_reuse(" in input_source,
        "no_final_publication_imports_page": "inputs_page" not in final_source,
        "no_streamlit_in_final_publication": "streamlit" not in final_source,
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in input_source
            and "_record_rendered_design_guide_primary_apply_payload" not in final_source
        ),
        "rendering_remains_page_owned": (
            "_design_guide_dashboard_card_html_from_render_model" in input_source
            and "_design_guide_dashboard_card_html_from_render_model" not in final_source
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Stable No-Input Candidate-Search Reuse Implementation Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Ready and implemented: `{payload['ready_for_live_stable_reuse']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        f"- Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Source Guards",
        "",
        "| Guard | PASS |",
        "| --- | --- |",
    ]
    for key, value in payload["source_guards"].items():
        lines.append(f"| `{_escape_md(key)}` | `{value}` |")
    lines.extend(["", "## Required Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
    lines.extend(["", "## Force-Rebuild Reasons", ""])
    for reason in payload["force_rebuild_reasons"]:
        lines.append(f"- `{reason}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Step", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
    source_guards = _source_guards(input_source, final_source)

    failures: list[str] = []
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    for key, value in source_guards.items():
        if value is not True:
            failures.append(f"source_guard_failed::{key}")

    passed = not failures
    payload: dict[str, Any] = {
        "schema": "design_guide_no_input_candidate_search_reuse_implementation_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "source_guards": source_guards,
        "locks": locks,
        "force_rebuild_reasons": list(REQUIRED_FORCE_REBUILD_REASONS),
        "ready_for_live_stable_reuse": passed,
        "product_behavior_changed": False,
        "recommended_next_slice": (
            "Run browser/live impact profiling for stable no-input candidate-search reuse, "
            "then move to layout/first-paint gap profiling."
        ),
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "source_guards": source_guards,
            "locks": {name: lock.get("path") for name, lock in locks.items()},
            "force_rebuild_reasons": payload["force_rebuild_reasons"],
            "product_behavior_changed": payload["product_behavior_changed"],
        }
    )

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    artifact_path = ARTIFACT_DIR / f"design_guide_no_input_candidate_search_reuse_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_no_input_candidate_search_reuse_implementation_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"status={payload['status']}")
    print(f"artifact={artifact_path}")
    print(f"report={report_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
