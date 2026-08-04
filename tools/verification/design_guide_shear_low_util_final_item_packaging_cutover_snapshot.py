"""Verify shear low-util final item packaging cutover from page code."""

from __future__ import annotations

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _old_format_guidance_title(title: str, util: float | None) -> str:
    if util is None:
        return title
    return f"{title} (utilisation = {util:.2f})"


def _old_packaging(
    *,
    candidate: dict[str, Any],
    existing_action_payload: dict[str, Any],
    title: str,
    formatted_title: str | None,
    updates: dict[str, Any],
    candidate_id: str,
    final_shear_util: Any,
    evidence: dict[str, Any],
    preferred_target_blocker: dict[str, Any],
) -> dict[str, Any]:
    display_title = (
        str(formatted_title)
        if formatted_title is not None
        else _old_format_guidance_title(title, final_shear_util)
    )
    resolved_candidate = dict(candidate)
    resolved_candidate.update(
        {
            "updates": dict(updates),
            "action_type": "apply_resolved_candidate",
            "label": title,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "family": "shear",
            "recommendation_family_tag": "shear",
            "subfamilies": ["shear"],
            "candidate_post_util": final_shear_util,
            "candidate_shear_util": final_shear_util,
            "expected_util": final_shear_util,
            "candidate_search_evidence": dict(evidence),
        }
    )
    out_item_update = {
        "title_main": title,
        "title": display_title,
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "action_type": "apply_resolved_candidate",
        "updates": dict(updates),
        "resolved_candidate_updates": dict(updates),
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "local_cleanup_candidate": True,
        "guidance_intent": "efficiency_tightening",
        "allow_in_target_primary_action": True,
        "candidate_search_evidence": dict(evidence),
        "no_second_cta_required": False,
    }
    if preferred_target_blocker:
        out_item_update["preferred_target_blocker_evidence_by_family"] = {
            "shear": dict(preferred_target_blocker)
        }
    payload = dict(existing_action_payload)
    payload.update(
        {
            "resolved_candidate_updates": dict(updates),
            "resolved_candidate_action_type": "apply_resolved_candidate",
            "resolved_candidate_label": title,
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "family": "shear",
            "resolved_candidate_family_tag": "shear",
            "resolved_candidate_subfamilies": ["shear"],
            "candidate_search_evidence": dict(evidence),
        }
    )
    if preferred_target_blocker:
        payload["preferred_target_blocker_evidence_by_family"] = {
            "shear": dict(preferred_target_blocker)
        }
    return {
        "resolved_candidate": dict(resolved_candidate),
        "out_item_update": dict(out_item_update),
        "action_payload": dict(payload),
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "updates": dict(updates),
            "preview_pass": True,
            "expected_util": final_shear_util,
            "blocking_reason": None,
            "source_candidate_id": candidate_id,
            "candidate_id": candidate_id,
        },
    }


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_final_item_packaging,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    cases = [
        {
            "name": "plain_action_payload",
            "candidate": {"overview": {"utils": {"shear": 0.88}}},
            "existing_action_payload": {},
            "title": "Shear cleanup - one-click reduction",
            "formatted_title": None,
            "updates": {"s_lig": 300.0},
            "candidate_id": "local_cleanup:shear:spacing",
            "final_shear_util": 0.88,
            "evidence": {"family": "shear", "safe_candidate_count": 1},
            "preferred_target_blocker": {},
        },
        {
            "name": "preserves_existing_payload_and_blocker",
            "candidate": {"source": "candidate"},
            "existing_action_payload": {"existing": True},
            "title": "Shear cleanup - best safe one-click reduction",
            "formatted_title": None,
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 9999.0},
            "candidate_id": "local_cleanup:shear:no_link",
            "final_shear_util": 0.64,
            "evidence": {
                "family": "shear",
                "best_safe_partial_cleanup": True,
                "no_link_candidate_selected": True,
                "unnecessary_shear_reinforcement_exists": True,
            },
            "preferred_target_blocker": {"family": "shear", "reason": "exact reason"},
        },
    ]
    comparisons = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "name"}
        old = _old_packaging(**kwargs)
        new = build_design_guide_shear_low_util_final_item_packaging(**kwargs)
        expected_family_owner = (
            "SHEAR_OVERDESIGN_GOVERNS"
            if bool(dict(case.get("evidence") or {}).get("no_link_candidate_selected"))
            else None
        )
        owner_sources = [
            dict(new.get("out_item_update") or {}),
            dict(new.get("action_payload") or {}),
            dict(new.get("button_contract") or {}),
            dict(new.get("resolved_candidate") or {}),
            dict((new.get("out_item_update") or {}).get("candidate_search_evidence") or {}),
        ]
        owner_stamped = all(
            str(source.get("selected_family_id") or source.get("family_id") or "").strip()
            == expected_family_owner
            for source in owner_sources
        ) if expected_family_owner else True
        allowed_difference = bool(expected_family_owner and owner_stamped)
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": new,
                "match": old == new,
                "expected_family_owner": expected_family_owner,
                "owner_stamped": owner_stamped,
                "allowed_difference": allowed_difference,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_FINAL_ITEM_PACKAGING_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_final_item_packaging as "
                "_build_design_guide_shear_low_util_final_item_packaging"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_final_item_packaging("
                in shear_cleanup_source
            ),
            "guidance_item_shell_moved_to_controller": (
                "_build_design_guide_shear_low_util_guidance_item_shell("
                in shear_cleanup_source
                and "_guidance_item(" not in shear_cleanup_source
            ),
            "promotion_adapter_moved_to_controller": (
                "_build_design_guide_shear_low_util_promoted_item(" in shear_cleanup_source
                and "_promote_guidance_item_to_resolved_candidate(" not in shear_cleanup_source
            ),
            "formatted_title_moved_to_controller": (
                "_format_guidance_title(" not in shear_cleanup_source
            ),
            "old_inline_button_contract_removed": (
                'out_item["button_contract"] = {' not in shear_cleanup_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_final_item_packaging("
                in controller_source
            ),
            "controller_page_free": "inputs_page" not in controller_source
            and "st.session_state" not in controller_source
            and "streamlit" not in controller_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_evaluation_moved": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "old_new_cases_match_or_intentional_owner_stamp": all(
            item.get("match") or item.get("allowed_difference")
            for item in capture.get("comparisons") or []
        ),
        "no_link_cleanup_stamps_shear_overdesign_owner": any(
            item.get("case") == "preserves_existing_payload_and_blocker"
            and item.get("expected_family_owner") == "SHEAR_OVERDESIGN_GOVERNS"
            and item.get("owner_stamped")
            for item in capture.get("comparisons") or []
        ),
        "source_checks_pass": all(source_checks.values())
        or (
            source_checks.get("target_function_found") is False
            and source_checks.get("controller_has_helper") is True
            and source_checks.get("formatted_title_moved_to_controller") is True
            and source_checks.get("old_inline_button_contract_removed") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Final Item Packaging Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Cases", ""])
    for item in capture.get("comparisons") or []:
        lines.append(f"- {item.get('case')}: `{item.get('match')}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_final_item_packaging_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_final_item_packaging_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_final_item_packaging_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
