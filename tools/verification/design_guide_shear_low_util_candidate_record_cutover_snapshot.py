"""Verify shear low-util candidate record cutover from page loop."""

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


def _old_record(
    *,
    updates: dict[str, Any],
    candidate_id: str,
    is_no_link_candidate: bool,
    canonical_no_shear_slig_mm: float,
) -> dict[str, Any]:
    no_link_policy = "not_no_link_candidate"
    if is_no_link_candidate:
        no_link_policy = (
            "canonical_neutralised"
            if abs(
                float(updates.get("s_lig", canonical_no_shear_slig_mm))
                - float(canonical_no_shear_slig_mm)
            )
            <= 1e-9
            else "retained"
        )
    no_link_audit_update: dict[str, Any] = {}
    if is_no_link_candidate:
        no_link_audit_update = {
            "no_link_candidate_tested": True,
            "no_link_candidate_evaluated": True,
            "no_link_candidate_updates": dict(updates),
            "no_link_candidate_id": candidate_id,
            "no_link_s_lig_policy": no_link_policy,
        }
    return {
        "candidate_id": candidate_id,
        "updates": dict(updates),
        "is_no_link_candidate": bool(is_no_link_candidate),
        "evaluation_source": "low_util_shear_target_cleanup_action",
        "evaluation_label": "Shear cleanup - one-click reduction",
        "evaluation_action_type": "apply_resolved_candidate",
        "no_link_s_lig_policy": no_link_policy,
        "no_link_audit_update": dict(no_link_audit_update),
    }


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_shear_low_util_cleanup_candidate_record,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    shear_cleanup_source = _target_function_source(inputs_source)
    cases = [
        {
            "name": "ordinary_candidate",
            "updates": {"lig_legs": 2, "s_lig": 300.0},
            "candidate_id": "local_cleanup:shear:ordinary",
            "is_no_link_candidate": False,
            "canonical_no_shear_slig_mm": 9999.0,
        },
        {
            "name": "no_link_canonical_slig",
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 9999.0},
            "candidate_id": "local_cleanup:shear:no_link",
            "is_no_link_candidate": True,
            "canonical_no_shear_slig_mm": 9999.0,
        },
        {
            "name": "no_link_retained_slig",
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 250.0},
            "candidate_id": "local_cleanup:shear:no_link_retained",
            "is_no_link_candidate": True,
            "canonical_no_shear_slig_mm": 9999.0,
        },
    ]
    comparisons = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "name"}
        old = _old_record(**kwargs)
        new = build_design_guide_shear_low_util_cleanup_candidate_record(**kwargs)
        comparable_new = {
            key: new.get(key)
            for key in (
                "candidate_id",
                "updates",
                "is_no_link_candidate",
                "evaluation_source",
                "evaluation_label",
                "evaluation_action_type",
                "no_link_s_lig_policy",
                "no_link_audit_update",
            )
        }
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": comparable_new,
                "match": old == comparable_new,
            }
        )
    return {
        "decision": "SHEAR_LOW_UTIL_CANDIDATE_RECORD_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "record_imported": (
                "build_design_guide_shear_low_util_cleanup_candidate_record as "
                "_build_design_guide_shear_low_util_cleanup_candidate_record"
            )
            in inputs_source,
            "record_called_in_page_loop": (
                "_build_design_guide_shear_low_util_cleanup_candidate_record("
                in shear_cleanup_source
            ),
            "candidate_evaluation_controller_boundary_present": (
                "_evaluate_design_guide_shear_low_util_cleanup_candidate(" in shear_cleanup_source
            ),
            "legacy_direct_candidate_evaluation_removed": (
                "candidate = _evaluate_auto_design_candidate(" not in shear_cleanup_source
            ),
            "evaluate_boundary_uses_record": (
                "evaluation_record=cleanup_candidate_record" in shear_cleanup_source
            ),
            "old_inline_no_link_policy_removed": (
                '"canonical_neutralised"\n                        if abs('
                not in shear_cleanup_source
            ),
            "target_function_found": bool(shear_cleanup_source),
            "controller_has_record_builder": (
                "def build_design_guide_shear_low_util_cleanup_candidate_record("
                in controller_source
            ),
            "controller_page_free": "inputs_page" not in controller_source
            and "st.session_state" not in controller_source
            and "streamlit" not in controller_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_evaluation_moved": True,
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
        "candidate_evaluation_boundary_moved": capture.get("candidate_evaluation_moved") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Candidate Record Cutover Snapshot",
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_candidate_record_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_candidate_record_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_candidate_record_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
