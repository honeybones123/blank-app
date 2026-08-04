"""Proof-only readiness for no-input-change candidate search reuse.

This verifier checks whether the existing Design Guide/input fingerprint and
publication authority hashes are stable enough to justify a future candidate
evaluation/search reuse bridge. It does not implement a cache or bypass.
"""

from __future__ import annotations

from datetime import datetime
import glob
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(pattern: str) -> Path | None:
    matches = [Path(path) for path in glob.glob(str(ARTIFACT_DIR / pattern))]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "output_tail": proc.stdout[-4000:],
    }


def _line_number(source: str, needle: str) -> int | None:
    index = source.find(needle)
    if index < 0:
        return None
    return source.count("\n", 0, index) + 1


def _source_inventory() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    checks = {
        "design_guide_fingerprint_function": "def _get_design_guide_fp(",
        "candidate_cache_key_function": "def _candidate_cache_key(",
        "guidance_cache_getter": "def _get_cached_design_guide_guidance(",
        "guidance_cache_setter": "def _set_cached_design_guide_guidance(",
        "local_candidate_eval_cache": "eval_cache_by_candidate_fp",
        "global_eval_cache": "_global_eval_cache",
        "cache_invalidation": "def _invalidate_design_guide_caches(",
        "guidance_apply_invalidates_cache": "_invalidate_design_guide_caches(",
        "debug_mode_guard": "def _design_guide_sidebar_debug_enabled(",
        "post_apply_preview_evaluation": 'source=f"{source}:post_apply_preview"',
    }
    return {
        key: {
            "present": needle in source,
            "line": _line_number(source, needle),
            "needle": needle,
        }
        for key, needle in checks.items()
    }


def _rerun_stability(profile: dict[str, Any]) -> dict[str, Any]:
    cls = dict(profile.get("classification") or {})
    compared = dict(cls.get("compared_hashes") or {})
    def matches(key: str) -> bool:
        row = dict(compared.get(key) or {})
        return bool(row.get("matches"))
    return {
        "source_artifact": str(profile.get("_path") or ""),
        "status": profile.get("status"),
        "state_fingerprint_stable": matches("state_fingerprint"),
        "design_guide_publication_fingerprint_stable": matches("design_guide_publication_fingerprint"),
        "final_publication_authority_hash_stable": matches("final_publication_authority_hash"),
        "final_publication_display_hash_stable": matches("final_publication_display_hash"),
        "stable_publication_or_state_hashes": bool(cls.get("stable_publication_or_state_hashes")),
        "pending_flags_after_reload": dict(cls.get("pending_flags_after_reload") or {}),
        "likely_sources": list(cls.get("likely_sources") or []),
    }


def _hotspot_profile(profile: dict[str, Any]) -> dict[str, Any]:
    hotspots = list(profile.get("all_hotspot_scores") or [])
    candidate = next(
        (
            dict(item)
            for item in hotspots
            if "candidate evaluation/search" in str(item.get("name") or "").lower()
        ),
        {},
    )
    evidence = dict(candidate.get("evidence") or {})
    return {
        "source_artifact": str(profile.get("_path") or ""),
        "status": profile.get("status"),
        "candidate_hotspot_present": bool(candidate),
        "candidate_hotspot_class": candidate.get("class"),
        "candidate_hotspot_score": candidate.get("score"),
        "candidate_evaluation_count": int(evidence.get("candidate_evaluation_count") or 0),
        "candidate_cache_misses": int(evidence.get("candidate_cache_misses") or 0),
        "candidate_total_ms": float(evidence.get("candidate_total_ms") or 0.0),
        "recommended_first_fix": profile.get("recommended_first_fix"),
    }


def _classify(*, source_inventory: dict[str, Any], rerun: dict[str, Any], hotspot: dict[str, Any], locks: list[dict[str, Any]]) -> dict[str, Any]:
    required_source = (
        "design_guide_fingerprint_function",
        "candidate_cache_key_function",
        "local_candidate_eval_cache",
        "cache_invalidation",
        "guidance_apply_invalidates_cache",
        "debug_mode_guard",
    )
    source_ready = all(bool(source_inventory.get(key, {}).get("present")) for key in required_source)
    stable_key_ready = all(
        bool(rerun.get(key))
        for key in (
            "state_fingerprint_stable",
            "design_guide_publication_fingerprint_stable",
            "final_publication_authority_hash_stable",
            "final_publication_display_hash_stable",
        )
    )
    hotspot_material = (
        bool(hotspot.get("candidate_hotspot_present"))
        and int(hotspot.get("candidate_evaluation_count") or 0) > 0
        and int(hotspot.get("candidate_cache_misses") or 0) > 0
    )
    locks_pass = all(bool(row.get("passed")) for row in locks)
    guard_matrix = {
        "rebuild_on_changed_state_fingerprint": True,
        "rebuild_on_changed_design_guide_fingerprint": True,
        "rebuild_on_changed_final_publication_authority_hash": True,
        "rebuild_on_changed_final_publication_display_hash": True,
        "rebuild_on_missing_hash": True,
        "rebuild_on_debug_mode": True,
        "rebuild_on_post_click_apply_in_flight": True,
        "rebuild_on_missing_cached_search_result": True,
        "rebuild_on_changed_family_result": True,
        "reuse_only_for_no_input_change": True,
    }
    ready_for_trace_bridge = source_ready and stable_key_ready and hotspot_material and locks_pass
    ready_for_live_reuse = False
    if ready_for_trace_bridge:
        diagnosis = "READY_FOR_TRACE_ONLY_REUSE_BRIDGE_NOT_LIVE_CACHE"
        next_slice = (
            "Wire a trace-only candidate-search reuse decision beside the current "
            "search path and prove hash parity across normal, changed-input, debug, "
            "post-click, stale/missing-hash, and family-result-change cases."
        )
    elif not stable_key_ready:
        diagnosis = "BLOCKED_BY_UNSTABLE_REUSE_KEY"
        next_slice = "Stabilize state/publication hashes before any candidate search reuse bridge."
    elif not hotspot_material:
        diagnosis = "NO_MATERIAL_CANDIDATE_SEARCH_HOTSPOT_IN_LATEST_PROFILE"
        next_slice = "Refresh browser/live smoothness profile with a candidate-search-heavy recipe."
    else:
        diagnosis = "SOURCE_OR_LOCK_GAP"
        next_slice = "Resolve missing source surface or failing lock before reuse work."
    return {
        "status": "PASS" if ready_for_trace_bridge or not locks_pass else "PARTIAL",
        "diagnosis": diagnosis,
        "source_ready": source_ready,
        "stable_reuse_key_ready": stable_key_ready,
        "candidate_hotspot_material": hotspot_material,
        "locks_pass": locks_pass,
        "ready_for_trace_only_reuse_bridge": ready_for_trace_bridge,
        "ready_for_live_candidate_search_reuse": ready_for_live_reuse,
        "guard_matrix": guard_matrix,
        "remaining_proof_before_live_cache": [
            "trace-only live reuse decision bridge",
            "parity scenarios for stable rerun, changed input, missing hash, stale hash, debug mode, post-click/apply in flight",
            "proof that reused result includes same selected family, selected candidate, button contract, and FinalDesignGuidePublication hashes",
        ],
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Candidate Search Reuse Readiness Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Ready for trace-only reuse bridge: `{cls.get('ready_for_trace_only_reuse_bridge')}`",
        f"- Ready for live candidate-search reuse/cache: `{cls.get('ready_for_live_candidate_search_reuse')}`",
        f"- Stable reuse key ready: `{cls.get('stable_reuse_key_ready')}`",
        f"- Candidate hotspot material: `{cls.get('candidate_hotspot_material')}`",
        "",
        "## Hotspot Evidence",
        "",
        "```json",
        json.dumps(payload.get("hotspot_profile") or {}, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Rerun Stability Evidence",
        "",
        "```json",
        json.dumps(payload.get("rerun_stability") or {}, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Guard Matrix",
        "",
        "```json",
        json.dumps(cls.get("guard_matrix") or {}, indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
    ]
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_candidate_search_reuse_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_search_reuse_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    created_at = _stamp()
    rerun_path = _latest("design_guide_rerun_trigger_source_profile_*.json")
    hotspot_path = _latest("design_guide_browser_live_smoothness_profile_*.json")
    rerun_profile = _read_json(rerun_path)
    hotspot_json = _read_json(hotspot_path)
    if rerun_path:
        rerun_profile["_path"] = str(rerun_path)
    if hotspot_path:
        hotspot_json["_path"] = str(hotspot_path)
    locks = [
        _run([sys.executable, "tools/verification/design_guide_independence_lock_verifier.py"]),
        _run([sys.executable, "tools/verification/design_guide_render_bridge_lock_verifier.py"]),
        _run([sys.executable, "tools/verification/design_guide_compute_resolver_publication_bridge_lock_verifier.py"]),
    ]
    source_inventory = _source_inventory()
    rerun = _rerun_stability(rerun_profile)
    hotspot = _hotspot_profile(hotspot_json)
    classification = _classify(
        source_inventory=source_inventory,
        rerun=rerun,
        hotspot=hotspot,
        locks=locks,
    )
    payload = {
        "schema": "design_guide_candidate_search_reuse_readiness.v1",
        "created_at": created_at,
        "status": classification["status"],
        "classification": classification,
        "product_behaviour_changed": False,
        "behaviour_scope": {
            "cache_or_bypass_implemented": False,
            "publication_changed": False,
            "cta_apply_changed": False,
            "family_runtime_changed": False,
            "visible_wording_changed": False,
            "engineering_behaviour_changed": False,
        },
        "source_inventory": source_inventory,
        "rerun_stability": rerun,
        "hotspot_profile": hotspot,
        "lock_runs": locks,
    }
    json_path, md_path = _write(payload)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "diagnosis": classification["diagnosis"],
                "ready_for_trace_only_reuse_bridge": classification[
                    "ready_for_trace_only_reuse_bridge"
                ],
                "ready_for_live_candidate_search_reuse": classification[
                    "ready_for_live_candidate_search_reuse"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if all(row.get("passed") for row in locks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
