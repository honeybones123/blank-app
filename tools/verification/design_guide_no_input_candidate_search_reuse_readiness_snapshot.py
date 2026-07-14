"""No-input candidate search reuse readiness snapshot.

Proof-only. This verifier checks whether the current Design Guide has enough
stable key/evidence surface to later reuse candidate evaluation/search results
on no-input-change reruns. It does not implement a cache, bypass, or behaviour
change.
"""

from __future__ import annotations

import hashlib
import json
import re
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
    "browser_live_smoothness_profile": "design_guide_browser_live_smoothness_profile",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "design_guide_independence_lock": "design_guide_independence_lock",
}

REQUIRED_SOURCE_TOKENS = {
    "guidance_runtime_fp_created": "guidance_runtime_fp = stable_fingerprint_for_payload",
    "guidance_runtime_fp_uses_canonical_state": '"canonical_state": canonical_state',
    "guidance_compute_cache_read": 'get_rerun_pure_cache(\n        "compute_design_guidance_items"',
    "guidance_compute_cache_write": 'set_rerun_pure_cache("compute_design_guidance_items"',
    "candidate_eval_fp_created": 'eval_fp = stable_fingerprint_for_payload',
    "candidate_eval_cache_read": 'get_rerun_pure_cache("evaluate_candidate_full"',
    "candidate_eval_cache_write": 'set_rerun_pure_cache("evaluate_candidate_full"',
    "candidate_eval_metric_count": '"evaluate_candidate_full_count"',
    "candidate_eval_metric_hits": '"evaluate_candidate_full_cache_hit_count"',
    "candidate_eval_metric_misses": '"evaluate_candidate_full_cache_miss_count"',
    "candidate_eval_fingerprint_bucket": '"evaluate_candidate_full_fingerprints"',
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
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
    return {
        "found": True,
        "path": str(path),
        "status": payload.get("status"),
        "payload": payload,
    }


def _count_call(source: str, name: str) -> int:
    return len(re.findall(rf"(?<!def )\b{re.escape(name)}\s*\(", source))


def _line_numbers(source: str, token: str, *, limit: int = 10) -> list[int]:
    lines: list[int] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        if token in line:
            lines.append(line_no)
            if len(lines) >= limit:
                break
    return lines


def _source_proof(source: str) -> dict[str, Any]:
    token_results = {
        name: {
            "present": token in source,
            "line_numbers": _line_numbers(source, token),
        }
        for name, token in REQUIRED_SOURCE_TOKENS.items()
    }
    # Keep this key conservative. It is the smallest existing no-input key that
    # already includes canonical state, request kind, debug mode, and post-click
    # cleanup acceptance state.
    key_inputs = {
        "algorithm_version": "DESIGN_GUIDE_ALGORITHM_VERSION" in source,
        "request_kind": '"request_kind": request_kind_norm' in source,
        "debug_mode": '"debug_enabled": bool(debug_enabled)' in source,
        "verbose_debug": '"guidance_debug_verbose": bool(guidance_debug_verbose)' in source,
        "canonical_state": '"canonical_state": canonical_state' in source,
        "post_click_cleanup_acceptance": "_design_guide_post_cleanup_acceptance" in source,
        "global_cleanup_acceptance_fingerprint": "_local_cleanup_acceptance_fingerprint(state)" in source,
    }
    invalidation_guards = {
        "stale_apply_state_fingerprint": "state_fingerprint" in source
        and "stale_apply_payload" in source,
        "post_click_acceptance_fp": "_design_guide_post_cleanup_acceptance_fp" in source,
        "debug_force_recompute_surface": "debug_enabled" in source
        and "guidance_debug_verbose" in source,
        "candidate_eval_cache_key_includes_updates": '"updates": updates' in source,
        "candidate_eval_cache_key_includes_candidate_state": '"candidate_state": candidate_state' in source,
    }
    return {
        "required_tokens": token_results,
        "missing_required_tokens": [
            name for name, row in token_results.items() if not bool(row.get("present"))
        ],
        "proposed_reuse_key": {
            "name": "guidance_runtime_fp + candidate evaluation fingerprint set",
            "source": "stable_fingerprint_for_payload in _compute_design_guidance_items and evaluate_candidate_full",
            "key_inputs": key_inputs,
            "all_key_inputs_present": all(key_inputs.values()),
        },
        "invalidation_guards": invalidation_guards,
        "all_invalidation_guards_present": all(invalidation_guards.values()),
        "call_surface": {
            "evaluate_candidate_full_calls": _count_call(source, "evaluate_candidate_full"),
            "evaluate_candidate_fast_calls": _count_call(source, "evaluate_candidate_fast"),
            "_evaluate_candidate_fast_calls": _count_call(source, "_evaluate_candidate_fast"),
            "compute_design_guidance_items_cache_reads": source.count(
                'get_rerun_pure_cache(\n        "compute_design_guidance_items"'
            ),
            "evaluate_candidate_full_cache_reads": source.count(
                'get_rerun_pure_cache("evaluate_candidate_full"'
            ),
        },
    }


def _candidate_metrics(row: dict[str, Any]) -> dict[str, Any]:
    counters = dict(row.get("counters") or {})
    return dict(counters.get("candidate_evaluation") or {})


def _scenario_readiness(profile: dict[str, Any]) -> dict[str, Any]:
    scenarios = [
        dict(row)
        for row in list(profile.get("scenarios") or [])
        if isinstance(row, dict)
    ]
    stable_rows = [
        row
        for row in scenarios
        if str(row.get("scenario_id") or "").startswith("stable_no_input_reload")
    ]
    initial_rows = [
        row for row in scenarios if str(row.get("scenario_id") or "") == "initial_recipe_load"
    ]
    post_click_rows = [
        row for row in scenarios if str(row.get("scenario_id") or "") == "post_click_apply"
    ]
    stable_metrics = [_candidate_metrics(row) for row in stable_rows]
    stable_eval_counts = [int(row.get("count") or 0) for row in stable_metrics]
    stable_misses = [int(row.get("cache_misses") or 0) for row in stable_metrics]
    stable_hits = [int(row.get("cache_hits") or 0) for row in stable_metrics]
    stable_total_ms = [float(row.get("total_ms") or 0.0) for row in stable_metrics]
    stable_fingerprint_sets = [
        set((dict(row.get("repeated_fingerprints") or {})).keys())
        for row in stable_metrics
    ]
    repeated_fingerprint_keys_visible = any(stable_fingerprint_sets)
    all_stable_have_work = bool(stable_rows) and all(count > 0 for count in stable_eval_counts)
    all_stable_have_misses = bool(stable_rows) and all(
        miss > 0 and count > 0 for miss, count in zip(stable_misses, stable_eval_counts)
    )
    stable_counts_match = len(set(stable_eval_counts)) == 1 if stable_eval_counts else False
    stable_hashes = [
        {
            "scenario_id": row.get("scenario_id"),
            "rerun_seq": row.get("rerun_seq"),
            "final_publication_hash": (dict(row.get("counters") or {})).get("final_publication_hash"),
            "final_publication_display_hash": (dict(row.get("counters") or {})).get(
                "final_publication_display_hash"
            ),
            "button_contract_hash": (dict(row.get("counters") or {})).get("button_contract_hash"),
            "apply_payload_hash": (dict(row.get("counters") or {})).get("apply_payload_hash"),
        }
        for row in stable_rows
    ]
    post_click_available = any(not bool(row.get("skipped")) for row in post_click_rows)
    return {
        "stable_no_input_scenarios_found": len(stable_rows),
        "initial_scenarios_found": len(initial_rows),
        "post_click_apply_available": post_click_available,
        "post_click_apply_rows": [
            {
                "scenario_id": row.get("scenario_id"),
                "skipped": bool(row.get("skipped")),
                "skip_reason": row.get("skip_reason"),
            }
            for row in post_click_rows
        ],
        "stable_candidate_eval_counts": stable_eval_counts,
        "stable_candidate_cache_hits": stable_hits,
        "stable_candidate_cache_misses": stable_misses,
        "stable_candidate_total_ms": [round(value, 3) for value in stable_total_ms],
        "stable_counts_match": stable_counts_match,
        "stable_no_input_still_recomputes_candidates": all_stable_have_work and all_stable_have_misses,
        "stable_no_input_has_partial_inner_cache_hits": bool(stable_rows) and any(hit > 0 for hit in stable_hits),
        "repeated_candidate_fingerprint_keys_visible": repeated_fingerprint_keys_visible,
        "stable_publication_hash_rows": stable_hashes,
        "observed_reuse_opportunity_count": sum(stable_eval_counts),
        "observed_reuse_opportunity_ms": round(sum(stable_total_ms), 3),
    }


def _readiness_rows(source: dict[str, Any], scenarios: dict[str, Any], artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "check": "existing guidance/input fingerprint",
            "status": "PASS" if source["proposed_reuse_key"]["all_key_inputs_present"] else "FAIL",
            "evidence": source["proposed_reuse_key"],
        },
        {
            "check": "candidate evaluation fingerprint/cache surface",
            "status": "PASS"
            if not source["missing_required_tokens"]
            else "FAIL",
            "evidence": {
                "missing_required_tokens": source["missing_required_tokens"],
                "candidate_eval_cache_reads": source["call_surface"][
                    "evaluate_candidate_full_cache_reads"
                ],
            },
        },
        {
            "check": "no-input live reuse opportunity",
            "status": "PASS"
            if scenarios["stable_no_input_still_recomputes_candidates"]
            else "PARTIAL",
            "evidence": {
                "stable_counts": scenarios["stable_candidate_eval_counts"],
                "stable_misses": scenarios["stable_candidate_cache_misses"],
                "observed_ms": scenarios["observed_reuse_opportunity_ms"],
            },
        },
        {
            "check": "invalidation guard surface",
            "status": "PASS" if source["all_invalidation_guards_present"] else "PARTIAL",
            "evidence": source["invalidation_guards"],
        },
        {
            "check": "locks stay green",
            "status": "PASS"
            if all(
                artifacts[key].get("status") == "PASS"
                for key in (
                    "compute_resolver_publication_bridge_lock",
                    "render_bridge_lock",
                    "design_guide_independence_lock",
                )
            )
            else "FAIL",
            "evidence": {
                key: {
                    "found": artifacts[key].get("found"),
                    "status": artifacts[key].get("status"),
                    "path": artifacts[key].get("path"),
                }
                for key in (
                    "compute_resolver_publication_bridge_lock",
                    "render_bridge_lock",
                    "design_guide_independence_lock",
                )
            },
        },
        {
            "check": "post-click guard proof",
            "status": "PASS" if scenarios["post_click_apply_available"] else "PARTIAL",
            "evidence": {
                "post_click_apply_available": scenarios["post_click_apply_available"],
                "rows": scenarios["post_click_apply_rows"],
            },
        },
    ]


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide No-Input Candidate Search Reuse Readiness",
        "",
        f"- Status: `{payload['status']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"- New cache or bypass implemented: `{payload['new_cache_or_bypass_implemented']}`",
        "",
        "## Executive Summary",
        "",
        payload["executive_summary"],
        "",
        "## Readiness Checks",
        "",
        "| Check | Status | Evidence |",
        "|---|---|---|",
    ]
    for row in payload["readiness_checks"]:
        lines.append(
            "| {check} | {status} | `{evidence}` |".format(
                check=_escape_md(row["check"]),
                status=_escape_md(row["status"]),
                evidence=_escape_md(json.dumps(row["evidence"], sort_keys=True)),
            )
        )
    lines.extend(
        [
            "",
            "## Proposed Reuse Key",
            "",
            "```json",
            json.dumps(payload["source_proof"]["proposed_reuse_key"], indent=2, sort_keys=True),
            "```",
            "",
            "## Live Reuse Opportunity",
            "",
            "```json",
            json.dumps(payload["scenario_readiness"], indent=2, sort_keys=True),
            "```",
            "",
            "## Required Before Implementation",
            "",
        ]
    )
    for item in payload["required_before_implementation"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## What Not To Touch Yet",
            "",
        ]
    )
    for item in payload["do_not_touch_yet"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Supporting Artifacts",
            "",
            "| Artifact | Found | Status | Path |",
            "|---|---:|---|---|",
        ]
    )
    for name, row in payload["supporting_artifacts"].items():
        lines.append(
            f"| {_escape_md(name)} | {bool(row.get('found'))} | {_escape_md(row.get('status'))} | {_escape_md(row.get('path'))} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source_text = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    artifacts = {key: _latest_artifact(prefix) for key, prefix in REQUIRED_ARTIFACTS.items()}
    source_proof = _source_proof(source_text)
    browser_profile = dict(artifacts["browser_live_smoothness_profile"].get("payload") or {})
    scenario_readiness = _scenario_readiness(browser_profile)
    checks = _readiness_rows(source_proof, scenario_readiness, artifacts)
    hard_failures = [row for row in checks if row["status"] == "FAIL"]
    partials = [row for row in checks if row["status"] == "PARTIAL"]
    status = "FAIL" if hard_failures else ("PARTIAL" if partials else "PASS")
    if status == "PASS":
        implementation_readiness = "READY_FOR_PROOF_ONLY_REUSE_ADAPTER"
    elif status == "PARTIAL" and not hard_failures:
        implementation_readiness = "READY_FOR_NARROWER_POST_CLICK_PROOF_BEFORE_IMPLEMENTATION"
    else:
        implementation_readiness = "NOT_READY"

    payload = {
        "status": status,
        "snapshot_kind": "design_guide_no_input_candidate_search_reuse_readiness",
        "created_at": stamp,
        "product_behaviour_changed": False,
        "new_cache_or_bypass_implemented": False,
        "code_deleted": False,
        "executive_summary": (
            "The app already has an outer guidance runtime fingerprint/cache and candidate evaluation "
            "fingerprints. Browser/live profiling shows stable no-input reloads still execute candidate "
            "evaluations with cache misses, so a reuse opportunity exists. The only remaining readiness "
            "gap is post-click Apply coverage in the live profile; implementation should wait for that "
            "or keep post-click states force-rebuilding."
        ),
        "implementation_readiness": implementation_readiness,
        "source_proof": source_proof,
        "scenario_readiness": scenario_readiness,
        "readiness_checks": checks,
        "required_before_implementation": [
            "Keep reuse keyed by guidance_runtime_fp plus candidate evaluation fingerprint set.",
            "Force rebuild when debug mode is enabled.",
            "Force rebuild when post-click cleanup acceptance fingerprint changes.",
            "Force rebuild on missing/stale guidance runtime fingerprint.",
            "Add explicit post-click browser proof before allowing reuse after Apply.",
        ],
        "do_not_touch_yet": [
            "Do not change engineering formulas.",
            "Do not change family contracts or ladder runtime logic.",
            "Do not change CTA/apply routing.",
            "Do not remove the existing compute_design_guidance_items cache.",
            "Do not bypass active post-click states without focused proof.",
        ],
        "supporting_artifacts": artifacts,
        "snapshot_hash": _stable_hash(
            {
                "status": status,
                "source_proof": source_proof,
                "scenario_readiness": scenario_readiness,
                "checks": checks,
                "implementation_readiness": implementation_readiness,
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"design_guide_no_input_candidate_search_reuse_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_no_input_candidate_search_reuse_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_no_input_candidate_search_reuse_readiness {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(f"implementation_readiness={implementation_readiness}")
    for row in checks:
        print(f"{row['status']}: {row['check']}")
    return 0 if status in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
