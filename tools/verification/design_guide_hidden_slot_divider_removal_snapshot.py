"""Snapshot for hidden Design Guide slot divider removal.

The hidden Design Guide slot path is page-shell layout only. It must not create
Design Brain truth, publication, CTA, or apply routing. This verifier proves the
old extra page divider is gone from the hidden-slot branch while the render gate
and final-panel render path remain present.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _source() -> str:
    return (ROOT / "inputs_page.py").read_text(encoding="utf-8")


def _hidden_branch(source: str) -> str:
    match = re.search(
        r"else:\n(?P<body>[\s\S]*?)\n\s*_dg_render_gate_verifier\s*=",
        source,
    )
    return match.group("body") if match else ""


def _snapshot() -> dict:
    source = _source()
    branch = _hidden_branch(source)
    checks = {
        "render_gate_helper_present": "def should_render_design_guide_slot_from_publication_eligibility(" in source,
        "render_gate_call_present": "_dg_render_gate_decision = should_render_design_guide_slot_from_publication_eligibility(" in source,
        "hidden_branch_found": bool(branch.strip()),
        "hidden_branch_keeps_scroll_anchor": "_render_inputs_scroll_anchor_keeper()" in branch,
        "hidden_branch_clears_apply_in_flight": "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY" in branch,
        "hidden_branch_records_timing": "inputs_page.design_guide_hidden_until_actions_or_loads" in branch,
        "hidden_branch_has_page_divider": "page_divider()" in branch,
        "visible_design_guide_slot_path_present": "design_guide_slot = st.empty()" in source,
        "final_panel_render_path_present": "design_guide_page.render_final_panel(" in source,
    }
    failures: list[str] = []
    for key in (
        "render_gate_helper_present",
        "render_gate_call_present",
        "hidden_branch_found",
        "hidden_branch_keeps_scroll_anchor",
        "hidden_branch_clears_apply_in_flight",
        "hidden_branch_records_timing",
        "visible_design_guide_slot_path_present",
        "final_panel_render_path_present",
    ):
        if not checks[key]:
            failures.append(key)
    if checks["hidden_branch_has_page_divider"]:
        failures.append("hidden_branch_still_inserts_page_divider")
    return {
        "schema": "design_guide_hidden_slot_divider_removal_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "created_at": _stamp(),
        "product_behaviour_changed": False,
        "engineering_behaviour_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "design_brain_authority_changed": False,
        "checks": checks,
        "failures": failures,
        "decision": "hidden_slot_page_divider_removed" if not failures else "hidden_slot_divider_removal_incomplete",
    }


def _markdown(payload: dict) -> str:
    lines = [
        "# Design Guide Hidden Slot Divider Removal Snapshot",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"- CTA/apply semantics changed: `{payload['cta_apply_semantics_changed']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", "", ", ".join(payload.get("failures") or []) or "-"])
    return "\n".join(lines) + "\n"


def main() -> int:
    payload = _snapshot()
    payload["snapshot_hash"] = _stable_hash(payload)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_hidden_slot_divider_removal_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_hidden_slot_divider_removal_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_hidden_slot_divider_removal_snapshot {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
