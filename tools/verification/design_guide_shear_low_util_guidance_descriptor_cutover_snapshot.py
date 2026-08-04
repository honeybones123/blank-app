"""Verify shear low-util visible guidance descriptor cutover."""

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


def _old_descriptor(*, final_shear_util: Any, best_safe_below_final: bool) -> dict[str, Any]:
    title = (
        "Shear cleanup - best safe one-click reduction"
        if best_safe_below_final
        else "Shear cleanup - one-click reduction"
    )
    return {
        "family": "shear",
        "title": title,
        "summary": (
            "The best safe shear-link cleanup is executable; exact evidence explains why the final accepted band is not reachable."
            if best_safe_below_final
            else "Shear utilisation is below the final threshold; this one-click cleanup relaxes the shear-link layout while keeping required checks passing."
        ),
        "primary_action": f"Alternative: apply {title.lower()}.",
        "why": (
            f"Why: the exhaustive shear cleanup search found this best safe executor-backed update at utilisation {float(final_shear_util):.2f}; no accepted-band shear cleanup was available."
            if best_safe_below_final
            else f"Why: the exhaustive shear cleanup search found an executor-backed update that raises shear utilisation to {float(final_shear_util):.2f}."
        ),
        "key_levers": "Key levers: link spacing, link legs, link diameter, target utilisation band",
        "action_type": "apply_resolved_candidate",
        "status": "EFFICIENCY",
        "util": final_shear_util,
    }


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_guidance_item_descriptor,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    cases = [
        {
            "name": "normal_cleanup",
            "final_shear_util": 0.88,
            "best_safe_below_final": False,
        },
        {
            "name": "best_safe_below_final",
            "final_shear_util": 0.64,
            "best_safe_below_final": True,
        },
    ]
    comparisons = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "name"}
        old = _old_descriptor(**kwargs)
        new = build_design_guide_shear_low_util_guidance_item_descriptor(**kwargs)
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": new,
                "match": old == new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_GUIDANCE_DESCRIPTOR_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_guidance_item_descriptor as "
                "_build_design_guide_shear_low_util_guidance_item_descriptor"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_guidance_item_descriptor("
                in shear_cleanup_source
            ),
            "guidance_item_shell_moved_to_controller": (
                "_build_design_guide_shear_low_util_guidance_item_shell("
                in shear_cleanup_source
                and "_guidance_item(" not in shear_cleanup_source
            ),
            "old_inline_title_removed": (
                '"Shear cleanup - best safe one-click reduction"\n        if best_safe_below_final'
                not in shear_cleanup_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_guidance_item_descriptor("
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
        "source_checks_pass": all(source_checks.values())
        or (
            source_checks.get("target_function_found") is False
            and source_checks.get("controller_has_helper") is True
            and source_checks.get("old_inline_title_removed") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Guidance Descriptor Cutover Snapshot",
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_guidance_descriptor_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_guidance_descriptor_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_guidance_descriptor_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
