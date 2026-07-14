"""Classify remaining final-visible branch page-shell projection effects."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_final_visible_branch_body_inventory_snapshot import (  # noqa: E402
    build_snapshot as build_branch_body_inventory_snapshot,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


CLASSIFICATION = {
    "primary_button_session_helper": {
        "class": "R1 retain page-shell for now",
        "owner": "inputs_page.py session/apply shell",
        "reason": "writes current primary button contract into Streamlit/session state",
        "next_action": "do not delete until apply/session binding is controller-returned and browser-live proven",
    },
    "primary_apply_payload_session_projection_helper": {
        "class": "R1 retain page-shell for now",
        "owner": "inputs_page.py apply payload shell",
        "reason": "records primary Apply payload for the current rendered card",
        "next_action": "needs CTA/apply payload controller-return parity before deletion",
    },
    "disabled_payload_binding_audit_projection_helper": {
        "class": "M1 move/delete candidate after audit",
        "owner": "compatibility/debug audit",
        "reason": "disabled-state payload audit should be derivable from FinalDesignGuidePublication.cta",
        "next_action": "prove disabled payload binding audit consumers are debug-only, then delete or adapter-drive",
    },
    "enabled_debug_projection_helper": {
        "class": "M1 move/delete candidate after audit",
        "owner": "debug projection",
        "reason": "debug payload should be same-object verifier/debug output, not branch-local projection",
        "next_action": "prove consumers use final publication verifier payload, then remove branch debug projection",
    },
    "disabled_debug_projection_helper": {
        "class": "M1 move/delete candidate after audit",
        "owner": "debug projection",
        "reason": "debug payload should be same-object verifier/debug output, not branch-local projection",
        "next_action": "prove consumers use final publication verifier payload, then remove branch debug projection",
    },
    "cta_authority_projection_helper": {
        "class": "R1 retain page-shell for now",
        "owner": "FinalDesignGuidePublication.cta stamp / page-shell binding",
        "reason": "binds CTA authority hash into current page/debug state",
        "next_action": "do not delete until CTA binding no longer needs page/session projection",
    },
    "family_status_display_projection_helper": {
        "class": "M2 controller-input migration candidate",
        "owner": "page supplies overview-derived inputs, FinalDesignGuidePublication owns projection shape",
        "reason": "still depends on live overview/preview/blocker tables from page/evaluator helpers",
        "next_action": "move overview-derived family status tables into controller request/result when evaluator boundary allows",
    },
    "combined_outside_target_blocker_projection_helper": {
        "class": "M2 controller-input migration candidate",
        "owner": "page supplies target-band/overview inputs, FinalDesignGuidePublication owns projection shape",
        "reason": "still depends on target-band and overview inputs from page/evaluator helpers",
        "next_action": "move outside-target blocker evidence input construction into controller/family proof",
    },
}


def build_snapshot() -> dict[str, Any]:
    inventory = build_branch_body_inventory_snapshot()
    rows: list[dict[str, Any]] = []
    totals_by_class: dict[str, int] = {}
    for branch in inventory.get("branches", []):
        page_shell_hits = branch.get("page_shell_effect_hits") or {}
        for helper, hit in page_shell_hits.items():
            count = int((hit or {}).get("count") or 0)
            if count <= 0:
                continue
            spec = CLASSIFICATION.get(
                helper,
                {
                    "class": "U unknown",
                    "owner": "unknown",
                    "reason": "not classified",
                    "next_action": "add classification before changing",
                },
            )
            totals_by_class[spec["class"]] = totals_by_class.get(spec["class"], 0) + count
            rows.append(
                {
                    "branch": branch.get("branch"),
                    "helper": helper,
                    "count": count,
                    **spec,
                }
            )
    failures = []
    inventory_totals = inventory.get("totals") or {}
    if inventory.get("status") != "PASS":
        failures.append("branch_inventory_not_pass")
    if inventory_totals.get("future_extraction_candidate_count") != 0:
        failures.append("future_extraction_candidates_not_zero")
    if any(row["class"] == "U unknown" for row in rows):
        failures.append("unknown_page_shell_effect_classification")
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_page_shell_effect_classification_snapshot.v1",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "FINAL_VISIBLE_PAGE_SHELL_EFFECTS_CLASSIFIED"
            if status == "PASS"
            else "FINAL_VISIBLE_PAGE_SHELL_EFFECTS_NEED_CLASSIFICATION"
        ),
        "rows": rows,
        "totals_by_class": totals_by_class,
        "inventory_totals": inventory_totals,
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "audit disabled payload binding/debug projection consumers first; these are the clearest move/delete candidates"
        ),
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Visible Page-Shell Effect Classification",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Summary",
        "| Branch | Helper | Count | Class | Owner | Next action |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for row in snapshot["rows"]:
        lines.append(
            "| {branch} | `{helper}` | {count} | {klass} | {owner} | {next_action} |".format(
                branch=row["branch"],
                helper=row["helper"],
                count=row["count"],
                klass=row["class"],
                owner=row["owner"],
                next_action=row["next_action"],
            )
        )
    lines.extend(
        [
            "",
            "## Totals By Class",
            *(
                f"- `{key}`: `{value}`"
                for key, value in sorted(snapshot["totals_by_class"].items())
            ),
            "",
            "## Next Safe Step",
            snapshot["next_safe_step"],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / (
        f"design_guide_final_visible_page_shell_effect_classification_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_final_visible_page_shell_effect_classification_{stamp}.md"
    )
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_guide_final_visible_page_shell_effect_classification {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
