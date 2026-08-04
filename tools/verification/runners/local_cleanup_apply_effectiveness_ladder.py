from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
TIMESTAMP = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

LOCAL_CLEANUP_CASES = [
    "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP",
    "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
    "SHEAR_VISIBLE_CTA_APPLIES_SHEAR_PAYLOAD",
    "BENDING_TARGET_SHEAR_OVERPROVIDED_AFTER_CLICK",
    "BENDING_TARGET_SHEAR_LOW_FINAL_ACCEPTANCE",
    "SERVICEABILITY_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP",
    "GEOMETRY_LOW_REO_OR_SHEAR_IN_TARGET_LOCAL_CLEANUP",
]

INTENDED_FAMILY = {
    "BENDING_LOW_SHEAR_IN_TARGET_LOCAL_CLEANUP": "bending",
    "SHEAR_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP": "shear",
    "SHEAR_VISIBLE_CTA_APPLIES_SHEAR_PAYLOAD": "shear",
    "BENDING_TARGET_SHEAR_OVERPROVIDED_AFTER_CLICK": "shear",
    "BENDING_TARGET_SHEAR_LOW_FINAL_ACCEPTANCE": "shear",
    "SERVICEABILITY_LOW_BENDING_IN_TARGET_LOCAL_CLEANUP": "serviceability",
    "GEOMETRY_LOW_REO_OR_SHEAR_IN_TARGET_LOCAL_CLEANUP": "geometry",
}

FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _run_real_user_ladder_once(port: int, case_ids: list[str]) -> tuple[dict, str, str, int]:
    cmd = [
        sys.executable,
        str(REPO / "tools" / "verification" / "runners" / "real_user_design_guide_ladder.py"),
        "--port",
        str(port),
    ]
    for case_id in case_ids:
        cmd.extend(["--case", case_id])
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    payload: dict[str, Any] = {}
    try:
        payload = json.loads(proc.stdout.strip())
    except Exception:
        try:
            start = proc.stdout.rfind("{")
            end = proc.stdout.rfind("}")
            payload = json.loads(proc.stdout[start : end + 1]) if start >= 0 and end > start else {}
        except Exception:
            payload = {}
    artifact_path = payload.get("output")
    if artifact_path:
        try:
            with open(artifact_path, encoding="utf-8-sig") as f:
                data = json.load(f)
            data["_artifact_path"] = artifact_path
            return data, proc.stdout, proc.stderr, proc.returncode
        except Exception as exc:
            return {"_load_error": str(exc), "_artifact_path": artifact_path}, proc.stdout, proc.stderr, proc.returncode
    return {"_load_error": "missing_real_user_artifact"}, proc.stdout, proc.stderr, proc.returncode


def _run_real_user_ladder(port: int, case_ids: list[str] | None = None) -> tuple[dict, str, str, int]:
    selected_cases = list(case_ids or LOCAL_CLEANUP_CASES)
    if len(selected_cases) <= 1:
        return _run_real_user_ladder_once(port, selected_cases)

    combined_cases: list[dict[str, Any]] = []
    child_artifacts: list[str] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    returncode = 0
    validity_fail_reasons: list[str] = []
    one_click_statuses: list[str] = []
    for offset, case_id in enumerate(selected_cases):
        data, stdout, stderr, code = _run_real_user_ladder_once(port + offset, [case_id])
        stdout_parts.append(stdout)
        stderr_parts.append(stderr)
        if code != 0:
            returncode = code if returncode == 0 else returncode
        artifact_path = str(data.get("_artifact_path") or "")
        if artifact_path:
            child_artifacts.append(artifact_path)
        combined_cases.extend([dict(case) for case in list(data.get("cases") or [])])
        if data.get("verifier_validity_status") != "VALID":
            validity_fail_reasons.extend(
                [f"{case_id}:{reason}" for reason in list(data.get("verifier_validity_fail_reasons") or [])]
            )
        one_click_statuses.append(str(data.get("one_click_contract_status") or "UNKNOWN"))

    fail_count = sum(1 for case in combined_cases if case.get("verdict") != "PASS")
    combined = {
        "verdict": "PASS" if fail_count == 0 and returncode == 0 else "FAIL",
        "total_cases": len(combined_cases),
        "pass_count": len(combined_cases) - fail_count,
        "fail_count": fail_count,
        "verifier_validity_status": "VALID" if fail_count == 0 and not validity_fail_reasons else "INVALID",
        "verifier_validity_fail_reasons": validity_fail_reasons,
        "one_click_contract_status": "PASS" if all(status == "PASS" for status in one_click_statuses) else "FAIL",
        "_artifact_path": child_artifacts[-1] if child_artifacts else "",
        "_child_artifact_paths": child_artifacts,
        "cases": combined_cases,
    }
    return combined, "\n".join(stdout_parts), "\n".join(stderr_parts), returncode


def _visible_inputs(case: dict, suffix: str) -> dict:
    return dict(case.get(f"visible_inputs_{suffix}") or {})


def _bottom_proxy(inputs: dict) -> float:
    bars = _float(inputs.get("bottom_bars")) or 0.0
    dia = _float(inputs.get("bottom_dia")) or 0.0
    return bars * dia * dia


def _geometry_proxy(inputs: dict) -> float:
    b = _float(inputs.get("b")) or 0.0
    d = _float(inputs.get("D")) or 0.0
    return b * d


def _shear_proxy(inputs: dict) -> float:
    dia = _float(inputs.get("link_dia")) or 0.0
    legs = _float(inputs.get("link_legs")) or 0.0
    spacing = max(_float(inputs.get("link_spacing")) or 1.0, 1.0)
    return legs * dia * dia / spacing


def _updates_affect_serviceability(updates: dict) -> bool:
    keys = {str(key) for key in dict(updates or {})}
    return bool(
        keys & {"b", "D", "bw", "bf", "tf", "tw"}
        or any(key.startswith("bot") or key.startswith("db_bot") for key in keys)
    )


def _updates_affect_material(updates: dict) -> bool:
    keys = {str(key) for key in dict(updates or {})}
    return bool(
        keys & {"b", "D", "bw", "bf", "tf", "tw", "lig_d", "lig_legs", "s_lig", "link_dia", "link_legs", "link_spacing"}
        or any(key.startswith("bot") or key.startswith("db_bot") for key in keys)
    )


def _selected_evidence_row(case: dict) -> dict:
    selected_id = str(
        case.get("selected_candidate_id")
        or dict(case.get("button_contract") or {}).get("candidate_id")
        or dict(case.get("button_contract") or {}).get("source_candidate_id")
        or ""
    )
    evidence = dict(case.get("candidate_search_evidence") or {})
    rows: list[dict] = []
    for bucket in (
        "target_band_candidates",
        "safe_executor_backed_candidates",
        "rejected_target_band_candidates",
    ):
        rows.extend([dict(row) for row in list(evidence.get(bucket) or []) if isinstance(row, dict)])
    rows.extend([dict(row) for row in list(case.get("local_cleanup_candidate_inventory") or []) if isinstance(row, dict)])
    for row in rows:
        if selected_id and str(row.get("candidate_id") or "") == selected_id:
            return row
    updates = dict(case.get("selected_action_updates") or dict(case.get("button_contract") or {}).get("updates") or {})
    for row in rows:
        if updates and dict(row.get("proposed_updates") or row.get("updates") or {}) == updates:
            return row
    return {}


def _selected_material_delta(case: dict) -> float | None:
    row = _selected_evidence_row(case)
    for key in ("material_proxy_delta",):
        parsed = _float(row.get(key))
        if parsed is not None:
            return parsed
    efficiency = _float(row.get("net_efficiency_delta"))
    if efficiency is not None:
        return -float(efficiency)
    return None


def _changed_keys_from_updates(updates: dict, before: dict, after: dict) -> list[str]:
    changed = []
    for key in ("b", "D", "bottom_bars", "bottom_dia", "link_dia", "link_legs", "link_spacing"):
        if str(before.get(key)) != str(after.get(key)):
            changed.append(key)
    return changed


def _status_failures(summary: dict) -> list[str]:
    failures = []
    for family in ("bending", "shear"):
        row = dict(summary.get(family) or {})
        status = str(row.get("status") or "").strip().upper()
        if status == "FAIL":
            failures.append(f"post_click_{family}_failed")
    return failures


def _intended_family_improved(case: dict, before: dict, after: dict, movement: dict) -> tuple[bool, dict]:
    case_id = str(case.get("case_id") or "")
    intended = INTENDED_FAMILY.get(case_id, "")
    selected_family = str(
        case.get("selected_action_family")
        or dict(case.get("button_contract") or {}).get("family")
        or ""
    ).strip().lower()
    if (
        intended == "serviceability"
        and selected_family in {"bending", "shear", "geometry", "combined"}
        and _float(movement.get("serviceability_before")) is None
        and _float(movement.get("serviceability_after")) is None
    ):
        intended = selected_family
    details: dict[str, Any] = {"intended_family": intended}
    updates = dict(case.get("selected_action_updates") or dict(case.get("button_contract") or {}).get("updates") or {})
    if intended == "shear":
        before_proxy = _shear_proxy(before)
        after_proxy = _shear_proxy(after)
        before_util = _float(movement.get("shear_before"))
        after_util = _float(movement.get("shear_after"))
        details.update({"shear_proxy_before": before_proxy, "shear_proxy_after": after_proxy})
        return bool(after_proxy < before_proxy - 1e-9 or (before_util is not None and after_util is not None and after_util > before_util + 1e-3)), details
    if intended in {"bending", "combined"}:
        before_proxy = _bottom_proxy(before)
        after_proxy = _bottom_proxy(after)
        before_util = _float(movement.get("bending_before"))
        after_util = _float(movement.get("bending_after"))
        details.update({"bottom_proxy_before": before_proxy, "bottom_proxy_after": after_proxy})
        return bool(after_proxy < before_proxy - 1e-9 or (before_util is not None and after_util is not None and after_util > before_util + 1e-3)), details
    if intended == "geometry":
        before_proxy = _geometry_proxy(before)
        after_proxy = _geometry_proxy(after)
        before_shear_proxy = _shear_proxy(before)
        after_shear_proxy = _shear_proxy(after)
        material_delta = _selected_material_delta(case)
        details.update({
            "geometry_proxy_before": before_proxy,
            "geometry_proxy_after": after_proxy,
            "shear_material_proxy_before": before_shear_proxy,
            "shear_material_proxy_after": after_shear_proxy,
            "selected_material_delta": material_delta,
        })
        return bool(
            after_proxy < before_proxy - 1e-9
            or after_shear_proxy < before_shear_proxy - 1e-9
            or (material_delta is not None and material_delta < -1e-9)
        ), details
    before_material = _geometry_proxy(before) * 0.001 + _bottom_proxy(before) * 0.04
    after_material = _geometry_proxy(after) * 0.001 + _bottom_proxy(after) * 0.04
    material_delta = _selected_material_delta(case)
    before_worst = _float(movement.get("worst_before"))
    after_worst = _float(movement.get("worst_after"))
    details.update({
        "serviceability_material_proxy_before": before_material,
        "serviceability_material_proxy_after": after_material,
        "selected_material_delta": material_delta,
        "updates_affect_serviceability": _updates_affect_serviceability(updates),
    })
    return bool(
        after_material < before_material - 1e-9
        or (material_delta is not None and material_delta < -1e-9)
        or (
            _updates_affect_serviceability(updates)
            and before_worst is not None
            and after_worst is not None
            and after_worst > before_worst + 1e-3
        )
    ), details


def _case_effectiveness(case: dict) -> dict:
    case_id = str(case.get("case_id") or "")
    before = _visible_inputs(case, "before")
    after = _visible_inputs(case, "after")
    button = dict(case.get("button_contract") or {})
    updates = dict(button.get("updates") or case.get("selected_action_updates") or {})
    visible_primary_candidate_id = str(case.get("visible_primary_candidate_id") or "").strip()
    button_contract_candidate_id = str(
        case.get("button_contract_candidate_id")
        or button.get("source_candidate_id")
        or button.get("candidate_id")
        or ""
    ).strip()
    queued_apply_candidate_id = str(case.get("queued_apply_candidate_id") or "").strip()
    applied_candidate_id = str(case.get("applied_candidate_id") or "").strip()
    visible_updates = dict(case.get("visible_updates") or updates)
    button_contract_updates = dict(case.get("button_contract_updates") or updates)
    queued_apply_updates = dict(case.get("queued_apply_updates") or {})
    applied_updates = dict(case.get("applied_updates") or {})
    applied_changed_keys = [str(key) for key in list(case.get("applied_changed_keys") or [])]
    stale_candidate_changed_keys = [str(key) for key in list(case.get("stale_candidate_changed_keys") or [])]
    payload_binding_match = bool(case.get("payload_binding_match"))
    payload_update_match = bool(case.get("payload_update_match"))
    stale_apply_payload_blocked = bool(case.get("stale_apply_payload_blocked"))
    legacy_fallback_used = bool(case.get("legacy_fallback_used"))
    movement = dict(case.get("utilisation_movement") or {})
    changed_keys = list(case.get("changed_fields") or _changed_keys_from_updates(updates, before, after))
    cta_visible = bool(case.get("one_click_button_visible_before"))
    cta_enabled = bool(case.get("one_click_button_enabled_before"))
    click_attempted = bool(case.get("click_attempted"))
    executable = bool(button.get("actionable") and button.get("action_type") and updates and button.get("preview_pass") is True and button.get("blocking_reason") in (None, ""))
    advisory_only = bool(case.get("advisory_only") or button.get("advisory_only"))
    family_ok, improvement_details = _intended_family_improved(case, before, after, movement)
    post_click_primary_cta_visible = bool(
        case.get("post_click_primary_cta_visible", case.get("one_click_button_visible_after"))
    )
    post_click_primary_cta_enabled = bool(
        case.get("post_click_primary_cta_enabled", case.get("one_click_button_enabled_after"))
    )
    post_click_accepted_green = bool(case.get("post_click_accepted_green"))
    post_click_accepted_green_valid = bool(case.get("post_click_accepted_green_valid", True))
    post_click_valid_blocker = bool(case.get("post_click_valid_blocker_if_not_target"))
    post_click_in_target = bool(case.get("post_click_in_target_band"))
    post_click_family_utils = dict(case.get("post_click_family_utils") or {})
    post_click_material_families = [
        str(family or "").strip().lower()
        for family in list(case.get("post_click_materially_overprovided_families") or [])
        if str(family or "").strip()
    ]
    post_click_unresolved_families = [
        str(family or "").strip().lower()
        for family in list(case.get("post_click_unresolved_overprovided_families") or [])
        if str(family or "").strip()
    ]
    post_click_unresolved_low_util_families = [
        str(family or "").strip().lower()
        for family in list(case.get("post_click_unresolved_low_util_families") or post_click_unresolved_families)
        if str(family or "").strip()
    ]
    post_click_below_final_threshold = [
        str(family or "").strip().lower()
        for family in list(case.get("post_click_families_below_final_threshold") or [])
        if str(family or "").strip()
    ]
    post_click_exact_blockers = dict(case.get("post_click_exact_blockers_by_family") or {})
    post_click_exact_blocker_terminal = bool(
        post_click_exact_blockers
        and post_click_accepted_green_valid
        and not post_click_unresolved_low_util_families
    )
    post_click_terminal_accepted_or_blocked = bool(
        post_click_accepted_green
        or post_click_valid_blocker
        or (post_click_in_target and post_click_exact_blocker_terminal)
    )
    geometry_delta = {
        "b": (_float(after.get("b")) or 0.0) - (_float(before.get("b")) or 0.0),
        "D": (_float(after.get("D")) or 0.0) - (_float(before.get("D")) or 0.0),
    }
    fail_reasons = list(case.get("fail_reasons") or [])
    if str(case.get("browser_mode") or "") != "browser_live":
        fail_reasons.append("browser_mode_not_browser_live")
    if cta_enabled and not executable:
        fail_reasons.append("primary_cta_enabled_but_candidate_not_executable")
    if advisory_only and cta_enabled:
        fail_reasons.append("advisory_cleanup_rendered_as_primary_cta")
    if cta_enabled and button.get("preview_pass") is True and button.get("blocking_reason"):
        fail_reasons.append("preview_passed_but_button_contract_rejected")
    if cta_enabled and not changed_keys:
        fail_reasons.append("cleanup_click_no_visible_effect")
    if cta_enabled and not family_ok:
        fail_reasons.append("intended_family_not_improved")
    if cta_enabled and not click_attempted:
        fail_reasons.append("primary_cta_enabled_but_click_not_attempted")
    if click_attempted:
        ids = [
            visible_primary_candidate_id,
            button_contract_candidate_id,
            queued_apply_candidate_id,
            applied_candidate_id,
        ]
        if not all(ids) or len(set(ids)) != 1:
            fail_reasons.append("primary_payload_candidate_binding_mismatch")
        maps = [visible_updates, button_contract_updates, queued_apply_updates, applied_updates]
        if not all(maps) or any(candidate != maps[0] for candidate in maps[1:]):
            fail_reasons.append("primary_payload_update_binding_mismatch")
        if not payload_binding_match:
            fail_reasons.append("payload_binding_match_false")
        if not payload_update_match:
            fail_reasons.append("payload_update_match_false")
        if legacy_fallback_used:
            fail_reasons.append("primary_click_used_legacy_fallback")
        if stale_apply_payload_blocked:
            fail_reasons.append("stale_apply_payload_blocked")
        if stale_candidate_changed_keys:
            fail_reasons.append("applied_stale_candidate_keys_not_in_visible_updates")
        internal_changed_not_visible = [
            key for key in applied_changed_keys if key not in set(str(k) for k in visible_updates.keys())
        ]
        if internal_changed_not_visible:
            fail_reasons.append("actual_changed_keys_not_in_visible_proposed_updates")
    if click_attempted and (post_click_primary_cta_visible or post_click_primary_cta_enabled):
        fail_reasons.append("post_click_primary_cta_still_visible_or_enabled")
    if click_attempted and post_click_unresolved_families:
        fail_reasons.append("post_click_unresolved_materially_overprovided_families")
    if click_attempted and post_click_unresolved_low_util_families:
        fail_reasons.append("post_click_unresolved_low_util_families_below_0_85")
    if click_attempted and post_click_accepted_green and not post_click_accepted_green_valid:
        fail_reasons.append("post_click_accepted_green_has_unresolved_overprovided_families")
    if click_attempted and not post_click_terminal_accepted_or_blocked:
        fail_reasons.append("post_click_not_accepted_green_or_valid_blocker")
    if click_attempted and not (post_click_in_target or post_click_valid_blocker):
        fail_reasons.append("post_click_not_in_target_band_or_valid_blocker")
    if not cta_enabled:
        if int(case.get("executable_safe_cleanup_count") or 0) > 0:
            fail_reasons.append("no_primary_cta_but_executable_safe_cleanup_exists")
        if not post_click_terminal_accepted_or_blocked:
            fail_reasons.append("no_primary_cta_without_terminal_accepted_or_exact_blocker")
    fail_reasons.extend(_status_failures(dict(case.get("visible_summary_after") or {})))
    shear_after = _float(
        post_click_family_utils.get("shear")
        if post_click_family_utils.get("shear") is not None
        else movement.get("shear_after")
    )
    if (
        case_id == "BENDING_TARGET_SHEAR_OVERPROVIDED_AFTER_CLICK"
        or case_id == "BENDING_TARGET_SHEAR_LOW_FINAL_ACCEPTANCE"
    ) and (
        post_click_accepted_green
        and shear_after is not None
        and shear_after < FINAL_ACCEPTED_MIN_FAMILY_UTIL
        and "shear" not in post_click_exact_blockers
    ):
        fail_reasons.append("accepted_green_with_shear_util_below_0_85_without_blocker")
    if (
        case_id == "BENDING_TARGET_SHEAR_OVERPROVIDED_AFTER_CLICK"
        and post_click_accepted_green
        and shear_after is not None
        and shear_after < 0.70
        and "shear" not in post_click_exact_blockers
    ):
        fail_reasons.append("accepted_green_with_shear_util_below_0_70_without_blocker")
    if cta_enabled and geometry_delta["b"] > 1e-9 and geometry_delta["D"] >= -1e-9 and INTENDED_FAMILY.get(case_id) != "geometry":
        fail_reasons.append("incoherent_cleanup_geometry_increase")
    return {
        "case_id": case_id,
        "browser_mode": case.get("browser_mode"),
        "selected_title": case.get("selected_action_title"),
        "selected_family": case.get("selected_action_family"),
        "selected_action_type": case.get("selected_action_type") or button.get("action_type"),
        "primary_cta_visible": cta_visible,
        "primary_cta_enabled": cta_enabled,
        "click_attempted": click_attempted,
        "button_contract_status": "enabled" if executable else "not_executable",
        "button_contract_rejection_reason": button.get("blocking_reason"),
        "proposed_updates": updates,
        "preview_status": "PASS" if button.get("preview_pass") is True else "FAIL_OR_UNKNOWN",
        "visible_primary_candidate_id": visible_primary_candidate_id,
        "button_contract_candidate_id": button_contract_candidate_id,
        "queued_apply_candidate_id": queued_apply_candidate_id,
        "applied_candidate_id": applied_candidate_id,
        "visible_updates": visible_updates,
        "button_contract_updates": button_contract_updates,
        "queued_apply_updates": queued_apply_updates,
        "applied_updates": applied_updates,
        "applied_changed_keys": applied_changed_keys,
        "stale_candidate_changed_keys": stale_candidate_changed_keys,
        "payload_binding_match": payload_binding_match,
        "payload_update_match": payload_update_match,
        "stale_apply_payload_blocked": stale_apply_payload_blocked,
        "legacy_fallback_used": legacy_fallback_used,
        "before_util_by_family": {
            "bending": movement.get("bending_before"),
            "shear": movement.get("shear_before"),
            "worst": movement.get("worst_before"),
        },
        "post_click_util_by_family": {
            "bending": movement.get("bending_after"),
            "shear": movement.get("shear_after"),
            "worst": movement.get("worst_after"),
        },
        "before_state": before,
        "post_click_state": after,
        "intended_improvement_family": improvement_details.get("intended_family") or INTENDED_FAMILY.get(case_id),
        "actual_improvement_delta_by_family": improvement_details,
        "changed_keys": changed_keys,
        "changed_key_count": len(changed_keys),
        "geometry_delta": geometry_delta,
        "reo_delta": {
            "bottom_proxy": _bottom_proxy(after) - _bottom_proxy(before),
            "shear_proxy": _shear_proxy(after) - _shear_proxy(before),
        },
        "advisory_only": advisory_only,
        "executable": executable,
        "post_click_design_guide_state": case.get("post_click_design_guide_state"),
        "post_click_design_guide_title": case.get("post_click_design_guide_title"),
        "post_click_primary_cta_visible": post_click_primary_cta_visible,
        "post_click_primary_cta_enabled": post_click_primary_cta_enabled,
        "post_click_executable_safe_cleanup_count": case.get("post_click_executable_safe_cleanup_count"),
        "post_click_safe_local_cleanup_count": case.get("post_click_safe_local_cleanup_count"),
        "post_click_in_target_band": post_click_in_target,
        "post_click_valid_blocker_if_not_target": post_click_valid_blocker,
        "post_click_accepted_green": post_click_accepted_green,
        "post_click_accepted_green_valid": post_click_accepted_green_valid,
        "post_click_exact_blocker_terminal": post_click_exact_blocker_terminal,
        "post_click_terminal_accepted_or_blocked": post_click_terminal_accepted_or_blocked,
        "post_click_accepted_green_invalid_reason": case.get("post_click_accepted_green_invalid_reason"),
        "final_accepted_min_family_util": case.get("final_accepted_min_family_util", FINAL_ACCEPTED_MIN_FAMILY_UTIL),
        "post_click_family_utils": post_click_family_utils,
        "post_click_family_utils_meaningful": dict(case.get("post_click_family_utils_meaningful") or {}),
        "post_click_families_below_final_threshold": post_click_below_final_threshold,
        "post_click_unresolved_low_util_families": post_click_unresolved_low_util_families,
        "post_click_excluded_families": dict(case.get("post_click_excluded_families") or {}),
        "post_click_materially_overprovided_families": post_click_material_families,
        "post_click_unresolved_overprovided_families": post_click_unresolved_families,
        "post_click_cleanup_evidence_by_family": dict(case.get("post_click_cleanup_evidence_by_family") or {}),
        "post_click_exact_blockers_by_family": post_click_exact_blockers,
        "post_click_remaining_cleanup_reason": case.get("post_click_remaining_cleanup_reason"),
        "post_click_all_required_checks_pass": case.get("post_click_all_required_checks_pass"),
        "post_click_failed_checks": list(case.get("post_click_failed_checks") or []),
        "final_publication_post_click_exact_blocker_raw_bound_parity": dict(
            case.get("final_publication_post_click_exact_blocker_raw_bound_parity") or {}
        ),
        "final_publication_post_click_exact_blocker_raw_bound_parity_hash": case.get(
            "final_publication_post_click_exact_blocker_raw_bound_parity_hash"
        ),
        "final_publication_post_click_exact_blocker_raw_item_hash": case.get(
            "final_publication_post_click_exact_blocker_raw_item_hash"
        ),
        "final_publication_post_click_exact_blocker_bound_item_hash": case.get(
            "final_publication_post_click_exact_blocker_bound_item_hash"
        ),
        "final_publication_post_click_exact_blocker_raw_bound_adapter_result_parity": case.get(
            "final_publication_post_click_exact_blocker_raw_bound_adapter_result_parity"
        ),
        "final_publication_post_click_exact_blocker_ready_to_replace_old_binding": case.get(
            "final_publication_post_click_exact_blocker_ready_to_replace_old_binding"
        ),
        "final_publication_post_click_exact_blocker_raw_bound_parity_error": case.get(
            "final_publication_post_click_exact_blocker_raw_bound_parity_error"
        ),
        "verdict": "PASS" if not fail_reasons else "FAIL",
        "fail_reasons": fail_reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8524)
    parser.add_argument("--case", action="append", dest="case_ids", default=None)
    parser.add_argument("--cases", default=None, help="Comma-separated case_id list.")
    parser.add_argument("--list-cases", action="store_true")
    args = parser.parse_args()
    if args.list_cases:
        print("\n".join(LOCAL_CLEANUP_CASES))
        return 0
    selected_case_ids = {
        str(case_id).strip()
        for case_id in (args.case_ids or [])
        if str(case_id).strip()
    }
    selected_case_ids.update(
        str(case_id).strip()
        for case_id in str(args.cases or "").split(",")
        if str(case_id).strip()
    )
    missing_case_ids = sorted(selected_case_ids - set(LOCAL_CLEANUP_CASES))
    if missing_case_ids:
        raise SystemExit(f"Unknown local cleanup effectiveness case(s): {', '.join(missing_case_ids)}")
    run_case_ids = [case_id for case_id in LOCAL_CLEANUP_CASES if not selected_case_ids or case_id in selected_case_ids]
    real_user, stdout, stderr, returncode = _run_real_user_ladder(args.port, run_case_ids)
    cases = [_case_effectiveness(dict(case)) for case in list(real_user.get("cases") or [])]
    fail_count = sum(1 for case in cases if case["verdict"] != "PASS")
    summary = {
        "total_cases": len(cases),
        "PASS_count": len(cases) - fail_count,
        "FAIL_count": fail_count,
        "requires_post_click_green_or_accepted": True,
        "requires_target_band_or_exact_blocker": True,
        "can_pass_without_intended_family_improvement": False,
        "can_pass_with_post_click_cta_still_visible": False,
        "requires_accepted_green_no_unresolved_overprovided_families": True,
        "can_pass_with_shear_util_below_0_70_without_blocker": False,
        "final_accepted_min_family_util": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
        "requires_all_meaningful_family_utils_ge_0_85_or_exact_blocker": True,
        "can_pass_with_shear_util_below_0_85_without_blocker": False,
        "can_pass_with_accepted_green_unresolved_low_util_families": False,
        "low_util_family_blocker_evidence_required": True,
        "browser_mode_required": "browser_live",
        "non_executable_primary_failures": sum("primary_cta_enabled_but_candidate_not_executable" in c["fail_reasons"] for c in cases),
        "advisory_primary_failures": sum("advisory_cleanup_rendered_as_primary_cta" in c["fail_reasons"] for c in cases),
        "preview_button_contract_mismatch_failures": sum("preview_passed_but_button_contract_rejected" in c["fail_reasons"] for c in cases),
        "click_no_effect_failures": sum("cleanup_click_no_visible_effect" in c["fail_reasons"] for c in cases),
        "click_not_attempted_failures": sum("primary_cta_enabled_but_click_not_attempted" in c["fail_reasons"] for c in cases),
        "intended_family_not_improved_failures": sum("intended_family_not_improved" in c["fail_reasons"] for c in cases),
        "post_click_not_accepted_failures": sum("post_click_not_accepted_green_or_valid_blocker" in c["fail_reasons"] for c in cases),
        "post_click_cta_still_visible_failures": sum("post_click_primary_cta_still_visible_or_enabled" in c["fail_reasons"] for c in cases),
        "post_click_target_or_blocker_failures": sum("post_click_not_in_target_band_or_valid_blocker" in c["fail_reasons"] for c in cases),
        "post_click_unresolved_overprovided_failures": sum("post_click_unresolved_materially_overprovided_families" in c["fail_reasons"] for c in cases),
        "post_click_unresolved_low_util_failures": sum("post_click_unresolved_low_util_families_below_0_85" in c["fail_reasons"] for c in cases),
        "accepted_green_unresolved_overprovided_failures": sum("post_click_accepted_green_has_unresolved_overprovided_families" in c["fail_reasons"] for c in cases),
        "accepted_green_shear_under_0_70_no_blocker_failures": sum("accepted_green_with_shear_util_below_0_70_without_blocker" in c["fail_reasons"] for c in cases),
        "accepted_green_shear_under_0_85_no_blocker_failures": sum("accepted_green_with_shear_util_below_0_85_without_blocker" in c["fail_reasons"] for c in cases),
        "requires_primary_payload_binding_match": True,
        "requires_primary_payload_update_match": True,
        "payload_candidate_binding_failures": sum("primary_payload_candidate_binding_mismatch" in c["fail_reasons"] for c in cases),
        "payload_update_binding_failures": sum("primary_payload_update_binding_mismatch" in c["fail_reasons"] for c in cases),
        "legacy_fallback_primary_apply_failures": sum("primary_click_used_legacy_fallback" in c["fail_reasons"] for c in cases),
        "stale_apply_payload_failures": sum("applied_stale_candidate_keys_not_in_visible_updates" in c["fail_reasons"] or "stale_apply_payload_blocked" in c["fail_reasons"] for c in cases),
        "post_click_new_failure_failures": sum(any(str(r).startswith("post_click_") and str(r).endswith("_failed") for r in c["fail_reasons"]) for c in cases),
        "incoherent_candidate_failures": sum("incoherent_cleanup_geometry_increase" in c["fail_reasons"] for c in cases),
    }
    artifact = {
        "verdict": "PASS" if fail_count == 0 and returncode == 0 else "FAIL",
        "summary": summary,
        "real_user_artifact": real_user.get("_artifact_path"),
        "real_user_returncode": returncode,
        "real_user_stdout_tail": "\n".join(stdout.splitlines()[-20:]),
        "real_user_stderr_tail": "\n".join(stderr.splitlines()[-20:]),
        "cases": cases,
    }
    out_dir = REPO / "artifacts" / "verification" / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"local_cleanup_apply_effectiveness_ladder_{TIMESTAMP}.json"
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": artifact["verdict"], "output": str(out), **summary}, indent=2))
    return 0 if artifact["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
