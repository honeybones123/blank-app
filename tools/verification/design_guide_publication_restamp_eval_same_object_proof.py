"""Prove whether publication/restamp candidate evals are same-object passive work.

Proof-only. This verifier focuses on the publication/restamp stream from the
candidate-evaluation breakdown. It determines whether the observed repeated
candidate evals are compatibility-only same-object stamps, or whether any still
drive product-visible contract/display state.
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
INPUTS_PAGE = ROOT / "inputs_page.py"


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


def _extract_function(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(marker))
    if next_def < 0:
        next_def = source.find("\nif __name__", start + len(marker))
    return source[start:] if next_def < 0 else source[start:next_def]


def _context_around(source: str, needle: str, *, before: int = 1200, after: int = 3600) -> str:
    index = source.find(needle)
    if index < 0:
        return ""
    return source[max(0, index - before) : min(len(source), index + after)]


def _capture(breakdown_path: Path) -> dict[str, Any]:
    breakdown = json.loads(breakdown_path.read_text(encoding="utf-8"))
    stream = dict((breakdown.get("stream_totals") or {}).get("publication_or_restamp_probe") or {})
    examples = [dict(item) for item in list(stream.get("examples") or []) if isinstance(item, dict)]
    sources = sorted({str(example.get("source") or "") for example in examples if example.get("source")})
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    binding_body = _extract_function(source, "_publish_final_visible_design_guide_contract_binding")
    source_contexts = {name: _context_around(source, name) for name in sources}
    markers = {
        "binding_function_exists": bool(binding_body),
        "source_examples": sources,
        "active_shear_restamp_eval_present": (
            "source=\"final_visible_active_shear_repair_family_restamp\"" in source
            and "_evaluate_auto_design_candidate(" in _context_around(
                source,
                "source=\"final_visible_active_shear_repair_family_restamp\"",
            )
        ),
        "active_shear_preview_helper_imported": (
            "_build_shear_fail_active_repair_preview_evidence" in source
            and "design_brain.families.shear_fail_governs.active_repair_preview" in source
        ),
        "active_shear_preview_helper_called": (
            "_build_shear_fail_active_repair_preview_evidence(" in _context_around(
                source,
                "source=\"final_visible_active_shear_repair_family_restamp\"",
                before=1800,
                after=6200,
            )
        ),
        "active_shear_family_proof_stamped": (
            "active_repair_preview_proof" in _context_around(
                source,
                "source=\"final_visible_active_shear_repair_family_restamp\"",
                before=1800,
                after=6200,
            )
            and "final_binding_active_shear_repair_proof" in _context_around(
                source,
                "source=\"final_visible_active_shear_repair_family_restamp\"",
                before=1800,
                after=6200,
            )
        ),
        "updates_button_contract": '"button_contract": dict(contract)' in binding_body
        or 'out["button_contract"]' in binding_body,
        "updates_display_truth": 'out["display_truth"]' in binding_body,
        "updates_candidate_search_evidence": 'out["candidate_search_evidence"]' in binding_body,
        "updates_action_payload_or_resolved_candidate": (
            'out["action_payload"]' in binding_body or 'out["resolved_candidate"]' in binding_body
        ),
        "compatibility_only_callsite_guarded": "compatibility_only_callsite" in binding_body,
        "restamper_metadata_present": "final_publication_restamper_metadata" in binding_body,
        "final_publication_authority_markers_present": "final_publication" in binding_body,
    }
    return {
        "breakdown_path": str(breakdown_path),
        "breakdown_snapshot_hash": breakdown.get("snapshot_hash"),
        "profile_recipe": (breakdown.get("classification") or {}).get("profile_recipe"),
        "stream": stream,
        "source_context_hashes": {name: _stable_hash(text) for name, text in source_contexts.items()},
        "markers": markers,
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    stream = dict(capture.get("stream") or {})
    markers = dict(capture.get("markers") or {})
    product_driving_markers = [
        "active_shear_restamp_eval_present",
        "updates_button_contract",
        "updates_display_truth",
        "updates_candidate_search_evidence",
        "updates_action_payload_or_resolved_candidate",
    ]
    product_driving = [name for name in product_driving_markers if markers.get(name)]
    family_proof_backed = bool(
        markers.get("active_shear_restamp_eval_present")
        and markers.get("active_shear_preview_helper_imported")
        and markers.get("active_shear_preview_helper_called")
        and markers.get("active_shear_family_proof_stamped")
    )
    same_object_passive = bool(stream) and not product_driving
    if not stream:
        diagnosis = "NO_PUBLICATION_RESTAMP_STREAM_IN_BREAKDOWN"
        next_slice = "Refresh candidate-evaluation stream breakdown with actionable browser profile."
    elif product_driving and family_proof_backed:
        diagnosis = "PUBLICATION_RESTAMP_EVAL_FAMILY_PROOF_BACKED_EVALUATOR_STILL_LIVE"
        next_slice = (
            "Do not bypass this eval stream yet. It no longer owns active-shear proof normalisation in the page, "
            "but the evaluator still runs as a live safety/preview check. Profile or prove evaluator reuse before "
            "adding any cache."
        )
    elif product_driving:
        diagnosis = "PUBLICATION_RESTAMP_EVAL_STILL_PRODUCT_DRIVING"
        next_slice = (
            "Do not bypass this eval stream. Move/prove the active-shear restamp candidate check "
            "inside the locked family/runtime or controller authority before narrowing."
        )
    elif same_object_passive:
        diagnosis = "PUBLICATION_RESTAMP_EVAL_SAME_OBJECT_PASSIVE"
        next_slice = "Eligible for guarded compatibility-only bypass proof."
    else:
        diagnosis = "PUBLICATION_RESTAMP_EVAL_NEEDS_MANUAL_REVIEW"
        next_slice = "Inspect source examples and browser trace before bypass."
    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "same_object_passive": same_object_passive,
        "family_proof_backed": family_proof_backed,
        "proof_owner": "SHEAR_FAIL_GOVERNS" if family_proof_backed else None,
        "product_driving_markers": product_driving,
        "can_bypass_now": False,
        "fingerprint_rows": int(stream.get("fingerprint_rows") or 0),
        "observed_repeated_count": int(stream.get("observed_repeated_count") or 0),
        "observed_cache_hits": int(stream.get("observed_cache_hits") or 0),
        "observed_total_ms": float(stream.get("observed_total_ms") or 0.0),
        "source_examples": list(markers.get("source_examples") or []),
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Publication/Restamp Eval Same-Object Proof",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Same-object passive: `{cls.get('same_object_passive')}`",
        f"- Family proof backed: `{cls.get('family_proof_backed')}`",
        f"- Proof owner: `{cls.get('proof_owner')}`",
        f"- Can bypass now: `{cls.get('can_bypass_now')}`",
        f"- Product-driving markers: `{cls.get('product_driving_markers')}`",
        f"- Source examples: `{cls.get('source_examples')}`",
        f"- Repeated count: `{cls.get('observed_repeated_count')}`",
        f"- Cache hits: `{cls.get('observed_cache_hits')}`",
        f"- Observed total ms: `{cls.get('observed_total_ms')}`",
        "",
        "## Markers",
        "",
        "```json",
        json.dumps(payload.get("markers") or {}, indent=2, sort_keys=True),
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
    json_path = ARTIFACT_DIR / f"design_guide_publication_restamp_eval_same_object_proof_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_publication_restamp_eval_same_object_proof_{stamp}.md"
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
        "schema": "design_guide_publication_restamp_eval_same_object_proof.v1",
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
    print(f"design_guide_publication_restamp_eval_same_object_proof {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(json.dumps(classification, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
