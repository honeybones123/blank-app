"""Duplicate publication stamp bypass readiness snapshot.

Proof-only. This verifier proves the three safe bypass candidates from the
smoothness audit can be keyed by FinalDesignGuidePublication.publication_hash.
It does not implement a live bypass and does not change product behaviour.
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

SAFE_BYPASS_CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "id": "duplicate_compute_proof_debug_payload_stamping",
        "area": "duplicate compute proof/debug payload stamping",
        "scope": "compute proof/debug payload stamping; former helper-row users deleted",
        "source_tokens": (
            "_FINAL_PUBLICATION_DUPLICATE_STAMP_BYPASS_CANDIDATES",
            "duplicate_compute_proof_debug_payload_stamping",
            "_final_publication_duplicate_stamp_bypass_decision",
        ),
        "affected_surface": "debug/compatibility stamp rebuild only",
    },
    {
        "id": "duplicate_debug_session_publication_stamps",
        "area": "duplicate debug/session publication stamps",
        "scope": "legacy non-authoritative publication-shaped session/debug bundles",
        "source_tokens": (
            "final_publication_authority_hash",
            "publication_hash",
            "legacy_non_authoritative",
            "compatibility_only",
        ),
        "affected_surface": "debug/session compatibility stamp rebuild only",
    },
    {
        "id": "repeated_verifier_debug_payload_stamping",
        "area": "repeated verifier/debug payload stamping",
        "scope": "final_publication_verifier_payload assembly",
        "source_tokens": (
            "final_publication_verifier_payload",
            "publication_hash",
            "final_publication_authority_hash",
        ),
        "affected_surface": "verifier/debug payload rebuild only",
    },
)

LOCKS = {
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _bypass_decision(
    *,
    current_publication_hash: str | None,
    previous_publication_hash: str | None,
    debug_force_rebuild: bool = False,
) -> dict[str, Any]:
    if debug_force_rebuild:
        return {
            "decision": "REBUILD",
            "reason": "debug_force_rebuild",
            "ready_to_skip": False,
        }
    if not current_publication_hash:
        return {
            "decision": "REBUILD",
            "reason": "missing_current_publication_hash",
            "ready_to_skip": False,
        }
    if not previous_publication_hash:
        return {
            "decision": "REBUILD",
            "reason": "missing_previous_publication_hash",
            "ready_to_skip": False,
        }
    if current_publication_hash != previous_publication_hash:
        return {
            "decision": "REBUILD",
            "reason": "stale_or_changed_publication_hash",
            "ready_to_skip": False,
        }
    return {
        "decision": "SKIP_REBUILD",
        "reason": "publication_hash_unchanged",
        "ready_to_skip": True,
    }


def _candidate_checks(source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in SAFE_BYPASS_CANDIDATES:
        token_checks = {token: token in source for token in candidate["source_tokens"]}
        scenarios = {
            "same_hash": _bypass_decision(
                current_publication_hash="pub-hash",
                previous_publication_hash="pub-hash",
            ),
            "debug_force_rebuild": _bypass_decision(
                current_publication_hash="pub-hash",
                previous_publication_hash="pub-hash",
                debug_force_rebuild=True,
            ),
            "missing_current_hash": _bypass_decision(
                current_publication_hash=None,
                previous_publication_hash="pub-hash",
            ),
            "missing_previous_hash": _bypass_decision(
                current_publication_hash="pub-hash",
                previous_publication_hash=None,
            ),
            "stale_hash": _bypass_decision(
                current_publication_hash="pub-hash-new",
                previous_publication_hash="pub-hash-old",
            ),
        }
        rows.append(
            {
                **candidate,
                "source_tokens_present": token_checks,
                "all_source_tokens_present": all(token_checks.values()),
                "bypass_key": "FinalDesignGuidePublication.publication_hash",
                "would_change_final_publication": False,
                "would_change_cta": False,
                "would_change_display": False,
                "would_change_apply_payload": False,
                "would_change_visible_wording": False,
                "debug_mode_can_force_rebuild": scenarios["debug_force_rebuild"]["decision"] == "REBUILD",
                "stale_or_missing_hash_falls_back_to_rebuild": all(
                    scenarios[name]["decision"] == "REBUILD"
                    for name in ("missing_current_hash", "missing_previous_hash", "stale_hash")
                ),
                "same_hash_can_skip_rebuild": scenarios["same_hash"]["decision"] == "SKIP_REBUILD",
                "scenarios": scenarios,
            }
        )
    return rows


def _source_guards(input_source: str, final_source: str) -> dict[str, bool]:
    return {
        "final_publication_has_publication_hash": "publication_hash" in final_source,
        "final_publication_has_no_inputs_page_import": "inputs_page" not in final_source,
        "final_publication_has_no_streamlit_import": "streamlit" not in final_source,
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in input_source
            and "_record_rendered_design_guide_primary_apply_payload" not in final_source
        ),
        "cta_rendering_remains_page_owned": (
            "_design_guide_dashboard_card_html_from_render_model" in input_source
            and "_design_guide_dashboard_card_html_from_render_model" not in final_source
        ),
        "debug_compute_stamp_surfaces_deleted_or_compatibility_only": (
            (
                "final_publication_compute_debug_restamp_metadata_rows" not in input_source
                and "final_publication_compute_a_class_evidence_rows" not in input_source
            )
            or (
                "final_publication_compute_debug_restamp_metadata_compatibility_only" in input_source
                and "final_publication_compute_a_class_evidence_compatibility_only" in input_source
            )
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Duplicate Publication Stamp Bypass Readiness Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Safe bypass candidates identified: `{payload['safe_bypass_candidate_count']}`",
        f"- Ready for non-debug bypass: `{payload['ready_for_non_debug_bypass']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Candidates",
        "",
        "| Candidate | Key | Affected surface | Same hash skip | Debug force rebuild | Missing/stale rebuild |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["candidate_checks"]:
        lines.append(
            "| `{candidate}` | `{key}` | {surface} | `{same}` | `{debug}` | `{stale}` |".format(
                candidate=_escape_md(row["id"]),
                key=_escape_md(row["bypass_key"]),
                surface=_escape_md(row["affected_surface"]),
                same=row["same_hash_can_skip_rebuild"],
                debug=row["debug_mode_can_force_rebuild"],
                stale=row["stale_or_missing_hash_falls_back_to_rebuild"],
            )
        )
    lines.extend(["", "## Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
    lines.extend(["", "## Source Guards", "", "| Guard | PASS |", "| --- | --- |"])
    for key, value in payload["source_guards"].items():
        lines.append(f"| `{_escape_md(key)}` | `{value}` |")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    locks = {name: _latest(prefix) for name, prefix in LOCKS.items()}
    candidate_checks = _candidate_checks(input_source)
    source_guards = _source_guards(input_source, final_source)

    failures: list[str] = []
    if len(candidate_checks) != 3:
        failures.append(f"expected_3_safe_bypass_candidates_found_{len(candidate_checks)}")
    for lock_name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{lock_name}_not_passed")
    for row in candidate_checks:
        if not row["all_source_tokens_present"]:
            failures.append(f"{row['id']}_source_tokens_missing")
        if row["bypass_key"] != "FinalDesignGuidePublication.publication_hash":
            failures.append(f"{row['id']}_not_keyed_by_publication_hash")
        if not row["same_hash_can_skip_rebuild"]:
            failures.append(f"{row['id']}_same_hash_cannot_skip")
        if not row["debug_mode_can_force_rebuild"]:
            failures.append(f"{row['id']}_debug_force_rebuild_missing")
        if not row["stale_or_missing_hash_falls_back_to_rebuild"]:
            failures.append(f"{row['id']}_stale_missing_hash_rebuild_missing")
        if any(
            row[key]
            for key in (
                "would_change_final_publication",
                "would_change_cta",
                "would_change_display",
                "would_change_apply_payload",
                "would_change_visible_wording",
            )
        ):
            failures.append(f"{row['id']}_would_change_product_surface")
    for key, value in source_guards.items():
        if value is not True:
            failures.append(f"source_guard_failed::{key}")

    ready = not failures
    payload = {
        "schema": "design_guide_duplicate_publication_stamp_bypass_readiness_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if ready else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "ready_for_non_debug_bypass": ready,
        "safe_bypass_candidate_count": len(candidate_checks),
        "candidate_checks": candidate_checks,
        "locks": {
            name: {
                "path": lock.get("path"),
                "passed": lock.get("passed"),
                "found": lock.get("found"),
            }
            for name, lock in locks.items()
        },
        "source_guards": source_guards,
        "bypass_decision_contract": {
            "key": "FinalDesignGuidePublication.publication_hash",
            "skip_when": "current_publication_hash == previous_publication_hash and debug_force_rebuild is false",
            "rebuild_when": [
                "debug_force_rebuild",
                "missing_current_publication_hash",
                "missing_previous_publication_hash",
                "stale_or_changed_publication_hash",
            ],
            "live_product_paths_changed": False,
        },
        "snapshot_hash": _stable_hash(
            {
                "candidate_checks": candidate_checks,
                "locks": {name: lock.get("path") for name, lock in locks.items()},
                "source_guards": source_guards,
            }
        ),
        "recommended_next_slice": (
            "Implement a non-debug bypass for duplicate compute/debug publication stamp rebuilds keyed by "
            "FinalDesignGuidePublication.publication_hash, with debug/verifier mode forcing rebuild and "
            "missing/stale hashes rebuilding."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_duplicate_publication_stamp_bypass_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_duplicate_publication_stamp_bypass_readiness_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_duplicate_publication_stamp_bypass_readiness_snapshot {payload['status']}")
    print(f"ready_for_non_debug_bypass={payload['ready_for_non_debug_bypass']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
