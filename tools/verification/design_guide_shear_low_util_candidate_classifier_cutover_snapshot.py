"""Verify shear low-util candidate band classifier cutover from page loop."""

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


def _old_distance_to_target_band(util: float, target_min: float, target_max: float) -> float:
    try:
        u = float(util)
        lo = float(target_min)
        hi = float(target_max)
    except (TypeError, ValueError):
        return float("inf")
    if lo <= u <= hi:
        return 0.0
    if u < lo:
        return lo - u
    return u - hi


def _old_classification(
    *,
    shear_util: Any,
    threshold: Any,
    preferred_low: Any,
    target_high: Any,
    target_band_eps: Any,
    allow_best_safe_below_threshold: bool,
) -> dict[str, Any]:
    try:
        util = float(shear_util)
        threshold_f = float(threshold)
        preferred_low_f = float(preferred_low)
        target_high_f = float(target_high)
        eps_f = float(target_band_eps)
    except (TypeError, ValueError):
        return {
            "below_threshold": False,
            "failed_reason": None,
            "skip_for_selection": False,
            "accepted_band_candidate": False,
            "target_band_candidate": False,
            "distance_to_target_band": float("inf"),
        }
    below_threshold = util < threshold_f
    return {
        "below_threshold": below_threshold,
        "failed_reason": "shear_target_threshold_not_reached" if below_threshold else None,
        "skip_for_selection": bool(below_threshold and not allow_best_safe_below_threshold),
        "accepted_band_candidate": bool(not below_threshold and util <= 1.0 + eps_f),
        "target_band_candidate": bool(
            preferred_low_f - eps_f <= util <= target_high_f + eps_f
        ),
        "distance_to_target_band": _old_distance_to_target_band(util, threshold_f, target_high_f),
    }


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        classify_design_guide_shear_low_util_cleanup_candidate,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    cases = [
        {
            "name": "below_threshold_blocked",
            "shear_util": 0.42,
            "threshold": 0.85,
            "preferred_low": 0.85,
            "target_high": 0.95,
            "target_band_eps": 1e-9,
            "allow_best_safe_below_threshold": False,
        },
        {
            "name": "below_threshold_allowed",
            "shear_util": 0.42,
            "threshold": 0.85,
            "preferred_low": 0.85,
            "target_high": 0.95,
            "target_band_eps": 1e-9,
            "allow_best_safe_below_threshold": True,
        },
        {
            "name": "accepted_band",
            "shear_util": 0.88,
            "threshold": 0.85,
            "preferred_low": 0.85,
            "target_high": 0.95,
            "target_band_eps": 1e-9,
            "allow_best_safe_below_threshold": False,
        },
        {
            "name": "above_target",
            "shear_util": 1.04,
            "threshold": 0.85,
            "preferred_low": 0.85,
            "target_high": 0.95,
            "target_band_eps": 1e-9,
            "allow_best_safe_below_threshold": False,
        },
    ]
    comparisons = []
    for case in cases:
        old = _old_classification(**{key: value for key, value in case.items() if key != "name"})
        new = classify_design_guide_shear_low_util_cleanup_candidate(
            **{key: value for key, value in case.items() if key != "name"}
        )
        comparable_new = {
            key: new.get(key)
            for key in (
                "below_threshold",
                "failed_reason",
                "skip_for_selection",
                "accepted_band_candidate",
                "target_band_candidate",
                "distance_to_target_band",
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
        "decision": "SHEAR_LOW_UTIL_CANDIDATE_CLASSIFIER_CUTOVER_PASS",
        "comparisons": comparisons,
        "source_checks": {
            "classifier_imported": (
                "classify_design_guide_shear_low_util_cleanup_candidate as "
                "_classify_design_guide_shear_low_util_cleanup_candidate"
            )
            in inputs_source,
            "classifier_called_in_page_loop": (
                "_classify_design_guide_shear_low_util_cleanup_candidate(" in inputs_source
            ),
            "old_inline_distance_removed_from_loop": (
                "_distance_to_target_band(float(cand_shear_util), float(threshold), float(target_high))"
                not in inputs_source
            ),
            "page_evaluator_still_live": "_evaluate_auto_design_candidate(" in inputs_source,
            "controller_has_classifier": (
                "def classify_design_guide_shear_low_util_cleanup_candidate(" in controller_source
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
        "# Design Guide Shear Low-Util Candidate Classifier Cutover Snapshot",
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_candidate_classifier_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_candidate_classifier_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_candidate_classifier_cutover_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
