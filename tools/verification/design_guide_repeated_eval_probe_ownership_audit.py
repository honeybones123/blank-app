"""Audit ownership of repeated Design Guide candidate-evaluation probe streams.

Proof-only. Consumes the latest candidate-evaluation stream breakdown and
classifies repeated eval sources by likely ownership before any further bypass,
memoization, or deletion is considered.
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


def _latest_breakdown_path() -> Path:
    paths = sorted(
        ARTIFACT_DIR.glob("design_guide_candidate_evaluation_stream_breakdown_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    for path in reversed(paths):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("status") == "PASS":
            return path
    raise FileNotFoundError("No PASS design_guide_candidate_evaluation_stream_breakdown artifact found")


def _ownership_for_stream(stream_name: str, examples: list[dict[str, Any]]) -> dict[str, Any]:
    joined = " ".join(
        " ".join(str(example.get(key) or "") for key in ("source", "label", "action_type"))
        for example in examples
    ).lower()
    if stream_name == "publication_or_restamp_probe":
        classification = "A. compatibility/proof-only candidate"
        reason = "Restamp/final-visible publication probes should already be downstream of FinalDesignGuidePublication authority, but need row-level proof before bypass."
        next_proof = "publication/restamp repeated-eval same-object proof"
        can_bypass_now = False
    elif stream_name == "post_click_cleanup_probe":
        classification = "C. still live product-driving until proven otherwise"
        reason = "Post-click cleanup can affect accepted/blocked final state and must not be suppressed without post-click state parity proof."
        next_proof = "post-click cleanup repeated-eval same-object proof"
        can_bypass_now = False
    elif stream_name == "cta_payload_guard_probe":
        classification = "D. safety guard / keep"
        reason = "CTA/apply payload guard protects stale or unsafe Apply state."
        next_proof = "CTA guard bypass proof only if hash-stamped same-object state is proven"
        can_bypass_now = False
    elif stream_name == "family_preview_or_runtime_required":
        classification = "C. still live product-driving until proven otherwise"
        reason = "Family preview/runtime-labelled evals may still be required for engineering recommendation proof."
        next_proof = "family runtime candidate-eval ownership proof"
        can_bypass_now = False
    elif stream_name == "other_labelled_candidate_eval":
        classification = "E. unknown / needs source proof"
        reason = "Labelled eval stream is not specific enough to classify from browser labels alone."
        next_proof = "source-specific repeated-eval ownership audit"
        can_bypass_now = False
    else:
        classification = "E. unknown / needs source proof"
        reason = "Unrecognized stream bucket."
        next_proof = "source-specific repeated-eval ownership audit"
        can_bypass_now = False
    if "post_click" in joined and classification.startswith("A."):
        classification = "C. still live product-driving until proven otherwise"
        reason = "This stream includes post-click labels, so compatibility-only treatment needs stricter proof."
        next_proof = "post-click same-object proof before narrowing"
        can_bypass_now = False
    return {
        "stream_name": stream_name,
        "classification": classification,
        "reason": reason,
        "next_proof": next_proof,
        "can_bypass_now": can_bypass_now,
    }


def _capture(breakdown_path: Path) -> dict[str, Any]:
    breakdown = json.loads(breakdown_path.read_text(encoding="utf-8"))
    stream_totals = dict(breakdown.get("stream_totals") or {})
    rows = []
    for stream_name, stream in sorted(stream_totals.items()):
        examples = [dict(item) for item in list(dict(stream).get("examples") or []) if isinstance(item, dict)]
        ownership = _ownership_for_stream(stream_name, examples)
        rows.append(
            {
                **ownership,
                "fingerprint_rows": int(dict(stream).get("fingerprint_rows") or 0),
                "observed_repeated_count": int(dict(stream).get("observed_repeated_count") or 0),
                "observed_cache_hits": int(dict(stream).get("observed_cache_hits") or 0),
                "observed_total_ms": float(dict(stream).get("observed_total_ms") or 0.0),
                "examples": examples,
            }
        )
    return {
        "breakdown_path": str(breakdown_path),
        "breakdown_snapshot_hash": breakdown.get("snapshot_hash"),
        "profile_recipe": (breakdown.get("classification") or {}).get("profile_recipe"),
        "breakdown_classification": breakdown.get("classification"),
        "rows": rows,
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    rows = list(capture.get("rows") or [])
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("classification") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    bypassable_now = [row.get("stream_name") for row in rows if row.get("can_bypass_now")]
    live_product_driving = [
        row.get("stream_name")
        for row in rows
        if str(row.get("classification") or "").startswith("C.")
    ]
    compatibility_candidates = [
        row.get("stream_name")
        for row in rows
        if str(row.get("classification") or "").startswith("A.")
    ]
    if bypassable_now:
        diagnosis = "UNEXPECTED_BYPASSABLE_STREAM"
        status = "FAIL"
        next_slice = "Do not continue; audit classification because proof-only audit should not approve bypass directly."
    elif compatibility_candidates or live_product_driving:
        diagnosis = "OWNERSHIP_CLASSIFIED_NO_BYPASS_READY"
        status = "PASS"
        next_slice = "Build focused same-object proof for publication/restamp and post-click cleanup eval streams."
    else:
        diagnosis = "OWNERSHIP_UNCLEAR"
        status = "PASS"
        next_slice = "Add source-specific labels before any bypass work."
    return {
        "status": status,
        "diagnosis": diagnosis,
        "classification_counts": counts,
        "compatibility_candidates": compatibility_candidates,
        "live_product_driving_streams": live_product_driving,
        "bypassable_now": bypassable_now,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Repeated Eval Probe Ownership Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Compatibility candidates: `{cls.get('compatibility_candidates')}`",
        f"- Live product-driving streams: `{cls.get('live_product_driving_streams')}`",
        f"- Bypassable now: `{cls.get('bypassable_now')}`",
        "",
        "## Rows",
        "",
        "```json",
        json.dumps(payload.get("rows") or [], indent=2, sort_keys=True, default=str)[:12000],
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
    json_path = ARTIFACT_DIR / f"design_guide_repeated_eval_probe_ownership_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_repeated_eval_probe_ownership_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--breakdown", default="")
    args = parser.parse_args(argv)
    breakdown_path = Path(args.breakdown) if args.breakdown else _latest_breakdown_path()
    created_at = _stamp()
    capture = _capture(breakdown_path)
    classification = _classify(capture)
    payload = {
        "schema": "design_guide_repeated_eval_probe_ownership_audit.v1",
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
    print(f"design_guide_repeated_eval_probe_ownership_audit {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(json.dumps(classification, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
