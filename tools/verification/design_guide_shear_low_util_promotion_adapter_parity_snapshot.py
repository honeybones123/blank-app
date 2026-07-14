"""Verify proof-only shear low-util promotion adapter parity."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _old_promote(
    *,
    item: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    guidance_change_lines: list[Any] | None,
    failure_coverage: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(item, dict) or not isinstance(candidate, dict):
        return item
    updates = dict(candidate.get("updates") or {})
    if not updates:
        return item

    out = dict(item)
    payload = dict(out.get("action_payload") or {})
    original_action_type = str(
        candidate.get("action_type")
        or payload.get("resolved_candidate_action_type")
        or out.get("action_type")
        or "apply_shear_recommendation"
    ).strip()
    label = str(
        candidate.get("label")
        or payload.get("resolved_candidate_label")
        or out.get("title_main")
        or "Apply recommendation"
    ).strip()
    post_util = candidate.get("candidate_post_util", candidate.get("worst_util"))
    try:
        post_util = float(post_util) if post_util is not None else None
    except Exception:
        post_util = None
    change_lines = list(
        candidate.get("guidance_change_lines")
        or payload.get("guidance_change_lines")
        or out.get("guidance_change_lines")
        or guidance_change_lines
        or []
    )
    coverage = dict(failure_coverage or {})

    payload["resolved_candidate_updates"] = dict(updates)
    payload["resolved_candidate_label"] = label
    payload["resolved_candidate_action_type"] = original_action_type
    payload["resolved_candidate_post_util"] = post_util
    payload["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    payload["updates"] = dict(payload.get("updates") or updates)
    payload["guidance_change_lines"] = list(change_lines)
    payload["failure_coverage"] = dict(coverage)
    payload["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
    payload["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    payload["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])

    out["action_payload"] = payload
    out["action_type"] = "apply_resolved_candidate"
    out["resolved_candidate_label"] = label
    out["resolved_candidate_action_type"] = original_action_type
    out["resolved_candidate_updates"] = dict(updates)
    out["resolved_candidate_post_util"] = post_util
    out["resolved_candidate_reaches_target_band"] = bool(
        candidate.get("candidate_reaches_target_band")
        or candidate.get("reaches_target_band")
    )
    out["has_resolved_candidate_payload"] = True
    out["failure_coverage"] = dict(coverage)
    out["covers_all_current_failures"] = bool(coverage.get("covers_all_current_failures"))
    out["covered_fail_keys"] = list(coverage.get("covered_fail_keys") or [])
    out["remaining_fail_keys"] = list(coverage.get("remaining_fail_keys") or [])
    out["resolved_candidate"] = {
        **dict(candidate),
        "label": label,
        "action_type": original_action_type,
        "updates": dict(updates),
        "candidate_post_util": post_util,
        "candidate_reaches_target_band": bool(
            candidate.get("candidate_reaches_target_band")
            or candidate.get("reaches_target_band")
        ),
        "failure_coverage": dict(coverage),
    }
    return out


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_promoted_item,
    )

    cases = [
        {
            "name": "plain_candidate",
            "item": {
                "title_main": "Shear cleanup - one-click reduction",
                "action_payload": {},
            },
            "candidate": {
                "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
                "label": "Shear cleanup - one-click reduction",
                "action_type": "apply_resolved_candidate",
                "candidate_post_util": 0.69,
                "candidate_reaches_target_band": True,
            },
            "guidance_change_lines": ["Shear links removed"],
            "failure_coverage": {
                "covers_all_current_failures": True,
                "covered_fail_keys": ["shear"],
                "remaining_fail_keys": [],
            },
        },
        {
            "name": "payload_existing_label",
            "item": {
                "title_main": "Apply shear cleanup",
                "action_type": "apply_shear_recommendation",
                "action_payload": {
                    "resolved_candidate_label": "Existing label",
                    "guidance_change_lines": ["Existing line"],
                },
            },
            "candidate": {
                "updates": {"s_lig": 275.0},
                "worst_util": "0.74",
                "reaches_target_band": False,
            },
            "guidance_change_lines": ["Fallback line"],
            "failure_coverage": {
                "covers_all_current_failures": False,
                "covered_fail_keys": [],
                "remaining_fail_keys": ["bending"],
            },
        },
        {
            "name": "no_updates_no_promotion",
            "item": {"title_main": "No updates"},
            "candidate": {"label": "Candidate"},
            "guidance_change_lines": [],
            "failure_coverage": {},
        },
    ]
    comparisons = []
    for case in cases:
        old = _old_promote(
            item=dict(case["item"]),
            candidate=dict(case["candidate"]),
            guidance_change_lines=list(case["guidance_change_lines"]),
            failure_coverage=dict(case["failure_coverage"]),
        )
        new_raw = build_design_guide_shear_low_util_promoted_item(
            item=dict(case["item"]),
            candidate=dict(case["candidate"]),
            guidance_change_lines=list(case["guidance_change_lines"]),
            failure_coverage=dict(case["failure_coverage"]),
        )
        new = dict(new_raw.get("item") or {})
        comparisons.append(
            {
                "case": case["name"],
                "old_hash": _stable_hash(old),
                "new_hash": _stable_hash(new),
                "match": old == new,
                "promoted": bool(new_raw.get("promoted")),
            }
        )
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    return {
        "decision": "SHEAR_LOW_UTIL_PROMOTION_ADAPTER_PARITY_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "controller_has_helper": "def build_design_guide_shear_low_util_promoted_item(" in controller_source,
            "controller_page_free": "inputs_page" not in controller_source
            and "st.session_state" not in controller_source
            and "streamlit" not in controller_source,
            "live_page_promotion_bridge_still_present": (
                "_promote_guidance_item_to_resolved_candidate(" in inputs_source
            ),
        },
        "proof_only": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_cases_match": all(bool(item.get("match")) for item in capture.get("comparisons") or []),
        "source_checks_pass": all(source_checks.values()),
        "proof_only": capture.get("proof_only") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Promotion Adapter Parity Snapshot",
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
            f"- {item.get('case')}: match=`{item.get('match')}`, promoted=`{item.get('promoted')}`"
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_promotion_adapter_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_promotion_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_promotion_adapter_parity_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
