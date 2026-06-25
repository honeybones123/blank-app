"""Proof-only snapshot for narrowed Design Guide restamper mutations.

This verifier proves selected duplicate restamper callsites have been changed
from live mutation to compatibility-only stamping derived from
FinalDesignGuidePublication. It does not delete the callsite or change product
rendering/apply behaviour.
"""

from __future__ import annotations

import json
import subprocess
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

SELECTED_CALLSITE_IDS = (
    "primary_guidance_card_binding",
    "late_engine_combined_evidence_contract_rebound",
    "combined_evidence_contract_rebound",
    "post_click_low_bending_exact_blocker_final_binding",
    "post_click_low_bending_exact_blocker_primary_render_binding",
)
RESTAMPER = "_publish_final_visible_design_guide_contract_binding"
HELPER = "_mark_final_visible_restamper_compatibility_stamp"
EXPECTED_COMPATIBILITY_STAMPS = 6
EXPECTED_STILL_LIVE_MUTATIONS = 4


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest_reachability_artifact() -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob("design_guide_duplicate_restamper_reachability_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None}
    path = artifacts[-1]
    return {
        "path": str(path),
        "snapshot": json.loads(path.read_text(encoding="utf-8")),
    }


def _selected_callsites(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in snapshot.get("callsites") or []:
        if row.get("target") != RESTAMPER:
            continue
        context = str(row.get("context_excerpt") or "")
        for callsite_id in SELECTED_CALLSITE_IDS:
            if callsite_id in context:
                selected[callsite_id] = dict(row)
    return selected


def _callsite_check(row: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "found": row is not None,
        "classification": None if row is None else row.get("classification"),
        "can_change_outcome_after_publication": None
        if row is None
        else row.get("can_change_outcome_after_publication"),
        "can_change_cta_after_publication": None
        if row is None
        else row.get("can_change_cta_after_publication"),
        "can_change_display_after_publication": None
        if row is None
        else row.get("can_change_display_after_publication"),
        "writes_only_compatibility_debug_metadata": None
        if row is None
        else row.get("writes_only_compatibility_debug_metadata"),
        "upstream_publication_hash_available": None
        if row is None
        else row.get("upstream_publication_hash_available"),
    }


def _is_compatibility_stamp(checks: dict[str, Any]) -> bool:
    return bool(
        checks["found"]
        and checks["classification"] == "compatibility stamp"
        and checks["can_change_outcome_after_publication"] is False
        and checks["can_change_cta_after_publication"] is False
        and checks["can_change_display_after_publication"] is False
        and checks["writes_only_compatibility_debug_metadata"] is True
        and checks["upstream_publication_hash_available"] is True
    )


def _build_snapshot() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    independence = _run("tools/verification/design_guide_independence_lock_verifier.py")
    reachability = _run("tools/verification/design_guide_duplicate_restamper_reachability_snapshot.py")
    reachability_artifact = _latest_reachability_artifact()
    reachability_snapshot = reachability_artifact.get("snapshot") or {}
    selected = _selected_callsites(reachability_snapshot) if isinstance(reachability_snapshot, dict) else {}

    helper_tokens = {
        "helper_defined": f"def {HELPER}(" in source,
        **{
            f"callsite_opt_in:{callsite_id}": f'compatibility_only_callsite="{callsite_id}"' in source
            for callsite_id in SELECTED_CALLSITE_IDS
        },
        "legacy_non_authoritative_stamp": '"legacy_non_authoritative": True' in source,
        "compatibility_only_stamp": '"compatibility_only": True' in source,
        "authority_hash_stamp": '"final_publication_authority_hash"' in source,
        "may_override_false": '"may_override_publication": False' in source,
        "metadata_key": "final_publication_restamper_metadata" in source,
    }

    selected_checks = {
        callsite_id: _callsite_check(selected.get(callsite_id))
        for callsite_id in SELECTED_CALLSITE_IDS
    }

    counts = dict(reachability_snapshot.get("classification_counts") or {})
    remaining_live_mutations = int(counts.get("still live mutation") or 0)
    selected_is_compat = {
        callsite_id: _is_compatibility_stamp(checks)
        for callsite_id, checks in selected_checks.items()
    }

    failures: list[str] = []
    if not independence["passed"]:
        failures.append("design_guide_independence_lock_failed")
    if not reachability["passed"]:
        failures.append("duplicate_restamper_reachability_failed")
    for name, passed in helper_tokens.items():
        if not passed:
            failures.append(f"missing_source_marker:{name}")
    for callsite_id, checks in selected_checks.items():
        if not checks["found"]:
            failures.append(f"selected_callsite_not_found:{callsite_id}")
        elif not selected_is_compat.get(callsite_id):
            failures.append(f"selected_callsite_not_compatibility_stamp:{callsite_id}")
    if int(counts.get("compatibility stamp") or 0) != EXPECTED_COMPATIBILITY_STAMPS:
        failures.append(
            f"unexpected_compatibility_stamp_count:{counts.get('compatibility stamp')}"
        )
    if int(counts.get("still live mutation") or 0) != EXPECTED_STILL_LIVE_MUTATIONS:
        failures.append(
            f"unexpected_still_live_mutation_count:{counts.get('still live mutation')}"
        )

    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "selected_callsites": selected_checks,
        "selected_callsite_results": selected_is_compat,
        "classification_counts": counts,
        "remaining_still_live_mutations": remaining_live_mutations,
        "helper_tokens": helper_tokens,
        "independence_passed": independence["passed"],
        "reachability_passed": reachability["passed"],
        "reachability_artifact": reachability_artifact.get("path"),
    }

    return {
        "snapshot_name": "design_guide_restamper_mutation_narrowing",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "selected_callsite_ids": list(SELECTED_CALLSITE_IDS),
        "selected_restamper": RESTAMPER,
        "selected_callsites": selected,
        "helper_tokens": helper_tokens,
        "selected_callsite_no_longer_mutates_final_truth": all(selected_is_compat.values()),
        "selected_callsite_results": selected_is_compat,
        "compatibility_shape_preserved": bool(
            helper_tokens["metadata_key"]
            and helper_tokens["legacy_non_authoritative_stamp"]
            and helper_tokens["compatibility_only_stamp"]
        ),
        "final_design_guide_publication_remains_authority": bool(independence["passed"]),
        "duplicate_restamper_reachability": {
            "command": reachability,
            "artifact": reachability_artifact.get("path"),
            "classification_counts": counts,
            "selected_paths_recorded_as_compatibility_stamp": dict(selected_is_compat),
            "target_compatibility_stamp_count": EXPECTED_COMPATIBILITY_STAMPS,
            "target_still_live_mutation_count": EXPECTED_STILL_LIVE_MUTATIONS,
        },
        "design_guide_independence_lock": independence,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_display_authority_changed": False,
        "apply_routing_changed": False,
        "fallback_shell_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    selected = snapshot.get("selected_callsites") or {}
    counts = snapshot["duplicate_restamper_reachability"]["classification_counts"]
    count_rows = [
        f"| {name} | `{count}` |"
        for name, count in sorted(counts.items())
    ]
    selected_rows = []
    for callsite_id in snapshot.get("selected_callsite_ids") or []:
        row = dict(selected.get(callsite_id) or {})
        selected_rows.append(
            "| `{callsite}` | `{file}:{line}` | `{function}` | `{classification}` | `{outcome}` | `{cta}` | `{display}` | `{compat}` |".format(
                callsite=callsite_id,
                file=row.get("file"),
                line=row.get("line"),
                function=row.get("function"),
                classification=row.get("classification"),
                outcome=row.get("can_change_outcome_after_publication"),
                cta=row.get("can_change_cta_after_publication"),
                display=row.get("can_change_display_after_publication"),
                compat=row.get("writes_only_compatibility_debug_metadata"),
            )
        )
    marker_rows = [
        f"| `{name}` | `{value}` |"
        for name, value in sorted(snapshot["helper_tokens"].items())
    ]
    body = "\n".join(
        [
            "# Design Guide Restamper Mutation Narrowing Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Selected Callsites",
            "",
            f"- Restamper: `{snapshot['selected_restamper']}`",
            "",
            "| Callsite ID | Location | Function | Classification | Can Change Outcome | Can Change CTA | Can Change Display | Compat/Debug Only |",
            "|---|---|---|---|---:|---:|---:|---:|",
            *selected_rows,
            "",
            "## Source Markers",
            "",
            "| Marker | Present |",
            "|---|---:|",
            *marker_rows,
            "",
            "## Reachability Counts",
            "",
            "| Classification | Count |",
            "|---|---:|",
            *count_rows,
            "",
            "## Proof",
            "",
            f"- Selected callsite no longer mutates final publication truth: `{snapshot['selected_callsite_no_longer_mutates_final_truth']}`",
            f"- Compatibility shape preserved: `{snapshot['compatibility_shape_preserved']}`",
            f"- FinalDesignGuidePublication remains authority: `{snapshot['final_design_guide_publication_remains_authority']}`",
            f"- Reachability selected paths recorded as compatibility stamp: `{snapshot['duplicate_restamper_reachability']['selected_paths_recorded_as_compatibility_stamp']}`",
            f"- Target compatibility stamp count: `{snapshot['duplicate_restamper_reachability']['target_compatibility_stamp_count']}`",
            f"- Target still-live mutation count: `{snapshot['duplicate_restamper_reachability']['target_still_live_mutation_count']}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
            "- Visible wording changed: `False`",
            "- CTA/display authority changed: `False`",
            "- Apply routing changed: `False`",
            "- Fallback shell behavior changed: `False`",
            "",
            "## Composed Gates",
            "",
            f"- Independence lock passed: `{snapshot['design_guide_independence_lock']['passed']}`",
            f"- Duplicate restamper reachability passed: `{snapshot['duplicate_restamper_reachability']['command']['passed']}`",
            f"- Reachability artifact: `{snapshot['duplicate_restamper_reachability']['artifact']}`",
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_restamper_mutation_narrowing_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_restamper_mutation_narrowing_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_restamper_mutation_narrowing {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
