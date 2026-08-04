"""Classify remaining browser/live Design Guide family trace gaps.

Proof-only verifier. It does not drive product behaviour. It consumes the
latest family browser/live visual consistency snapshot and classifies remaining
non-visual observations into concrete fix buckets.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_live_visual_consistency_snapshot import (  # noqa: E402
    _stable_hash,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _datetime_stamp() -> str:
    return datetime.now().replace(microsecond=0).isoformat().replace(":", "-")


def _latest_visual_snapshot() -> Path | None:
    candidates = sorted(
        ARTIFACT_DIR.glob("design_guide_family_browser_live_visual_consistency_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("schema") == "design_guide_family_browser_live_visual_consistency_snapshot.v1":
            return candidate
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _text_sample(row: dict[str, Any]) -> str:
    return str(_as_dict(row.get("design_guide")).get("text_sample") or "")


def _is_lightweight_state(row: dict[str, Any]) -> bool:
    state = _as_dict(row.get("browser_state"))
    return bool(
        state.get("pre_page_render_lightweight")
        or "pre_page_render_lightweight" in set(state.get("top_level_keys") or [])
    )


def _has_final_publication_payload(row: dict[str, Any]) -> bool:
    state = _as_dict(row.get("browser_state"))
    payload = _as_dict(state.get("final_publication_verifier_payload"))
    hashes = _as_dict(state.get("final_publication_hashes"))
    return bool(payload.get("publication_hash") or hashes.get("publication_hash") or hashes.get("authority_hash"))


def _classify_observation(row: dict[str, Any], observation: str) -> dict[str, Any]:
    scenario_id = str(row.get("scenario_id") or "")
    classification = _as_dict(row.get("classification"))
    statuses = {str(value).upper() for value in classification.get("observed_statuses") or []}
    selected_family = str(classification.get("selected_family_id") or "")
    text = _text_sample(row)
    text_upper = text.upper()
    final_ready = bool(_as_dict(row.get("final_card_wait_probe")).get("final_card_ready"))
    lightweight_state = _is_lightweight_state(row)
    has_publication_hash = _has_final_publication_payload(row)

    if observation == "design_guide_section_parser_missed_final_card":
        bucket = "VERIFIER_SECTION_PARSER_GAP"
        fix = "Prefer data-testid design-guide-card/card data attributes over text-section slicing."
        ready = "READY"
    elif observation in {
        "same_beam_state_fingerprint_only_partially_browser_exposed",
        "selected_family_not_exposed_in_browser_state",
    } and lightweight_state:
        bucket = "VERIFIER_READINESS_PRE_PAGE_CAPTURE"
        fix = "Wait for final/full browser state before classifying family/hash exposure."
        ready = "READY"
    elif observation == "browser_state_final_publication_hash_not_available" and lightweight_state:
        bucket = "VERIFIER_READINESS_PRE_PAGE_CAPTURE"
        fix = "Wait for final/full browser state before requiring final publication hash."
        ready = "READY"
    elif observation == "browser_state_final_publication_hash_not_available" and final_ready and not has_publication_hash:
        bucket = "MISSING_READ_ONLY_PUBLICATION_HASH_EXPOSURE"
        fix = "Expose an existing final publication hash or explicitly bounded shell hash on this card path."
        ready = "NEEDS_SLICE"
    elif observation.startswith("expected_") and statuses & {"BLOCKED"}:
        bucket = "SCENARIO_EXPECTATION_OR_PRODUCT_CONTRACT_CHECK"
        fix = "Audit whether the recipe should expect BLOCKED rather than ACTION/PASS, or fix the family if a CTA is required."
        ready = "NEEDS_CONTRACT_DECISION"
    elif observation.startswith("expected_") and ("CHECKING DESIGN GUIDANCE" in text_upper or lightweight_state):
        bucket = "VERIFIER_READINESS_PRE_PAGE_CAPTURE"
        fix = "Wait for final card text/state before comparing expected visual state."
        ready = "READY"
    elif observation.startswith("expected_"):
        bucket = "SCENARIO_EXPECTATION_OR_PRODUCT_CONTRACT_CHECK"
        fix = "Confirm the representative recipe expectation against the current family contract."
        ready = "NEEDS_CONTRACT_DECISION"
    elif observation == "selected_family_not_exposed_in_browser_state" and selected_family:
        bucket = "STALE_OBSERVATION"
        fix = "No fix required; selected family is exposed in classification."
        ready = "READY"
    elif observation == "selected_family_not_exposed_in_browser_state":
        bucket = "MISSING_READ_ONLY_FAMILY_EXPOSURE"
        fix = "Expose existing family/source evidence on this card path, without deriving new product truth."
        ready = "NEEDS_SLICE"
    else:
        bucket = "UNKNOWN_NEEDS_AUDIT"
        fix = "Inspect scenario artifact before changing verifier or product code."
        ready = "BLOCKED"

    return {
        "scenario_id": scenario_id,
        "observation": observation,
        "bucket": bucket,
        "fix": fix,
        "readiness": ready,
        "observed_statuses": sorted(statuses),
        "selected_family_id": selected_family,
        "final_card_ready": final_ready,
        "lightweight_state": lightweight_state,
        "has_publication_hash": has_publication_hash,
    }


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Family Browser Trace Gap Classification",
        "",
        "## Executive Summary",
        "",
        f"Status: `{payload.get('status')}`",
        f"Source snapshot: `{payload.get('source_snapshot')}`",
        f"Trace gaps classified: `{payload.get('gap_count')}`",
        f"Unknown gaps: `{payload.get('unknown_count')}`",
        "",
        "## Bucket Counts",
        "",
    ]
    for bucket, count in sorted(dict(payload.get("bucket_counts") or {}).items()):
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(["", "## Gap Inventory", ""])
    for row in payload.get("classified_gaps") or []:
        lines.append(
            "- `{scenario}` `{bucket}` `{observation}` -> {fix}".format(
                scenario=row.get("scenario_id"),
                bucket=row.get("bucket"),
                observation=row.get("observation"),
                fix=row.get("fix"),
            )
        )
    lines.extend(["", "## Next Fix Order", ""])
    for item in payload.get("next_fix_order") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", help="Path to a family browser/live visual consistency JSON artifact.")
    args = parser.parse_args(argv)

    source = Path(args.snapshot) if args.snapshot else _latest_visual_snapshot()
    if source is None or not source.exists():
        raise SystemExit("No design_guide_family_browser_live_visual_consistency JSON artifact found.")
    source_payload = json.loads(source.read_text(encoding="utf-8"))

    classified: list[dict[str, Any]] = []
    for scenario in source_payload.get("scenarios") or []:
        for observation in _as_dict(scenario.get("classification")).get("non_visual_observations") or []:
            classified.append(_classify_observation(scenario, str(observation)))

    bucket_counts: dict[str, int] = {}
    for row in classified:
        bucket_counts[row["bucket"]] = bucket_counts.get(row["bucket"], 0) + 1

    unknown_count = bucket_counts.get("UNKNOWN_NEEDS_AUDIT", 0)
    status = "PASS" if classified and unknown_count == 0 else ("FAIL" if unknown_count else "PARTIAL")
    next_fix_order = [
        "Fix verifier readiness/pre-page capture first; this is proof-only.",
        "Move section parsing to card data attributes where possible.",
        "Add read-only final publication hash/family exposure for bounded blocker/terminal shells.",
        "Only then audit ACTION-vs-BLOCKED scenario expectation mismatches against family contracts.",
    ]

    stamp = _datetime_stamp()
    payload = {
        "schema": "design_guide_family_browser_trace_gap_classification_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "source_snapshot": str(source),
        "source_status": source_payload.get("status"),
        "source_hard_failures": list(source_payload.get("hard_failures") or []),
        "source_warnings": list(source_payload.get("warnings") or []),
        "gap_count": len(classified),
        "unknown_count": unknown_count,
        "bucket_counts": bucket_counts,
        "classified_gaps": classified,
        "next_fix_order": next_fix_order,
        "product_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "snapshot_hash": _stable_hash(
            {
                "source": str(source),
                "classified": classified,
                "bucket_counts": bucket_counts,
            }
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_family_browser_trace_gap_classification_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_family_browser_trace_gap_classification_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_build_report(payload), encoding="utf-8")
    print("design_guide_family_browser_trace_gap_classification_snapshot " + status)
    print(f"json={json_path}")
    print(f"report={report_path}")
    print("bucket_counts=" + json.dumps(bucket_counts, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
