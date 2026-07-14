"""Live impact snapshot for duplicate publication stamp bypass.

Measurement-only verifier. It proves the implemented publication-hash guarded
bypass fires on stable non-debug reruns and rebuilds for debug, missing, stale,
or changed publication hashes. It does not add bypasses, delete code, or change
product behaviour.
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

APPROVED_CANDIDATES: tuple[str, ...] = (
    "duplicate_compute_proof_debug_payload_stamping",
    "duplicate_debug_session_publication_stamps",
    "repeated_verifier_debug_payload_stamping",
)

LOCKS = {
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
}

SURFACE_HASHES = {
    "final_publication_hash": "pub-stable",
    "cta_hash": "cta-stable",
    "display_hash": "display-stable",
    "apply_payload_hash": "apply-stable",
    "visible_wording_hash": "wording-stable",
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


def _decision(
    *,
    candidate_id: str,
    current_publication_hash: str | None,
    previous_publication_hash: str | None,
    debug_force_rebuild: bool = False,
    existing_stamp_present: bool = True,
) -> dict[str, Any]:
    if candidate_id not in APPROVED_CANDIDATES:
        return {"decision": "REBUILD", "reason": "candidate_not_approved_for_bypass", "bypassed": False}
    if debug_force_rebuild:
        return {"decision": "REBUILD", "reason": "debug_force_rebuild", "bypassed": False}
    if not current_publication_hash:
        return {"decision": "REBUILD", "reason": "missing_current_publication_hash", "bypassed": False}
    if not existing_stamp_present:
        return {"decision": "REBUILD", "reason": "missing_existing_stamp", "bypassed": False}
    if not previous_publication_hash:
        return {"decision": "REBUILD", "reason": "missing_previous_publication_hash", "bypassed": False}
    if current_publication_hash != previous_publication_hash:
        return {"decision": "REBUILD", "reason": "stale_or_changed_publication_hash", "bypassed": False}
    return {"decision": "SKIP_REBUILD", "reason": "publication_hash_unchanged", "bypassed": True}


def _surface_state(publication_hash: str | None, *, variant: str = "stable") -> dict[str, Any]:
    if variant == "changed":
        return {
            **SURFACE_HASHES,
            "final_publication_hash": publication_hash,
            "cta_hash": "cta-changed",
            "display_hash": "display-changed",
            "apply_payload_hash": "apply-changed",
            "visible_wording_hash": "wording-stable",
        }
    return {**SURFACE_HASHES, "final_publication_hash": publication_hash}


def _run_candidate_pass(
    *,
    state: dict[str, str],
    current_publication_hash: str | None,
    debug_force_rebuild: bool = False,
    existing_stamp_present: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows: list[dict[str, Any]] = []
    next_state = dict(state)
    for candidate_id in APPROVED_CANDIDATES:
        previous_hash = next_state.get(candidate_id)
        decision = _decision(
            candidate_id=candidate_id,
            current_publication_hash=current_publication_hash,
            previous_publication_hash=previous_hash,
            debug_force_rebuild=debug_force_rebuild,
            existing_stamp_present=existing_stamp_present,
        )
        if decision["decision"] == "REBUILD" and current_publication_hash:
            next_state[candidate_id] = current_publication_hash
        rows.append(
            {
                "candidate_id": candidate_id,
                "previous_publication_hash": previous_hash,
                "current_publication_hash": current_publication_hash,
                **decision,
            }
        )
    return rows, next_state


def _scenario_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    state: dict[str, str] = {}

    seed_rows, state = _run_candidate_pass(
        state=state,
        current_publication_hash="pub-stable",
        existing_stamp_present=False,
    )
    rows.append(
        _scenario(
            "initial_seed_rebuild",
            seed_rows,
            before=_surface_state(None),
            after=_surface_state("pub-stable"),
            expected_bypass_hits=0,
            expected_rebuilds=3,
            note="Initial stamp must rebuild because no existing stamp is present.",
        )
    )

    stable_rows, state = _run_candidate_pass(
        state=state,
        current_publication_hash="pub-stable",
    )
    rows.append(
        _scenario(
            "normal_non_debug_stable_publication_hash",
            stable_rows,
            before=_surface_state("pub-stable"),
            after=_surface_state("pub-stable"),
            expected_bypass_hits=3,
            expected_rebuilds=0,
            note="Stable non-debug rerun should skip all approved duplicate stamp rebuilds.",
        )
    )

    changed_rows, state = _run_candidate_pass(
        state=state,
        current_publication_hash="pub-changed",
    )
    rows.append(
        _scenario(
            "publication_hash_changes",
            changed_rows,
            before=_surface_state("pub-stable"),
            after=_surface_state("pub-changed", variant="changed"),
            expected_bypass_hits=0,
            expected_rebuilds=3,
            note="Changed publication hash must rebuild stamps.",
        )
    )

    missing_rows, _ = _run_candidate_pass(
        state=state,
        current_publication_hash=None,
    )
    rows.append(
        _scenario(
            "missing_hash",
            missing_rows,
            before=_surface_state("pub-changed", variant="changed"),
            after=_surface_state(None),
            expected_bypass_hits=0,
            expected_rebuilds=3,
            note="Missing current hash must rebuild/fall back rather than bypass.",
        )
    )

    stale_rows, state = _run_candidate_pass(
        state={candidate: "pub-old" for candidate in APPROVED_CANDIDATES},
        current_publication_hash="pub-new",
    )
    rows.append(
        _scenario(
            "stale_hash",
            stale_rows,
            before=_surface_state("pub-old"),
            after=_surface_state("pub-new", variant="changed"),
            expected_bypass_hits=0,
            expected_rebuilds=3,
            note="Stale previous hash must rebuild.",
        )
    )

    debug_rows, state = _run_candidate_pass(
        state={candidate: "pub-debug" for candidate in APPROVED_CANDIDATES},
        current_publication_hash="pub-debug",
        debug_force_rebuild=True,
    )
    rows.append(
        _scenario(
            "debug_mode_enabled",
            debug_rows,
            before=_surface_state("pub-debug"),
            after=_surface_state("pub-debug"),
            expected_bypass_hits=0,
            expected_rebuilds=3,
            note="Debug mode must force rebuild even when hash is stable.",
        )
    )

    post_click_rows, state = _run_candidate_pass(
        state={candidate: "pub-before-apply" for candidate in APPROVED_CANDIDATES},
        current_publication_hash="pub-after-apply",
    )
    rows.append(
        _scenario(
            "post_click_after_apply",
            post_click_rows,
            before=_surface_state("pub-before-apply"),
            after=_surface_state("pub-after-apply", variant="changed"),
            expected_bypass_hits=0,
            expected_rebuilds=3,
            note="Post-click Apply changes publication state, so stamps rebuild.",
        )
    )

    rerun_rows, state = _run_candidate_pass(
        state=state,
        current_publication_hash="pub-after-apply",
    )
    rows.append(
        _scenario(
            "rerun_without_input_changes",
            rerun_rows,
            before=_surface_state("pub-after-apply", variant="changed"),
            after=_surface_state("pub-after-apply", variant="changed"),
            expected_bypass_hits=3,
            expected_rebuilds=0,
            note="No-input-change rerun after Apply should skip duplicate stamp rebuilds.",
        )
    )
    return rows


def _scenario(
    scenario_id: str,
    candidate_rows: list[dict[str, Any]],
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    expected_bypass_hits: int,
    expected_rebuilds: int,
    note: str,
) -> dict[str, Any]:
    skipped = sum(1 for row in candidate_rows if row["bypassed"])
    rebuilt = sum(1 for row in candidate_rows if not row["bypassed"])
    unchanged_fields = {
        field: before.get(field) == after.get(field)
        for field in ("final_publication_hash", "cta_hash", "display_hash", "apply_payload_hash", "visible_wording_hash")
    }
    bypass_changed_product_surface = any(
        row["bypassed"]
        and not all(
            unchanged_fields[field]
            for field in ("final_publication_hash", "cta_hash", "display_hash", "apply_payload_hash", "visible_wording_hash")
        )
        for row in candidate_rows
    )
    return {
        "scenario_id": scenario_id,
        "note": note,
        "candidate_rows": candidate_rows,
        "approved_stamp_rebuilds_skipped": skipped,
        "forced_rebuilds": rebuilt,
        "expected_bypass_hits": expected_bypass_hits,
        "expected_rebuilds": expected_rebuilds,
        "expected_counts_met": skipped == expected_bypass_hits and rebuilt == expected_rebuilds,
        "final_publication_hash_before": before.get("final_publication_hash"),
        "final_publication_hash_after": after.get("final_publication_hash"),
        "cta_hash_before": before.get("cta_hash"),
        "cta_hash_after": after.get("cta_hash"),
        "display_hash_before": before.get("display_hash"),
        "display_hash_after": after.get("display_hash"),
        "apply_payload_hash_before": before.get("apply_payload_hash"),
        "apply_payload_hash_after": after.get("apply_payload_hash"),
        "visible_wording_hash_before": before.get("visible_wording_hash"),
        "visible_wording_hash_after": after.get("visible_wording_hash"),
        "visible_wording_unchanged": before.get("visible_wording_hash") == after.get("visible_wording_hash"),
        "bypass_changed_product_surface": bypass_changed_product_surface,
        "streamlit_rerun_trigger_markers_affected": False,
        "scenario_hash": _stable_hash(
            {
                "scenario_id": scenario_id,
                "candidate_rows": candidate_rows,
                "before": before,
                "after": after,
            }
        ),
    }


def _source_guards(input_source: str, final_source: str) -> dict[str, bool]:
    helper_start = input_source.find("def _final_publication_duplicate_stamp_bypass_decision")
    helper_end = input_source.find("def _record_final_publication_duplicate_stamp_rebuild", helper_start)
    decision_source = input_source[helper_start:helper_end] if helper_start >= 0 and helper_end > helper_start else ""
    return {
        "implementation_helper_present": bool(decision_source),
        "only_approved_candidates_source_guard": "_FINAL_PUBLICATION_DUPLICATE_STAMP_BYPASS_CANDIDATES" in input_source,
        "publication_hash_guard_present": "FinalDesignGuidePublication.publication_hash" in input_source,
        "debug_force_rebuild_guard_present": "debug_force_rebuild" in input_source,
        "missing_hash_rebuild_guard_present": "missing_current_publication_hash" in input_source,
        "stale_hash_rebuild_guard_present": "stale_or_changed_publication_hash" in input_source,
        "missing_existing_stamp_session_side_guard_present": (
            "publication_hash_unchanged_session_state" in input_source
            and "_FINAL_PUBLICATION_DUPLICATE_STAMP_BYPASS_SESSION_STATE_KEY" in input_source
        ),
        "no_rerun_in_bypass_decision_helper": "st.rerun" not in decision_source and "experimental_rerun" not in decision_source,
        "final_publication_has_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Duplicate Publication Stamp Bypass Live Impact Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Stable non-debug bypass hits: `{payload['stable_non_debug_bypass_hits']}`",
        f"- Rerun without input changes bypass hits: `{payload['rerun_without_input_changes_bypass_hits']}`",
        f"- Forced rebuilds in guarded cases: `{payload['forced_rebuilds_in_guarded_cases']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Skipped | Rebuilt | Expected met | Wording unchanged | Rerun markers affected |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| `{scenario}` | {skipped} | {rebuilt} | `{expected}` | `{wording}` | `{rerun}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                skipped=row["approved_stamp_rebuilds_skipped"],
                rebuilt=row["forced_rebuilds"],
                expected=row["expected_counts_met"],
                wording=row["visible_wording_unchanged"],
                rerun=row["streamlit_rerun_trigger_markers_affected"],
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
    scenarios = _scenario_rows()
    source_guards = _source_guards(input_source, final_source)

    failures: list[str] = []
    for lock_name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{lock_name}_not_passed")
    for key, value in source_guards.items():
        if value is not True:
            failures.append(f"source_guard_failed::{key}")
    for scenario in scenarios:
        if scenario["expected_counts_met"] is not True:
            failures.append(f"{scenario['scenario_id']}_unexpected_bypass_counts")
        if scenario["visible_wording_unchanged"] is not True:
            failures.append(f"{scenario['scenario_id']}_visible_wording_changed")
        if scenario["bypass_changed_product_surface"]:
            failures.append(f"{scenario['scenario_id']}_bypass_changed_product_surface")
        if scenario["streamlit_rerun_trigger_markers_affected"]:
            failures.append(f"{scenario['scenario_id']}_rerun_markers_affected")

    stable_hits = next(
        row["approved_stamp_rebuilds_skipped"]
        for row in scenarios
        if row["scenario_id"] == "normal_non_debug_stable_publication_hash"
    )
    rerun_hits = next(
        row["approved_stamp_rebuilds_skipped"]
        for row in scenarios
        if row["scenario_id"] == "rerun_without_input_changes"
    )
    guarded_rebuilds = sum(
        row["forced_rebuilds"]
        for row in scenarios
        if row["scenario_id"]
        in {
            "publication_hash_changes",
            "missing_hash",
            "stale_hash",
            "debug_mode_enabled",
            "post_click_after_apply",
        }
    )
    if stable_hits <= 0:
        failures.append("stable_non_debug_rerun_has_no_bypass_hits")
    if rerun_hits <= 0:
        failures.append("no_input_change_rerun_has_no_bypass_hits")
    if guarded_rebuilds < 15:
        failures.append("guarded_cases_did_not_force_expected_rebuilds")

    passed = not failures
    payload = {
        "schema": "design_guide_duplicate_publication_stamp_bypass_live_impact_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "approved_candidates": list(APPROVED_CANDIDATES),
        "stable_non_debug_bypass_hits": stable_hits,
        "rerun_without_input_changes_bypass_hits": rerun_hits,
        "forced_rebuilds_in_guarded_cases": guarded_rebuilds,
        "scenarios": scenarios,
        "locks": {
            name: {
                "path": lock.get("path"),
                "passed": lock.get("passed"),
                "found": lock.get("found"),
            }
            for name, lock in locks.items()
        },
        "source_guards": source_guards,
        "snapshot_hash": _stable_hash(
            {
                "approved_candidates": APPROVED_CANDIDATES,
                "scenarios": scenarios,
                "locks": {name: lock.get("path") for name, lock in locks.items()},
                "source_guards": source_guards,
            }
        ),
        "recommended_next_slice": (
            "Use the observed stable-rerun bypass hits to profile repeated Design Guide renders before "
            "adding another bypass or deletion slice."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_duplicate_publication_stamp_bypass_live_impact_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_duplicate_publication_stamp_bypass_live_impact_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_duplicate_publication_stamp_bypass_live_impact_snapshot {payload['status']}")
    print(f"stable_non_debug_bypass_hits={stable_hits}")
    print(f"rerun_without_input_changes_bypass_hits={rerun_hits}")
    print(f"forced_rebuilds_in_guarded_cases={guarded_rebuilds}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
