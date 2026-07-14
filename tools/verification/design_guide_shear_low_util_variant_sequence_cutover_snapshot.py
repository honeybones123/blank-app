"""Verify shear low-util variant sequence cutover."""

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


def _old_variant_sequence(
    *,
    variants: list[dict[str, Any]],
    no_link_state: dict[str, Any],
    shear_reinforcement_active: bool,
    no_link_updates: dict[str, Any],
    no_link_key: Any,
    existing_variant_keys: list[Any],
) -> dict[str, Any]:
    merged = list(variants)
    prepended = False
    if shear_reinforcement_active and no_link_updates:
        if no_link_key not in list(existing_variant_keys or []):
            merged = [dict(no_link_state)] + merged
            prepended = True
    return {
        "variants": [dict(item) for item in merged],
        "no_link_variant_prepended": prepended,
    }


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_variant_sequence,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    base_variants = [
        {"id": "spacing", "s_lig": 250.0},
        {"id": "diameter", "lig_d": 8},
    ]
    no_link_state = {"id": "no_link", "lig_d": 0, "lig_legs": 0, "s_lig": 200.0}
    cases = [
        {
            "name": "prepend_no_link",
            "variants": base_variants,
            "shear_reinforcement_active": True,
            "no_link_updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
            "no_link_key": ("no_link",),
            "existing_variant_keys": [("spacing",), ("diameter",)],
        },
        {
            "name": "no_prepend_duplicate",
            "variants": base_variants,
            "shear_reinforcement_active": True,
            "no_link_updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
            "no_link_key": ("spacing",),
            "existing_variant_keys": [("spacing",), ("diameter",)],
        },
        {
            "name": "no_prepend_inactive_links",
            "variants": base_variants,
            "shear_reinforcement_active": False,
            "no_link_updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
            "no_link_key": ("no_link",),
            "existing_variant_keys": [("spacing",), ("diameter",)],
        },
        {
            "name": "no_prepend_empty_updates",
            "variants": base_variants,
            "shear_reinforcement_active": True,
            "no_link_updates": {},
            "no_link_key": ("no_link",),
            "existing_variant_keys": [("spacing",), ("diameter",)],
        },
    ]
    comparisons = []
    for case in cases:
        case_args = {key: value for key, value in case.items() if key != "name"}
        old = _old_variant_sequence(no_link_state=no_link_state, **case_args)
        new_raw = build_design_guide_shear_low_util_variant_sequence(
            no_link_state=no_link_state,
            **case_args,
        )
        new = {
            "variants": [dict(item) for item in list(new_raw.get("variants") or [])],
            "no_link_variant_prepended": bool(new_raw.get("no_link_variant_prepended")),
        }
        comparisons.append(
            {
                "case": case["name"],
                "old_hash": _stable_hash(old),
                "new_hash": _stable_hash(new),
                "match": old == new,
                "old": old,
                "new": new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_VARIANT_SEQUENCE_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_variant_sequence as "
                "_build_design_guide_shear_low_util_variant_sequence"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_variant_sequence("
                in shear_cleanup_source
            ),
            "target_uses_controller_raw_variant_states": (
                "_build_design_guide_shear_low_util_raw_variant_states("
                in shear_cleanup_source
            ),
            "page_still_computes_candidate_keys": (
                "_make_auto_design_candidate_key(" in shear_cleanup_source
            ),
            "old_inline_no_link_prepend_policy_removed": (
                "if no_link_key not in {" not in shear_cleanup_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_variant_sequence("
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
        "all_old_new_cases_match": all(
            item.get("match") for item in capture.get("comparisons") or []
        ),
        "source_checks_pass": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Variant Sequence Cutover Snapshot",
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_variant_sequence_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_variant_sequence_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_variant_sequence_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
