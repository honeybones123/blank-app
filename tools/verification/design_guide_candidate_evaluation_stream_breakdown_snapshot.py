"""Break down remaining browser/live Design Guide candidate evaluation streams.

Proof-only. Reads the latest PASS browser/live smoothness profile and classifies
candidate evaluation work by scenario and source labels. It does not implement
caches, bypasses, deletions, or product behaviour changes.
"""

from __future__ import annotations

import argparse
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


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest_profile_path() -> Path:
    candidates = sorted(
        ARTIFACT_DIR.glob("design_guide_browser_live_smoothness_profile_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    pass_profiles: list[Path] = []
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("status") == "PASS":
            pass_profiles.append(path)
    if not pass_profiles:
        raise FileNotFoundError("No PASS design_guide_browser_live_smoothness_profile artifact found")
    return pass_profiles[-1]


def _speed_diag(row: dict[str, Any]) -> dict[str, Any]:
    timing = dict(row.get("timing") or {})
    event = dict(timing.get("design_guide_build_end") or {})
    meta = dict(event.get("meta") or {})
    return dict(meta.get("dg_speed_diag") or {})


def _classify_source(source: str, label: str, action_type: str) -> str:
    text = f"{source} {label} {action_type}".lower()
    if "post_click" in text or "cleanup" in text:
        return "post_click_cleanup_probe"
    if "restamp" in text or "final_visible" in text or "publish_visible" in text:
        return "publication_or_restamp_probe"
    if "primary_payload_current_state_guard" in text or "payload" in text:
        return "cta_payload_guard_probe"
    if "family_preview" in text or "family" in text:
        return "family_preview_or_runtime_required"
    if "guidance:" in text or "compute" in text:
        return "guidance_compute_probe"
    if not text.strip():
        return "unlabelled_candidate_eval"
    return "other_labelled_candidate_eval"


def _row_breakdown(row: dict[str, Any]) -> dict[str, Any]:
    diag = _speed_diag(row)
    repeated = [dict(item) for item in list(diag.get("top_repeated_candidate_fingerprints") or []) if isinstance(item, dict)]
    streams: dict[str, dict[str, Any]] = {}
    for item in repeated:
        meta = dict(item.get("last_meta") or {})
        bucket = _classify_source(
            str(meta.get("source") or ""),
            str(meta.get("label") or ""),
            str(meta.get("action_type") or ""),
        )
        stream = streams.setdefault(
            bucket,
            {
                "fingerprint_rows": 0,
                "observed_repeated_count": 0,
                "observed_cache_hits": 0,
                "observed_total_ms": 0.0,
                "examples": [],
            },
        )
        stream["fingerprint_rows"] += 1
        stream["observed_repeated_count"] += int(item.get("count") or 0)
        stream["observed_cache_hits"] += int(item.get("cache_hit_count") or 0)
        stream["observed_total_ms"] = round(float(stream["observed_total_ms"]) + float(item.get("total_ms") or 0.0), 3)
        if len(stream["examples"]) < 5:
            stream["examples"].append(
                {
                    "fingerprint_sha1": item.get("fingerprint_sha1"),
                    "count": item.get("count"),
                    "cache_hit_count": item.get("cache_hit_count"),
                    "total_ms": item.get("total_ms"),
                    "source": meta.get("source"),
                    "label": meta.get("label"),
                    "action_type": meta.get("action_type"),
                }
            )
    return {
        "scenario_id": row.get("scenario_id"),
        "elapsed_ms": row.get("elapsed_ms"),
        "candidate_search_reuse": {
            "hit_count": int(diag.get("candidate_search_reuse_hit_count") or 0),
            "miss_count": int(diag.get("candidate_search_reuse_miss_count") or 0),
            "force_rebuild_count": int(diag.get("candidate_search_reuse_force_rebuild_count") or 0),
            "last_decision": dict(diag.get("candidate_search_reuse_last_decision") or {}),
        },
        "evaluation": {
            "evaluate_candidate_full_count": int(diag.get("evaluate_candidate_full_count") or 0),
            "evaluate_candidate_full_cache_hit_count": int(diag.get("evaluate_candidate_full_cache_hit_count") or 0),
            "evaluate_candidate_full_cache_miss_count": int(diag.get("evaluate_candidate_full_cache_miss_count") or 0),
            "evaluate_candidate_full_total_ms": float(diag.get("evaluate_candidate_full_total_ms") or 0.0),
            "duplicate_candidate_fingerprint_count": int(diag.get("duplicate_candidate_fingerprint_count") or 0),
        },
        "streams": streams,
    }


def _capture(profile_path: Path) -> dict[str, Any]:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    rows = [_row_breakdown(dict(row)) for row in list(profile.get("scenarios") or [])]
    totals = {
        "evaluate_candidate_full_count": sum(int((row.get("evaluation") or {}).get("evaluate_candidate_full_count") or 0) for row in rows),
        "evaluate_candidate_full_cache_hit_count": sum(
            int((row.get("evaluation") or {}).get("evaluate_candidate_full_cache_hit_count") or 0) for row in rows
        ),
        "evaluate_candidate_full_cache_miss_count": sum(
            int((row.get("evaluation") or {}).get("evaluate_candidate_full_cache_miss_count") or 0) for row in rows
        ),
        "evaluate_candidate_full_total_ms": round(
            sum(float((row.get("evaluation") or {}).get("evaluate_candidate_full_total_ms") or 0.0) for row in rows),
            3,
        ),
        "duplicate_candidate_fingerprint_count": sum(
            int((row.get("evaluation") or {}).get("duplicate_candidate_fingerprint_count") or 0) for row in rows
        ),
        "candidate_search_reuse_hits": sum(
            int((row.get("candidate_search_reuse") or {}).get("hit_count") or 0) for row in rows
        ),
        "candidate_search_reuse_misses": sum(
            int((row.get("candidate_search_reuse") or {}).get("miss_count") or 0) for row in rows
        ),
        "candidate_search_reuse_force_rebuilds": sum(
            int((row.get("candidate_search_reuse") or {}).get("force_rebuild_count") or 0) for row in rows
        ),
    }
    stream_totals: dict[str, dict[str, Any]] = {}
    for row in rows:
        for stream_name, stream in dict(row.get("streams") or {}).items():
            total = stream_totals.setdefault(
                stream_name,
                {
                    "fingerprint_rows": 0,
                    "observed_repeated_count": 0,
                    "observed_cache_hits": 0,
                    "observed_total_ms": 0.0,
                    "examples": [],
                },
            )
            total["fingerprint_rows"] += int(stream.get("fingerprint_rows") or 0)
            total["observed_repeated_count"] += int(stream.get("observed_repeated_count") or 0)
            total["observed_cache_hits"] += int(stream.get("observed_cache_hits") or 0)
            total["observed_total_ms"] = round(
                float(total["observed_total_ms"]) + float(stream.get("observed_total_ms") or 0.0),
                3,
            )
            total["examples"].extend(list(stream.get("examples") or [])[: max(0, 5 - len(total["examples"]))])
    return {
        "profile_path": str(profile_path),
        "profile_status": profile.get("status"),
        "profile_recipe": profile.get("recipe"),
        "profile_hash": profile.get("profile_hash"),
        "rows": rows,
        "totals": totals,
        "stream_totals": stream_totals,
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    totals = dict(capture.get("totals") or {})
    streams = dict(capture.get("stream_totals") or {})
    eval_count = int(totals.get("evaluate_candidate_full_count") or 0)
    duplicate_count = int(totals.get("duplicate_candidate_fingerprint_count") or 0)
    force_rebuilds = int(totals.get("candidate_search_reuse_force_rebuilds") or 0)
    post_click_rows = [
        row
        for row in list(capture.get("rows") or [])
        if str(row.get("scenario_id") or "") == "post_click_apply"
    ]
    post_click_eval_count = sum(int((row.get("evaluation") or {}).get("evaluate_candidate_full_count") or 0) for row in post_click_rows)
    publication_stream_present = "publication_or_restamp_probe" in streams
    post_click_cleanup_present = "post_click_cleanup_probe" in streams
    if eval_count <= 0:
        diagnosis = "NO_CANDIDATE_EVALUATION_OBSERVED"
        next_slice = "Refresh browser/live smoothness profile with an actionable recipe."
    elif duplicate_count <= 0:
        diagnosis = "CANDIDATE_EVALUATION_UNIQUE_WORK_DOMINATES"
        next_slice = "Profile family/runtime-required evaluation cost before bypass work."
    else:
        diagnosis = "CANDIDATE_EVALUATION_STREAMS_CLASSIFIED"
        next_slice = (
            "Add focused proof for repeated post-click cleanup and publication/restamp probes before any "
            "additional candidate-evaluation bypass."
        )
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "profile_recipe": capture.get("profile_recipe"),
        "eval_count": eval_count,
        "eval_cache_hits": int(totals.get("evaluate_candidate_full_cache_hit_count") or 0),
        "eval_cache_misses": int(totals.get("evaluate_candidate_full_cache_miss_count") or 0),
        "eval_total_ms": float(totals.get("evaluate_candidate_full_total_ms") or 0.0),
        "duplicate_candidate_fingerprint_count": duplicate_count,
        "candidate_search_reuse_hits": int(totals.get("candidate_search_reuse_hits") or 0),
        "candidate_search_reuse_misses": int(totals.get("candidate_search_reuse_misses") or 0),
        "candidate_search_reuse_force_rebuilds": force_rebuilds,
        "post_click_eval_count": post_click_eval_count,
        "stream_names": sorted(streams),
        "publication_or_restamp_stream_present": publication_stream_present,
        "post_click_cleanup_stream_present": post_click_cleanup_present,
        "ready_for_additional_bypass": False,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Candidate Evaluation Stream Breakdown",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Profile recipe: `{cls.get('profile_recipe')}`",
        f"- Eval count: `{cls.get('eval_count')}`",
        f"- Eval cache hits: `{cls.get('eval_cache_hits')}`",
        f"- Eval cache misses: `{cls.get('eval_cache_misses')}`",
        f"- Eval total ms: `{cls.get('eval_total_ms')}`",
        f"- Duplicate candidate fingerprints: `{cls.get('duplicate_candidate_fingerprint_count')}`",
        f"- Candidate-search reuse hits: `{cls.get('candidate_search_reuse_hits')}`",
        f"- Candidate-search reuse misses: `{cls.get('candidate_search_reuse_misses')}`",
        f"- Candidate-search force rebuilds: `{cls.get('candidate_search_reuse_force_rebuilds')}`",
        f"- Ready for additional bypass: `{cls.get('ready_for_additional_bypass')}`",
        "",
        "## Stream Totals",
        "",
        "```json",
        json.dumps(payload.get("stream_totals") or {}, indent=2, sort_keys=True, default=str)[:12000],
        "```",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
    ]
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_candidate_evaluation_stream_breakdown_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_evaluation_stream_breakdown_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="")
    args = parser.parse_args(argv)
    profile_path = Path(args.profile) if args.profile else _latest_profile_path()
    created_at = _stamp()
    capture = _capture(profile_path)
    classification = _classify(capture)
    payload = {
        "schema": "design_guide_candidate_evaluation_stream_breakdown_snapshot.v1",
        "created_at": created_at,
        "status": classification["status"],
        "product_behaviour_changed": False,
        "code_deleted": False,
        "new_bypass_or_cache_implemented": False,
        "classification": classification,
        "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
        **capture,
    }
    json_path, md_path = _write(payload)
    print(f"design_guide_candidate_evaluation_stream_breakdown {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(json.dumps(classification, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
