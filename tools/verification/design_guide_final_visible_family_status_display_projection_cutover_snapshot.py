"""Final-visible family-status display projection cutover snapshot.

Proof-only. This verifies the final-visible branch no longer calls the old
page-owned `_attach_family_status_display_payload(...)` helper directly and now
feeds family-status display tables through a FinalDesignGuidePublication-owned
plain-data projection adapter.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_publication import (
    build_final_visible_family_status_display_projection,
    stable_final_publication_hash,
)
from tools.verification.design_guide_final_visible_branch_body_inventory_snapshot import (
    build_snapshot as build_branch_body_inventory_snapshot,
)


INPUTS = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_body(source: str, name: str) -> str:
    needle = f"def {name}("
    start = source.find(needle)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(needle))
    return source[start:] if next_def < 0 else source[start:next_def]


def _branch_window(body: str) -> str:
    start = body.find('callsite_id="final_contract_binding.enabled_action_output"')
    end = body.find('callsite_id="final_contract_binding.disabled_output"')
    if start < 0 or end < 0:
        return body
    disabled_return = body.find("    return out", end)
    if disabled_return < 0:
        return body[start:]
    return body[start : disabled_return + len("    return out")]


def _adapter_projection_cases() -> dict[str, Any]:
    cases = {
        "current_only": build_final_visible_family_status_display_projection(
            input_item={"title": "Design is efficient"},
            current_state_for_display={"b": 300, "D": 500},
            family_status_current={"bending": {"util": 0.67, "status": "PASS"}},
        ),
        "preview": build_final_visible_family_status_display_projection(
            input_item={"title": "Strengthening required"},
            current_state_for_display={"b": 300},
            family_status_current={"bending": {"util": 1.42, "status": "FAIL"}},
            family_status_preview={"bending": {"util": 0.92, "status": "PASS"}},
        ),
        "blocker": build_final_visible_family_status_display_projection(
            input_item={"title": "Design Guide blocker proof incomplete"},
            current_state_for_display={"b": 300},
            family_status_current={"shear": {"util": 1.23, "status": "FAIL"}},
            blocker_attempts_by_family={"shear": {"reason": "blocked"}},
        ),
    }
    return {
        name: {
            "payload": payload,
            "hash": stable_final_publication_hash(payload),
            "keys": sorted(payload.keys()),
        }
        for name, payload in cases.items()
    }


def build_snapshot() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    final_publication_source = _read(FINAL_PUBLICATION)
    binding_body = _function_body(inputs_source, "_publish_final_visible_design_guide_contract_binding")
    branch_inventory = build_branch_body_inventory_snapshot()
    branch_old_attach_count = sum(
        int(
            (((branch.get("future_extraction_candidate_hits") or {}).get("family_status_display_payload") or {}).get("count"))
            or 0
        )
        for branch in branch_inventory.get("branches", [])
    )
    branch_projection_bridge_count = sum(
        int(
            (((branch.get("page_shell_effect_hits") or {}).get("family_status_display_projection_helper") or {}).get("count"))
            or 0
        )
        for branch in branch_inventory.get("branches", [])
    )
    projection_bridge_body = _function_body(
        inputs_source,
        "_project_final_visible_family_status_display_payload",
    )
    adapter_cases = _adapter_projection_cases()
    checks = {
        "final_publication_adapter_exists": (
            "def build_final_visible_family_status_display_projection(" in final_publication_source
        ),
        "adapter_exported": '"build_final_visible_family_status_display_projection"' in final_publication_source,
        "inputs_imports_adapter": (
            "build_final_visible_family_status_display_projection as "
            "_build_final_visible_family_status_display_projection" in inputs_source
        ),
        "page_bridge_exists": bool(projection_bridge_body),
        "page_bridge_calls_adapter": (
            "_build_final_visible_family_status_display_projection(" in projection_bridge_body
        ),
        "branch_old_attach_calls_zero": branch_old_attach_count == 0,
        "branch_projection_bridge_calls_four": branch_projection_bridge_count == 4,
        "adapter_current_case_shape": set(adapter_cases["current_only"]["keys"]) == {
            "_current_state_for_display",
            "family_status_current",
        },
        "adapter_preview_case_shape": set(adapter_cases["preview"]["keys"]) == {
            "_current_state_for_display",
            "family_status_current",
            "family_status_preview",
        },
        "adapter_blocker_case_shape": set(adapter_cases["blocker"]["keys"]) == {
            "_current_state_for_display",
            "blocker_attempts_by_family",
            "family_status_current",
        },
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_family_status_display_projection_cutover_snapshot.v1",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "FINAL_VISIBLE_FAMILY_STATUS_DISPLAY_PROJECTION_ADAPTER_CUTOVER_PASS"
            if status == "PASS"
            else "FINAL_VISIBLE_FAMILY_STATUS_DISPLAY_PROJECTION_CUTOVER_NEEDS_ATTENTION"
        ),
        "checks": checks,
        "failures": failures,
        "branch_counts": {
            "old_attach_family_status_display_payload": branch_old_attach_count,
            "projection_bridge_calls": branch_projection_bridge_count,
            "inventory_artifact_status": branch_inventory.get("status"),
            "inventory_future_extraction_candidate_count": (
                branch_inventory.get("totals") or {}
            ).get("future_extraction_candidate_count"),
        },
        "adapter_cases": adapter_cases,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "run branch inventory and locks; if green, classify remaining future extraction candidates"
        ),
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Visible Family Status Display Projection Cutover",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Branch Counts",
        f"- old `_attach_family_status_display_payload(...)` calls: `{snapshot['branch_counts']['old_attach_family_status_display_payload']}`",
        f"- new projection bridge calls: `{snapshot['branch_counts']['projection_bridge_calls']}`",
        "",
        "## Adapter Cases",
    ]
    for name, row in snapshot["adapter_cases"].items():
        lines.append(f"- `{name}` keys: `{', '.join(row['keys'])}`")
        lines.append(f"  hash: `{row['hash']}`")
    lines.extend(
        [
            "",
            "## Failures",
            *(f"- `{failure}`" for failure in snapshot["failures"]),
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
        f"design_guide_final_visible_family_status_display_projection_cutover_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"design_guide_final_visible_family_status_display_projection_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(
        "design_guide_final_visible_family_status_display_projection_cutover "
        f"{snapshot['status']}"
    )
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
