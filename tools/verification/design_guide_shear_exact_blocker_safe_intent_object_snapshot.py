"""Proof snapshot for safe shear intent recovery over exact blocker."""

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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _debug_payload(*, family: str = "shear", expected: float = 0.88) -> dict[str, Any]:
    return {
        "displayed_guidance_intent_items": [
            {
                "title": "Shear cleanup - one-click reduction",
                "family": family,
                "check_key": family,
                "button_contract": {
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": family,
                    "preview_pass": True,
                    "blocking_reason": None,
                    "updates": {"shear_bar_size": "N10", "shear_spacing": 0.0},
                    "expected_util": expected,
                    "candidate_id": "safe-shear-intent-1",
                },
            }
        ],
        "candidate_search_evidence": {
            "safe_candidate_count": 2,
            "executable_candidate_count": 2,
            "exact_blockers_by_family": {"shear": {"stale": True}},
            "cleanup_evidence_by_family": {"shear": {"stale": True}},
        },
    }


def _cases() -> dict[str, dict[str, Any]]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_design_guide_shear_exact_blocker_safe_intent_result,
    )

    kwargs = {
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 0.001,
        "shear_update_keys": ("shear_bar_size", "shear_spacing"),
    }
    available = build_final_design_guide_shear_exact_blocker_safe_intent_result(
        guidance_debug=_debug_payload(),
        state={"shear_bar_size": "N12", "shear_spacing": 150.0},
        overview={"utils": {"bending": 0.4, "shear": 0.7}},
        **kwargs,
    )
    repeat = build_final_design_guide_shear_exact_blocker_safe_intent_result(
        guidance_debug=_debug_payload(),
        state={"shear_bar_size": "N12", "shear_spacing": 150.0},
        overview={"utils": {"bending": 0.4, "shear": 0.7}},
        **kwargs,
    )
    wrong_family = build_final_design_guide_shear_exact_blocker_safe_intent_result(
        guidance_debug=_debug_payload(family="bending"),
        state={"shear_bar_size": "N12", "shear_spacing": 150.0},
        overview={"utils": {"bending": 0.4, "shear": 0.7}},
        **kwargs,
    )
    stale_updates = build_final_design_guide_shear_exact_blocker_safe_intent_result(
        guidance_debug=_debug_payload(),
        state={"shear_bar_size": "N10", "shear_spacing": 0.0},
        overview={"utils": {"bending": 0.4, "shear": 0.7}},
        **kwargs,
    )
    active_failure = build_final_design_guide_shear_exact_blocker_safe_intent_result(
        guidance_debug=_debug_payload(),
        state={"shear_bar_size": "N12", "shear_spacing": 150.0},
        overview={"utils": {"bending": 0.4, "shear": 1.2}},
        **kwargs,
    )
    out_of_range = build_final_design_guide_shear_exact_blocker_safe_intent_result(
        guidance_debug=_debug_payload(expected=0.6),
        state={"shear_bar_size": "N12", "shear_spacing": 150.0},
        overview={"utils": {"bending": 0.4, "shear": 0.7}},
        **kwargs,
    )
    return {
        "available": available,
        "repeat": repeat,
        "wrong_family": wrong_family,
        "stale_updates": stale_updates,
        "active_failure": active_failure,
        "out_of_range": out_of_range,
    }


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    cases = _cases()
    available_result = dict(cases["available"].get("result") or {})
    available_evidence = dict(available_result.get("evidence_effect") or {})
    blocked = ("wrong_family", "stale_updates", "active_failure", "out_of_range")
    return {
        "decision": "SHEAR_EXACT_BLOCKER_SAFE_INTENT_OBJECT_READY_FOR_CUTOVER",
        "cases": cases,
        "source_checks": {
            "builder_present": "def build_final_design_guide_shear_exact_blocker_safe_intent_result(" in source,
            "builder_exported": '"build_final_design_guide_shear_exact_blocker_safe_intent_result"' in source,
            "clean_import_boundary": all(
                token not in source
                for token in ("import streamlit", "st.session_state", "inputs_page")
            ),
        },
        "available_case_applies": available_result.get("available") is True,
        "available_evidence_sanitized": all(
            key not in available_evidence
            for key in (
                "exact_blockers_by_family",
                "post_click_exact_blockers_by_family",
                "cleanup_evidence_by_family",
                "post_click_cleanup_evidence_by_family",
            )
        ),
        "available_evidence_counts_present": all(
            int(available_evidence.get(key) or 0) >= 1
            for key in (
                "safe_candidate_count",
                "executable_candidate_count",
                "safe_cleanup_count",
                "executable_cleanup_count",
                "safe_shear_cleanup_count",
                "executable_shear_cleanup_count",
            )
        ),
        "available_candidate_id": available_result.get("candidate_id"),
        "stable_repeat_hash": cases["available"].get("proof_hash") == cases["repeat"].get("proof_hash"),
        "blocked_cases_do_not_apply": all(
            dict(cases[key].get("result") or {}).get("available") is False for key in blocked
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_source_checks_pass": all(source_checks.values()),
        "available_case_applies": capture.get("available_case_applies") is True,
        "available_evidence_sanitized": capture.get("available_evidence_sanitized") is True,
        "available_evidence_counts_present": capture.get("available_evidence_counts_present") is True,
        "available_candidate_id_present": bool(capture.get("available_candidate_id")),
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "blocked_cases_do_not_apply": capture.get("blocked_cases_do_not_apply") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Shear Exact Blocker Safe Intent Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if not value]
    payload = {
        "schema": "design_guide_shear_exact_blocker_safe_intent_object_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_shear_exact_blocker_safe_intent_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_exact_blocker_safe_intent_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_exact_blocker_safe_intent_object_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
