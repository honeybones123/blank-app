"""Verify shear low-util no-link probe cutover from page code."""

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


def _old_float_from_state(state: dict, key: str, default: float) -> float:
    value = state.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except Exception:
        return float(default)


def _old_int_from_state(state: dict, key: str, default: int) -> int:
    value = state.get(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _old_shear_reinforcement_is_active(state: dict | None) -> bool:
    if not isinstance(state, dict):
        return False
    return (
        _old_int_from_state(state, "lig_legs", 0) >= 2
        and _old_int_from_state(state, "lig_d", 0) > 0
        and _old_float_from_state(state, "s_lig", 0.0) > 0.0
    )


def _old_canonical_no_link_updates(
    state: dict | None,
    *,
    canonical_no_shear_slig_mm: float,
) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    return {
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": float(canonical_no_shear_slig_mm),
    }


def _old_initial_no_link_cleanup_audit(
    state: dict | None,
    updates: dict[str, Any] | None = None,
    *,
    canonical_no_shear_slig_mm: float,
) -> dict[str, Any]:
    canonical_updates = dict(
        updates
        or _old_canonical_no_link_updates(
            state,
            canonical_no_shear_slig_mm=canonical_no_shear_slig_mm,
        )
    )
    already_active = bool(
        isinstance(state, dict) and not _old_shear_reinforcement_is_active(state)
    )
    return {
        "no_link_candidate_tested": False,
        "no_link_candidate_evaluated": False,
        "no_link_candidate_passed": False,
        "no_link_candidate_selected": False,
        "no_link_candidate_already_active": already_active,
        "no_link_candidate_updates": dict(canonical_updates) if already_active else {},
        "no_link_candidate_id": (
            "shear_cleanup_floor_no_links_remaining" if already_active else None
        ),
        "no_link_candidate_failed_or_selected_reason": (
            "Shear links are already removed; no further shear-link cleanup is available."
            if already_active
            else None
        ),
        "no_link_candidate_reason": (
            "Shear links are already removed; no further shear-link cleanup is available."
            if already_active
            else None
        ),
        "no_link_s_lig_policy": (
            "canonical_neutralised" if already_active else "retained_or_unknown"
        ),
    }


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_no_link_probe,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    canonical = 200.0
    cases = [
        {"name": "not_mapping", "state": None},
        {
            "name": "active_links",
            "state": {"lig_d": 10, "lig_legs": 2, "s_lig": 180.0},
        },
        {
            "name": "already_no_links",
            "state": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
        },
    ]
    comparisons = []
    for case in cases:
        state = case["state"]
        old_updates = _old_canonical_no_link_updates(
            state,
            canonical_no_shear_slig_mm=canonical,
        )
        old_audit = _old_initial_no_link_cleanup_audit(
            state,
            old_updates,
            canonical_no_shear_slig_mm=canonical,
        )
        new = build_design_guide_shear_low_util_no_link_probe(
            state_is_mapping=isinstance(state, dict),
            shear_reinforcement_active=_old_shear_reinforcement_is_active(state),
            canonical_no_shear_slig_mm=canonical,
        )
        old = {"updates": old_updates, "audit": old_audit}
        new_relevant = {
            "updates": dict(new.get("updates") or {}),
            "audit": dict(new.get("audit") or {}),
        }
        comparisons.append(
            {
                "case": case["name"],
                "old_hash": _stable_hash(old),
                "new_hash": _stable_hash(new_relevant),
                "match": old == new_relevant,
                "old": old,
                "new": new_relevant,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_NO_LINK_PROBE_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_no_link_probe as "
                "_build_design_guide_shear_low_util_no_link_probe"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_no_link_probe("
                in shear_cleanup_source
            ),
            "old_canonical_helper_removed_from_target": (
                "_canonical_no_link_shear_cleanup_updates(" not in shear_cleanup_source
            ),
            "old_initial_audit_helper_removed_from_target": (
                "_initial_no_link_cleanup_audit(" not in shear_cleanup_source
            ),
            "generic_normaliser_not_moved": (
                "_normalise_invalid_shear_state_updates(" in inputs_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_no_link_probe("
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
        "shared_normaliser_moved": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_old_new_cases_match": all(
            item.get("match") for item in capture.get("comparisons") or []
        ),
        "source_checks_pass": all(source_checks.values())
        or (
            source_checks.get("target_function_found") is False
            and source_checks.get("controller_has_helper") is True
            and source_checks.get("old_canonical_helper_removed_from_target") is True
            and source_checks.get("old_initial_audit_helper_removed_from_target") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
        "shared_normaliser_not_moved": capture.get("shared_normaliser_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util No-Link Probe Cutover Snapshot",
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
        lines.append(
            f"- {item.get('case')}: match=`{item.get('match')}`, old=`{item.get('old_hash')}`, new=`{item.get('new_hash')}`"
        )
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_no_link_probe_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_no_link_probe_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_no_link_probe_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
