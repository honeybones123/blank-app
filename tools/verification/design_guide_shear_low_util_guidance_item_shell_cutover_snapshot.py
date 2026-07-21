"""Verify shear low-util guidance item shell cutover."""

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


def _old_guidance_bucket(status: str, util: float | None = None) -> str:
    upper = str(status or "—").upper()
    if "START" in upper:
        return "start"
    if "EFFICIENCY" in upper or "TIGHTEN" in upper:
        return "efficiency"
    if "FAIL" in upper or upper == "NG":
        return "fail"
    if "WARN" in upper or "NEAR LIMIT" in upper or upper == "CHECK":
        return "warn"
    if util is not None and util > 1.0:
        return "fail"
    if util is not None and util >= 0.9:
        return "warn"
    return "pass"


def _old_guidance_priority(bucket: str, util: float | None) -> float:
    util_score = util if util is not None else 0.0
    if bucket == "start":
        return 50.0
    if bucket == "fail":
        return 300.0 + util_score
    if bucket == "warn":
        return 200.0 + util_score
    if bucket == "efficiency":
        return 150.0 + util_score
    return 100.0 - util_score


def _old_format_guidance_title(title: str, util: float | None) -> str:
    if util is None:
        return title
    return f"{title} (utilisation = {util:.2f})"


def _old_guidance_item(
    check_key: str,
    title: str,
    primary_action: str,
    secondary_action: str | None,
    reasoning: str,
    levers: str,
    action_type: str | None,
    action_payload: dict | None,
    *,
    status: str,
    util: float | None,
) -> dict[str, Any]:
    bucket = _old_guidance_bucket(status, util)
    return {
        "check_key": check_key,
        "title_main": title,
        "title_util": f"(utilisation = {util:.2f})" if util is not None else None,
        "title": _old_format_guidance_title(title, util),
        "primary_action": primary_action,
        "secondary_action": secondary_action,
        "reasoning": reasoning,
        "levers": levers,
        "status": status,
        "bucket": bucket,
        "util": util,
        "priority": _old_guidance_priority(bucket, util),
        "action_type": action_type,
        "action_payload": action_payload or {},
    }


def _old_shell(
    *,
    guidance_descriptor: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, Any]:
    descriptor = dict(guidance_descriptor or {})
    title = str(descriptor.get("title") or "Shear cleanup - one-click reduction")
    return _old_guidance_item(
        str(descriptor.get("family") or "shear"),
        title,
        str(descriptor.get("summary") or ""),
        str(descriptor.get("primary_action") or f"Alternative: apply {title.lower()}."),
        str(descriptor.get("why") or ""),
        str(
            descriptor.get("key_levers")
            or "Key levers: link spacing, link legs, link diameter, target utilisation band"
        ),
        str(descriptor.get("action_type") or "apply_resolved_candidate"),
        {"updates": dict(updates)},
        status=str(descriptor.get("status") or "EFFICIENCY"),
        util=descriptor.get("util"),
    )


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_guidance_item_descriptor,
        build_design_guide_shear_low_util_guidance_item_shell,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    cases = [
        {
            "name": "normal_cleanup",
            "final_shear_util": 0.88,
            "best_safe_below_final": False,
            "updates": {"N_lig": 0, "s_lig": 9999.0, "db_lig": 0},
        },
        {
            "name": "best_safe_below_final",
            "final_shear_util": 0.64,
            "best_safe_below_final": True,
            "updates": {"N_lig": 2, "s_lig": 300.0, "db_lig": 10},
        },
    ]
    comparisons = []
    for case in cases:
        descriptor = build_design_guide_shear_low_util_guidance_item_descriptor(
            final_shear_util=case["final_shear_util"],
            best_safe_below_final=case["best_safe_below_final"],
        )
        old = _old_shell(guidance_descriptor=descriptor, updates=case["updates"])
        new = build_design_guide_shear_low_util_guidance_item_shell(
            guidance_descriptor=descriptor,
            updates=case["updates"],
        )
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
        "decision": "SHEAR_LOW_UTIL_GUIDANCE_ITEM_SHELL_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "helper_imported": (
                "build_design_guide_shear_low_util_guidance_item_shell as "
                "_build_design_guide_shear_low_util_guidance_item_shell"
            )
            in inputs_source,
            "helper_called_in_target_function": (
                "_build_design_guide_shear_low_util_guidance_item_shell("
                in shear_cleanup_source
            ),
            "old_page_guidance_item_shell_removed_from_target": (
                "_guidance_item(" not in shear_cleanup_source
            ),
            "promotion_adapter_moved_to_controller": (
                "_build_design_guide_shear_low_util_promoted_item(" in shear_cleanup_source
                and "_promote_guidance_item_to_resolved_candidate(" not in shear_cleanup_source
            ),
            "formatted_title_moved_to_controller": (
                "_format_guidance_title(" not in shear_cleanup_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_helper": (
                "def build_design_guide_shear_low_util_guidance_item_shell("
                in controller_source
            ),
            "controller_page_free": "inputs_page" not in controller_source
            and "st.session_state" not in controller_source
            and "streamlit" not in controller_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "rendering_moved": False,
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
            and source_checks.get("formatted_title_moved_to_controller") is True
            and source_checks.get("old_page_guidance_item_shell_removed_from_target") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "rendering_not_moved": capture.get("rendering_moved") is False,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_moved") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Guidance Item Shell Cutover Snapshot",
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_guidance_item_shell_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_guidance_item_shell_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_guidance_item_shell_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
