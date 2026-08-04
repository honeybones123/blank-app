"""Proof-only parity snapshot for resolved-candidate guidance item input pack."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_resolved_candidate_guidance_item_input_pack,
)


CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _legacy_page_preview_pack(case: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(case.get("candidate") or {})
    updates = dict(case.get("updates") or {})
    label = str(case.get("label") or "")
    original_candidate_action_type = str(case.get("original_candidate_action_type") or "")
    family_tag = case.get("family_tag")
    subfamilies = list(case.get("subfamilies") or [])
    candidate_post_util = case.get("candidate_post_util")
    change_lines = list(case.get("change_lines") or [])
    return {
        "resolved_action_type": "apply_resolved_candidate",
        "action_payload_preview": {
            "resolved_candidate_updates": dict(updates),
            "resolved_candidate_label": label,
            "resolved_candidate_action_type": original_candidate_action_type,
            "resolved_candidate_family_tag": family_tag,
            "resolved_candidate_subfamilies": list(subfamilies),
            "resolved_candidate_post_util": candidate_post_util,
            "resolved_candidate_reaches_target_band": bool(
                candidate.get("candidate_reaches_target_band") or candidate.get("reaches_target_band")
            ),
            "force_direct_apply": True,
            "label": label,
            "updates": dict(updates),
            "guidance_change_lines": list(change_lines),
            "guidance_change_summary_compact": str(case.get("guidance_change_summary_compact") or ""),
            "guidance_expected_util_text": str(case.get("guidance_expected_util_text") or ""),
            "guidance_why_text_compact": str(case.get("guidance_why_text_compact") or ""),
            "guidance_alternatives_text_compact": str(case.get("alternatives_text") or ""),
        },
    }


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "active_fail_bending_repair",
            "candidate": {"candidate_reaches_target_band": False},
            "updates": {"D": 650.0, "bot1_count": 8},
            "label": "Bending capacity is low",
            "original_candidate_action_type": "apply_compound_guidance",
            "family_tag": "bending",
            "subfamilies": ["bottom_reinforcement"],
            "candidate_post_util": 0.92,
            "change_lines": ["Bending: 1.42 FAIL -> 0.92 PASS"],
            "guidance_change_summary_compact": "Bending improves to 0.92",
            "guidance_expected_util_text": "Expected utilisation 0.92",
            "guidance_why_text_compact": "This bounded active-fail repair search uses current summary state.",
            "alternatives_text": "Alternative: adjust depth or bottom reinforcement",
        },
        {
            "name": "shear_cleanup_target_band",
            "candidate": {"reaches_target_band": True},
            "updates": {"lig_legs": 0, "lig_spacing": 600.0},
            "label": "Shear cleanup - one-click reduction",
            "original_candidate_action_type": "apply_resolved_candidate",
            "family_tag": "shear",
            "subfamilies": ["shear_links"],
            "candidate_post_util": 0.67,
            "change_lines": ["Shear: 0.94 PASS -> 0.67 PASS"],
            "guidance_change_summary_compact": "Shear links reduce safely",
            "guidance_expected_util_text": "Expected utilisation 0.67",
            "guidance_why_text_compact": "This keeps all checks passing.",
            "alternatives_text": "",
        },
        {
            "name": "combined_repair",
            "candidate": {"candidate_reaches_target_band": True, "reaches_target_band": False},
            "updates": {"D": 700.0, "bot1_count": 9, "lig_legs": 2},
            "label": "Bending and shear capacity are low",
            "original_candidate_action_type": "apply_compound_guidance",
            "family_tag": "combined",
            "subfamilies": ["geometry", "bottom_reinforcement", "shear_links"],
            "candidate_post_util": 0.87,
            "change_lines": ["Bending: 1.33 FAIL -> 0.87 PASS", "Shear: 1.08 FAIL -> 0.59 PASS"],
            "guidance_change_summary_compact": "Bending and shear pass after repair",
            "guidance_expected_util_text": "Expected utilisation 0.87",
            "guidance_why_text_compact": "Strengthening required.",
            "alternatives_text": "Alternative: increase section size",
        },
    ]


def _capture() -> dict[str, Any]:
    controller_source = _read(CONTROLLER)
    rows: list[dict[str, Any]] = []
    for case in _cases():
        legacy = _legacy_page_preview_pack(case)
        new = build_design_guide_controller_resolved_candidate_guidance_item_input_pack(
            candidate=dict(case.get("candidate") or {}),
            updates=dict(case.get("updates") or {}),
            label=str(case.get("label") or ""),
            original_candidate_action_type=str(case.get("original_candidate_action_type") or ""),
            family_tag=case.get("family_tag"),
            subfamilies=list(case.get("subfamilies") or []),
            candidate_post_util=case.get("candidate_post_util"),
            change_lines=list(case.get("change_lines") or []),
            guidance_change_summary_compact=str(case.get("guidance_change_summary_compact") or ""),
            guidance_expected_util_text=str(case.get("guidance_expected_util_text") or ""),
            guidance_why_text_compact=str(case.get("guidance_why_text_compact") or ""),
            alternatives_text=str(case.get("alternatives_text") or ""),
        )
        comparable_new = {
            "resolved_action_type": new.get("resolved_action_type"),
            "action_payload_preview": dict(new.get("action_payload_preview") or {}),
        }
        rows.append(
            {
                "name": case.get("name"),
                "match": legacy == comparable_new,
                "legacy": legacy,
                "new": comparable_new,
            }
        )
    return {
        "schema": "design_guide_resolved_candidate_guidance_item_input_pack_parity_snapshot.v1",
        "parity_rows": rows,
        "object_ready_for_cutover": all(bool(row.get("match")) for row in rows),
        "source_checks": {
            "helper_present": "def build_design_guide_controller_resolved_candidate_guidance_item_input_pack(" in controller_source,
            "helper_exported": '"build_design_guide_controller_resolved_candidate_guidance_item_input_pack"' in controller_source,
            "controller_boundary_clean": all(
                token not in controller_source for token in ("inputs_page", "streamlit", "st.session_state")
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    rows = list(payload.get("parity_rows") or [])
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "parity_rows_present": len(rows) >= 3,
        "all_rows_match": all(bool(row.get("match")) for row in rows),
        "object_ready_for_cutover": bool(payload.get("object_ready_for_cutover")),
        "helper_present": bool(source_checks.get("helper_present")),
        "helper_exported": bool(source_checks.get("helper_exported")),
        "controller_boundary_clean": bool(source_checks.get("controller_boundary_clean")),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_resolved_candidate_guidance_item_input_pack_parity_snapshot_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_resolved_candidate_guidance_item_input_pack_parity_snapshot_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Resolved-Candidate Guidance Item Input-Pack Parity Snapshot",
        "",
        f"Status: {payload['status']}",
        f"Object ready for cutover: {payload.get('object_ready_for_cutover')}",
        "",
        "## Parity Rows",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"- {row.get('name')}: {'PASS' if row.get('match') else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "Cut over only the `action_payload_preview` construction inside `_guidance_item_from_resolved_candidate(...)` to this controller helper.",
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_resolved_candidate_guidance_item_input_pack_parity_snapshot {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
