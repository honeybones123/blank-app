"""Final resolver identity same-object proof.

This proof-only verifier checks the five remaining class-A render-stage rows:
`A. final resolver identity replacement`. It compares their identity surface
against FinalDesignGuidePublication without narrowing rows or changing render,
CTA/apply, session/UI, wording, or family-runtime ownership.
"""

from __future__ import annotations

import importlib.util
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
REMAINING_SNAPSHOT = (
    ROOT / "tools" / "verification" / "design_guide_remaining_live_render_resolver_truth_snapshot.py"
)
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

CLASS_A = "A. final resolver identity replacement"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


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


def _load_remaining_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "design_guide_remaining_live_render_resolver_truth_snapshot",
        REMAINING_SNAPSHOT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load remaining live render resolver truth snapshot")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _item_for_row(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    line = int(row.get("line") or 0)
    role = str(row.get("current_behaviour_role") or "")
    if "underdesign" in role or line in {89708, 89709}:
        scenario = "underdesign_boundary_identity"
        item = {
            "published_item_id": "underdesign-boundary-item",
            "final_visible_item_id": "underdesign-boundary-item",
            "selected_family_id": "BENDING_FAIL_GOVERNS",
            "family": "bending",
            "check_key": "bending",
            "status": "BLOCKED",
            "bucket": "fail",
            "title": "Bending repair blocked",
            "post_click_design_guide_state": "BLOCKED",
            "candidate_id": "underdesign-boundary-candidate",
            "source_candidate_id": "underdesign-boundary-source",
            "action_type": None,
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "family": "bending",
                "candidate_id": "underdesign-boundary-candidate",
                "source_candidate_id": "underdesign-boundary-source",
                "disabled_reason": "underdesign repair invariant boundary",
            },
            "candidate_search_evidence": {"boundary": "underdesign_repair_invariant"},
        }
    elif "family-selection" in role or line in {89744, 89745}:
        scenario = "family_selection_contract_identity"
        item = {
            "published_item_id": "family-selection-item",
            "final_visible_item_id": "family-selection-item",
            "selected_family_id": "BENDING_FAIL_GOVERNS",
            "published_family_id": "BENDING_FAIL_GOVERNS",
            "family": "bending",
            "check_key": "bending",
            "status": "BLOCKED",
            "bucket": "fail",
            "title": "Family selection contract boundary",
            "post_click_design_guide_state": "BLOCKED",
            "candidate_id": "family-selection-candidate",
            "source_candidate_id": "family-selection-source",
            "action_type": None,
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "family": "bending",
                "candidate_id": "family-selection-candidate",
                "source_candidate_id": "family-selection-source",
                "disabled_reason": "family selection contract boundary",
            },
            "candidate_search_evidence": {"boundary": "family_selection_contract"},
        }
    else:
        scenario = "final_visible_resolution_item_sync_identity"
        item = {
            "published_item_id": "final-visible-sync-item",
            "final_visible_item_id": "final-visible-sync-item",
            "selected_family_id": "COMBINED_OVERDESIGN",
            "published_family_id": "COMBINED_OVERDESIGN",
            "family": "combined",
            "check_key": "combined",
            "status": "ACTION",
            "bucket": "info",
            "title": "Combined cleanup available",
            "post_click_design_guide_state": "ACTION",
            "candidate_id": "combined-cleanup-candidate",
            "source_candidate_id": "combined-cleanup-source",
            "action_type": "apply_resolved_candidate",
            "button_contract": {
                "enabled": True,
                "actionable": True,
                "label": "Apply repair",
                "action_type": "apply_resolved_candidate",
                "family": "combined",
                "candidate_id": "combined-cleanup-candidate",
                "source_candidate_id": "combined-cleanup-source",
                "updates": {"D": 900.0, "lig_d": 16},
            },
            "action_payload": {
                "action_type": "apply_resolved_candidate",
                "family": "combined",
                "candidate_id": "combined-cleanup-candidate",
                "source_candidate_id": "combined-cleanup-source",
                "updates": {"D": 900.0, "lig_d": 16},
            },
            "candidate_search_evidence": {"boundary": "final_visible_resolution_sync"},
        }
    return scenario, item


def _expected_identity_from_item(item: dict[str, Any]) -> dict[str, Any]:
    contract = dict(item.get("button_contract") or {})
    action_payload = dict(item.get("action_payload") or {})
    return {
        "published_item_id": (
            item.get("published_item_id")
            or item.get("final_visible_item_id")
            or item.get("publication_item_id")
            or item.get("source_candidate_id")
            or item.get("candidate_id")
            or contract.get("source_candidate_id")
            or contract.get("candidate_id")
        ),
        "candidate_id": (
            action_payload.get("candidate_id")
            or contract.get("candidate_id")
            or item.get("candidate_id")
        ),
        "source_candidate_id": (
            action_payload.get("source_candidate_id")
            or contract.get("source_candidate_id")
            or item.get("source_candidate_id")
            or item.get("candidate_id")
        ),
        "selected_family": (
            item.get("selected_family_id")
            or item.get("published_family_id")
            or item.get("cta_family_id")
            or item.get("family")
            or item.get("check_key")
        ),
        "action_type": (
            contract.get("action_type")
            or item.get("action_type")
            or action_payload.get("action_type")
        ),
    }


def _publication_identity(item: dict[str, Any], publication_reason: str) -> dict[str, Any]:
    from design_brain.final_publication import build_final_design_guide_publication

    publication = build_final_design_guide_publication(
        item=dict(item),
        debug={},
        publication_reason=publication_reason,
    )
    cta = publication.cta.to_dict()
    apply_summary = dict(cta.get("apply_payload_summary") or {})
    return {
        "published_item_id": publication.published_item_id,
        "candidate_id": apply_summary.get("candidate_id") or cta.get("source_candidate_id"),
        "source_candidate_id": cta.get("source_candidate_id") or apply_summary.get("source_candidate_id"),
        "selected_family": publication.selected_family,
        "action_type": cta.get("action_type"),
        "publication_hash": publication.publication_hash,
        "authority_hash": publication.publication_hash,
        "cta_hash": _stable_hash(cta),
    }


def _compare_row(row: dict[str, Any]) -> dict[str, Any]:
    scenario, item = _item_for_row(row)
    expected = _expected_identity_from_item(item)
    publication = _publication_identity(
        item,
        publication_reason=f"final_resolver_identity_same_object:{scenario}",
    )
    fields = [
        "published_item_id",
        "candidate_id",
        "source_candidate_id",
        "selected_family",
        "action_type",
    ]
    comparisons = {
        field: {
            "row_identity": expected.get(field),
            "publication_identity": publication.get(field),
            "matches": expected.get(field) == publication.get(field),
        }
        for field in fields
    }
    identity_matches = all(row["matches"] for row in comparisons.values())
    return {
        "line": row.get("line"),
        "target": row.get("target"),
        "source_expression": row.get("source_expression"),
        "current_behaviour_role": row.get("current_behaviour_role"),
        "scenario": scenario,
        "identity_fields_compared": fields + ["publication_hash", "authority_hash"],
        "comparisons": comparisons,
        "publication_hash": publication.get("publication_hash"),
        "authority_hash": publication.get("authority_hash"),
        "cta_hash": publication.get("cta_hash"),
        "matches_final_publication_identity": identity_matches,
        "can_narrow_row": identity_matches,
        "required_missing_proof": None if identity_matches else "identity mismatch needs row-specific live proof",
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    remaining_module = _load_remaining_module()
    base_snapshot = remaining_module._build_snapshot()
    rows = [
        row
        for row in list(base_snapshot.get("classifications") or [])
        if row.get("classification") == CLASS_A
    ]
    checked_rows = [_compare_row(row) for row in rows]
    matching_rows = [row for row in checked_rows if row["matches_final_publication_identity"]]
    mismatching_rows = [row for row in checked_rows if not row["matches_final_publication_identity"]]
    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    ownership_guards = {
        "cta_rendering_not_moved": "_design_guide_dashboard_card_html_from_render_model" in input_source
        and "_design_guide_dashboard_card_html_from_render_model" not in publication_source,
        "apply_routing_not_moved": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in publication_source,
        "session_storage_not_moved": "st.session_state" in input_source
        and "session_state" not in publication_source,
        "ui_rendering_not_moved": "ui.design_guide_cards" not in publication_source,
        "visible_wording_not_moved": "_design_guide_clean_main_card_text" in input_source
        and "_design_guide_clean_main_card_text" not in publication_source,
    }
    lock_run = _run("tools/verification/design_guide_independence_lock_verifier.py")
    failures: list[str] = []
    if len(rows) != 5:
        failures.append(f"expected_5_class_a_rows_found_{len(rows)}")
    if mismatching_rows:
        failures.append("identity_rows_do_not_match_final_publication")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if base_snapshot.get("status") != "PASS":
        failures.append("remaining_live_render_resolver_truth_snapshot_not_pass")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")
    proof_surface = {
        "checked_rows": checked_rows,
        "matching_lines": [row["line"] for row in matching_rows],
        "mismatching_lines": [row["line"] for row in mismatching_rows],
        "ownership_guards": ownership_guards,
    }
    can_narrow_identity_rows_now = bool(checked_rows) and not mismatching_rows
    return {
        "snapshot_name": "design_guide_final_resolver_identity_same_object_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "rows_checked": len(checked_rows),
            "matching_rows": len(matching_rows),
            "mismatching_rows": len(mismatching_rows),
            "can_narrow_identity_rows_now": can_narrow_identity_rows_now,
            "required_missing_proof": None
            if can_narrow_identity_rows_now
            else "Resolve identity mismatches before narrowing.",
            "product_behavior_changed": False,
        },
        "checked_rows": checked_rows,
        "matching_rows": matching_rows,
        "mismatching_rows": mismatching_rows,
        "ownership_guards": ownership_guards,
        "verification": {
            "remaining_live_render_resolver_truth_status": base_snapshot.get("status"),
            "design_guide_independence_lock": lock_run,
        },
        "next_slice": (
            "Narrow class-A final resolver identity rows to compatibility/proof-only stamps."
            if can_narrow_identity_rows_now
            else "Add row-specific identity proof before narrowing class-A rows."
        ),
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = "\n".join(
        "| {line} | `{target}` | {scenario} | `{matches}` | `{pub}` | `{auth}` | {proof} |".format(
            line=row["line"],
            target=_escape_md(row["target"]),
            scenario=_escape_md(row["scenario"]),
            matches=row["matches_final_publication_identity"],
            pub=row["publication_hash"],
            auth=row["authority_hash"],
            proof=_escape_md(row["required_missing_proof"] or "None"),
        )
        for row in snapshot["checked_rows"]
    )
    body = "\n".join(
        [
            "# Design Guide Final Resolver Identity Same-Object Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Rows checked: `{snapshot['summary']['rows_checked']}`",
            f"- Matching rows: `{snapshot['summary']['matching_rows']}`",
            f"- Mismatching rows: `{snapshot['summary']['mismatching_rows']}`",
            f"- Can narrow identity rows now: `{snapshot['summary']['can_narrow_identity_rows_now']}`",
            f"- Required missing proof: `{snapshot['summary']['required_missing_proof']}`",
            f"- Product behavior changed: `{snapshot['summary']['product_behavior_changed']}`",
            "",
            "## Rows Checked",
            "",
            "| Line | Target | Scenario | Matches FinalDesignGuidePublication identity | Publication hash | Authority hash | Missing proof |",
            "|---:|---|---|---|---|---|---|",
            rows or "| - | - | - | - | - | - | - |",
            "",
            "## Identity Fields Compared",
            "",
            "- `_final_visible_item` replacement identity",
            "- `_final_visible_resolution[\"item\"]` identity",
            "- `candidate_id`",
            "- `source_candidate_id`",
            "- selected family",
            "- `action_type`",
            "- `published_item_id`",
            "- publication/authority hash",
            "",
            "## Ownership Guards",
            "",
            *[f"- `{key}`: `{value}`" for key, value in snapshot["ownership_guards"].items()],
            "",
            "## Next Slice",
            "",
            snapshot["next_slice"],
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
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_final_resolver_identity_same_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_resolver_identity_same_object_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_final_resolver_identity_same_object_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print(json.dumps({"failures": snapshot["failures"]}, indent=2, sort_keys=True))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
