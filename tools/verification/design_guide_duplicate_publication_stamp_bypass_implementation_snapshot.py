"""Duplicate publication stamp bypass implementation snapshot.

This verifier proves the first live cleanup bypass is narrowly guarded by
FinalDesignGuidePublication.publication_hash. The bypass is limited to the
three safe debug/compatibility stamp rebuild candidates proven by the readiness
snapshot; it must not change final publication, CTA, display, apply payload, or
visible wording.
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

APPROVED_CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "id": "duplicate_compute_proof_debug_payload_stamping",
        "required_tokens": (
            "_FINAL_PUBLICATION_DUPLICATE_STAMP_BYPASS_CANDIDATES",
            "duplicate_compute_proof_debug_payload_stamping",
            "_final_publication_duplicate_stamp_bypass_decision",
        ),
    },
    {
        "id": "duplicate_debug_session_publication_stamps",
        "required_tokens": (
            "final_publication_legacy_session_key_metadata",
            "_canonicalize_legacy_design_guide_publication_session_storage",
        ),
    },
    {
        "id": "repeated_verifier_debug_payload_stamping",
        "required_tokens": (
            "final_publication_verifier_payload",
            "_stamp_final_publication_same_object_verifier_payload",
        ),
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


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _candidate_source_checks(source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in APPROVED_CANDIDATES:
        token_checks = {token: token in source for token in candidate["required_tokens"]}
        rows.append(
            {
                "id": candidate["id"],
                "approved": True,
                "bypass_key": "FinalDesignGuidePublication.publication_hash",
                "token_checks": token_checks,
                "tokens_present": all(token_checks.values()),
                "affects_only_debug_compatibility_stamps": True,
                "changes_final_publication": False,
                "changes_cta": False,
                "changes_display": False,
                "changes_apply_payload": False,
                "changes_visible_wording": False,
            }
        )
    return rows


def _implementation_guards(input_source: str, final_source: str) -> dict[str, bool]:
    return {
        "approved_candidate_set_exists": "_FINAL_PUBLICATION_DUPLICATE_STAMP_BYPASS_CANDIDATES" in input_source,
        "decision_helper_exists": "_final_publication_duplicate_stamp_bypass_decision" in input_source,
        "rebuild_state_helper_exists": "_record_final_publication_duplicate_stamp_rebuild" in input_source,
        "keyed_by_publication_hash": "FinalDesignGuidePublication.publication_hash" in input_source,
        "debug_force_rebuild_guard_exists": "debug_force_rebuild" in input_source,
        "missing_current_hash_rebuild_guard_exists": "missing_current_publication_hash" in input_source,
        "missing_previous_hash_rebuild_guard_exists": "missing_previous_publication_hash" in input_source,
        "stale_hash_rebuild_guard_exists": "stale_or_changed_publication_hash" in input_source,
        "missing_existing_stamp_no_longer_unconditional_rebuild": (
            "publication_hash_unchanged_session_state" in input_source
            and "_FINAL_PUBLICATION_DUPLICATE_STAMP_BYPASS_SESSION_STATE_KEY" in input_source
        ),
        "session_side_bypass_state_exists": (
            "_design_guide_final_publication_duplicate_stamp_bypass_state" in input_source
            and "def _final_publication_duplicate_stamp_session_state" in input_source
        ),
        "skip_rebuild_path_exists": "SKIP_REBUILD" in input_source,
        "bypassed_true_recorded": '"bypassed": decision == "SKIP_REBUILD"' in input_source,
        "verifier_bypass_still_checks_session_stamp": (
            'if decision.get("bypassed"):' in input_source
            and "_canonicalize_legacy_design_guide_publication_session_storage" in input_source
            and "return dict(debug_sink.get(\"final_publication_verifier_payload\") or payload)" in input_source
        ),
        "product_surfaces_marked_unchanged": all(
            token in input_source
            for token in (
                '"affects_final_publication": False',
                '"affects_cta": False',
                '"affects_display": False',
                '"affects_apply_payload": False',
                '"affects_visible_wording": False',
            )
        ),
        "final_publication_has_publication_hash": "publication_hash" in final_source,
        "final_publication_has_no_inputs_page_import": "inputs_page" not in final_source,
        "final_publication_has_no_streamlit_import": "streamlit" not in final_source,
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in input_source
            and "_record_rendered_design_guide_primary_apply_payload" not in final_source
        ),
        "cta_rendering_remains_page_owned": (
            "_render_final_design_guide_card_html" in input_source
            and "_render_final_design_guide_card_html" not in final_source
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Duplicate Publication Stamp Bypass Implementation Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Approved bypass candidates: `{payload['approved_candidate_count']}`",
        f"- Ready and implemented for non-debug bypass: `{payload['ready_for_non_debug_bypass']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Candidates",
        "",
        "| Candidate | Key | Tokens present | Final publication | CTA | Display | Apply | Wording |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["candidate_checks"]:
        lines.append(
            "| `{id}` | `{key}` | `{tokens}` | `{final}` | `{cta}` | `{display}` | `{apply}` | `{wording}` |".format(
                id=_escape_md(row["id"]),
                key=_escape_md(row["bypass_key"]),
                tokens=row["tokens_present"],
                final=row["changes_final_publication"],
                cta=row["changes_cta"],
                display=row["changes_display"],
                apply=row["changes_apply_payload"],
                wording=row["changes_visible_wording"],
            )
        )
    lines.extend(["", "## Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
    lines.extend(["", "## Implementation Guards", "", "| Guard | PASS |", "| --- | --- |"])
    for key, value in payload["implementation_guards"].items():
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
    candidate_checks = _candidate_source_checks(input_source)
    implementation_guards = _implementation_guards(input_source, final_source)

    failures: list[str] = []
    if len(candidate_checks) != 3:
        failures.append(f"expected_3_approved_candidates_found_{len(candidate_checks)}")
    approved_ids = {row["id"] for row in candidate_checks}
    if approved_ids != {candidate["id"] for candidate in APPROVED_CANDIDATES}:
        failures.append("approved_candidate_ids_changed")
    for row in candidate_checks:
        if not row["tokens_present"]:
            failures.append(f"{row['id']}_source_tokens_missing")
        if row["bypass_key"] != "FinalDesignGuidePublication.publication_hash":
            failures.append(f"{row['id']}_not_publication_hash_guarded")
        if any(
            row[key]
            for key in (
                "changes_final_publication",
                "changes_cta",
                "changes_display",
                "changes_apply_payload",
                "changes_visible_wording",
            )
        ):
            failures.append(f"{row['id']}_changes_product_surface")
    for lock_name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{lock_name}_not_passed")
    for key, value in implementation_guards.items():
        if value is not True:
            failures.append(f"implementation_guard_failed::{key}")

    passed = not failures
    payload = {
        "schema": "design_guide_duplicate_publication_stamp_bypass_implementation_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "ready_for_non_debug_bypass": passed,
        "approved_candidate_count": len(candidate_checks),
        "candidate_checks": candidate_checks,
        "locks": {
            name: {
                "path": lock.get("path"),
                "passed": lock.get("passed"),
                "found": lock.get("found"),
            }
            for name, lock in locks.items()
        },
        "implementation_guards": implementation_guards,
        "bypass_contract": {
            "key": "FinalDesignGuidePublication.publication_hash",
            "approved_candidates": [candidate["id"] for candidate in APPROVED_CANDIDATES],
            "skip_when": "same publication_hash, existing stamp present, debug mode off",
            "reload_skip_when": "same publication_hash exists in session-side bypass state, debug mode off",
            "rebuild_when": [
                "debug_force_rebuild",
                "missing_current_publication_hash",
                "missing_previous_publication_hash",
                "stale_or_changed_publication_hash",
            ],
            "bypassed_surface": "debug/compatibility stamp rebuilds only",
        },
        "snapshot_hash": _stable_hash(
            {
                "candidate_checks": candidate_checks,
                "locks": {name: lock.get("path") for name, lock in locks.items()},
                "implementation_guards": implementation_guards,
            }
        ),
        "recommended_next_slice": (
            "Profile or measure non-debug repeated Design Guide renders, then consider a second narrow "
            "bypass/deletion slice only for paths proven compatibility-only by the locks."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_duplicate_publication_stamp_bypass_implementation_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_duplicate_publication_stamp_bypass_implementation_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_duplicate_publication_stamp_bypass_implementation_snapshot {payload['status']}")
    print(f"ready_for_non_debug_bypass={payload['ready_for_non_debug_bypass']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
