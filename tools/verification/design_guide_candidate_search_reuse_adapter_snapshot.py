"""Proof-only candidate search/evaluation reuse adapter snapshot.

This does not implement a live cache or bypass. It proves the decision contract
for a future no-input-change candidate search reuse adapter.
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

REQUIRED_ARTIFACTS = {
    "candidate_search_reuse_readiness": "design_guide_no_input_candidate_search_reuse_readiness",
    "reload_publication_hash_drift_audit": "design_guide_no_input_reload_publication_hash_drift_audit",
    "browser_live_smoothness_profile": "design_guide_browser_live_smoothness_profile",
    "next_smoothness_hotspot_audit": "design_guide_next_smoothness_hotspot_audit",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _candidate_reuse_decision(
    *,
    current_guidance_runtime_fp: str | None,
    previous_guidance_runtime_fp: str | None,
    current_candidate_fingerprint_set_hash: str | None,
    previous_candidate_fingerprint_set_hash: str | None,
    current_post_click_cleanup_acceptance_fp: str | None,
    previous_post_click_cleanup_acceptance_fp: str | None,
    debug_mode: bool = False,
    apply_in_flight: bool = False,
    post_click_unsafe_state: bool = False,
    missing_previous_payload: bool = False,
) -> dict[str, Any]:
    checks = {
        "has_current_guidance_runtime_fp": bool(current_guidance_runtime_fp),
        "has_previous_guidance_runtime_fp": bool(previous_guidance_runtime_fp),
        "guidance_runtime_fp_unchanged": bool(
            current_guidance_runtime_fp
            and previous_guidance_runtime_fp
            and current_guidance_runtime_fp == previous_guidance_runtime_fp
        ),
        "has_current_candidate_fingerprint_set": bool(current_candidate_fingerprint_set_hash),
        "has_previous_candidate_fingerprint_set": bool(previous_candidate_fingerprint_set_hash),
        "candidate_fingerprint_set_unchanged": bool(
            current_candidate_fingerprint_set_hash
            and previous_candidate_fingerprint_set_hash
            and current_candidate_fingerprint_set_hash == previous_candidate_fingerprint_set_hash
        ),
        "post_click_cleanup_acceptance_fp_unchanged": bool(
            current_post_click_cleanup_acceptance_fp
            and previous_post_click_cleanup_acceptance_fp
            and current_post_click_cleanup_acceptance_fp == previous_post_click_cleanup_acceptance_fp
        ),
        "debug_mode_off": not debug_mode,
        "apply_not_in_flight": not apply_in_flight,
        "post_click_state_safe": not post_click_unsafe_state,
        "previous_payload_available": not missing_previous_payload,
    }
    reuse_allowed = all(checks.values())
    rebuild_reasons = [name for name, ok in checks.items() if not ok]
    return {
        "reuse_allowed": reuse_allowed,
        "rebuild_required": not reuse_allowed,
        "rebuild_reasons": rebuild_reasons,
        "checks": checks,
        "decision_hash": _stable_hash(checks),
        "adapter_contract": (
            "guidance_runtime_fp+candidate_fingerprint_set+post_click_cleanup_acceptance_fp"
        ),
    }


def _scenario_rows() -> list[dict[str, Any]]:
    base = {
        "current_guidance_runtime_fp": "runtime-A",
        "previous_guidance_runtime_fp": "runtime-A",
        "current_candidate_fingerprint_set_hash": "candidate-set-A",
        "previous_candidate_fingerprint_set_hash": "candidate-set-A",
        "current_post_click_cleanup_acceptance_fp": "acceptance-A",
        "previous_post_click_cleanup_acceptance_fp": "acceptance-A",
    }
    scenarios = [
        ("stable_no_input_reuse", {}, True),
        ("changed_guidance_runtime_rebuild", {"current_guidance_runtime_fp": "runtime-B"}, False),
        ("changed_candidate_fingerprint_set_rebuild", {"current_candidate_fingerprint_set_hash": "candidate-set-B"}, False),
        ("changed_post_click_acceptance_rebuild", {"current_post_click_cleanup_acceptance_fp": "acceptance-B"}, False),
        ("missing_current_runtime_rebuild", {"current_guidance_runtime_fp": None}, False),
        ("missing_previous_payload_rebuild", {"missing_previous_payload": True}, False),
        ("debug_mode_rebuild", {"debug_mode": True}, False),
        ("apply_in_flight_rebuild", {"apply_in_flight": True}, False),
        ("post_click_unsafe_state_rebuild", {"post_click_unsafe_state": True}, False),
    ]
    rows: list[dict[str, Any]] = []
    for scenario_id, override, expected_reuse in scenarios:
        payload = {**base, **override}
        decision = _candidate_reuse_decision(**payload)
        rows.append(
            {
                "scenario_id": scenario_id,
                "expected_reuse_allowed": expected_reuse,
                "decision": decision,
                "expected_met": decision["reuse_allowed"] is expected_reuse,
            }
        )
    return rows


def _source_checks(source: str) -> dict[str, bool]:
    return {
        "guidance_runtime_fp_exists": "guidance_runtime_fp = stable_fingerprint_for_payload" in source,
        "guidance_runtime_cache_exists": (
            'get_rerun_pure_cache(\n        "compute_design_guidance_items"' in source
            and 'set_rerun_pure_cache("compute_design_guidance_items"' in source
        ),
        "candidate_evaluation_fp_exists": 'eval_fp = stable_fingerprint_for_payload' in source,
        "candidate_evaluation_cache_exists": (
            'get_rerun_pure_cache("evaluate_candidate_full"' in source
            and 'set_rerun_pure_cache("evaluate_candidate_full"' in source
        ),
        "candidate_eval_metrics_exist": all(
            token in source
            for token in (
                '"evaluate_candidate_full_count"',
                '"evaluate_candidate_full_cache_hit_count"',
                '"evaluate_candidate_full_cache_miss_count"',
                '"evaluate_candidate_full_fingerprints"',
            )
        ),
        "post_click_cleanup_acceptance_fingerprint_exists": (
            "_design_guide_post_cleanup_acceptance_fp" in source
            and "_local_cleanup_acceptance_fingerprint(state)" in source
        ),
        "debug_mode_guard_surface_exists": (
            '"debug_enabled": bool(debug_enabled)' in source
            and '"guidance_debug_verbose": bool(guidance_debug_verbose)' in source
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Candidate Search Reuse Adapter Snapshot",
        "",
        f"- Status: `{payload['status']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"- Live cache/bypass implemented: `{payload['live_cache_or_bypass_implemented']}`",
        "",
        "## Scenario Decisions",
        "",
        "| Scenario | Reuse allowed | Expected | Rebuild reasons |",
        "|---|---:|---:|---|",
    ]
    for row in payload["scenario_rows"]:
        decision = row["decision"]
        lines.append(
            "| {scenario} | {reuse} | {expected} | `{reasons}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                reuse=decision["reuse_allowed"],
                expected=row["expected_reuse_allowed"],
                reasons=_escape_md(", ".join(decision["rebuild_reasons"])),
            )
        )
    lines.extend(["", "## Source Checks", "", "| Check | PASS |", "|---|---:|"])
    for key, value in payload["source_checks"].items():
        lines.append(f"| `{_escape_md(key)}` | `{value}` |")
    lines.extend(["", "## Supporting Artifacts", "", "| Artifact | Found | Status | Path |", "|---|---:|---|---|"])
    for key, row in payload["supporting_artifacts"].items():
        lines.append(
            f"| {_escape_md(key)} | {bool(row.get('found'))} | {_escape_md(row.get('status'))} | {_escape_md(row.get('path'))} |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            payload["next_safe_step"],
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    artifacts = {key: _latest(prefix) for key, prefix in REQUIRED_ARTIFACTS.items()}
    source_checks = _source_checks(source)
    rows = _scenario_rows()
    failures = []
    for key, value in source_checks.items():
        if value is not True:
            failures.append(f"source_check_failed::{key}")
    for row in rows:
        if row["expected_met"] is not True:
            failures.append(f"scenario_failed::{row['scenario_id']}")
    for key, row in artifacts.items():
        if row.get("status") != "PASS":
            failures.append(f"supporting_artifact_not_passed::{key}")
    passed = not failures
    payload = {
        "status": "PASS" if passed else "FAIL",
        "schema": "design_guide_candidate_search_reuse_adapter_snapshot.v1",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "live_cache_or_bypass_implemented": False,
        "scenario_rows": rows,
        "source_checks": source_checks,
        "supporting_artifacts": {
            key: {"found": value.get("found"), "status": value.get("status"), "path": value.get("path")}
            for key, value in artifacts.items()
        },
        "failures": failures,
        "snapshot_hash": _stable_hash(
            {
                "rows": rows,
                "source_checks": source_checks,
                "supporting_artifacts": {
                    key: value.get("path") for key, value in artifacts.items()
                },
            }
        ),
        "next_safe_step": (
            "Implement a live no-input candidate-search reuse gate only after this adapter proof is "
            "wired trace-only beside the existing compute_design_guidance_items cache and proves parity."
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_candidate_search_reuse_adapter_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_search_reuse_adapter_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_candidate_search_reuse_adapter_snapshot {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print(f"failures={json.dumps(failures)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
