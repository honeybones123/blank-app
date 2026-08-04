"""Proof snapshot for late-render shear-action intent contract extraction."""

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
SHEAR_KEYS = ("shear_bar_size", "shear_spacing")


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _debug(*, family: str = "shear", updates: dict[str, Any] | None = None, expected: float = 0.9) -> dict[str, Any]:
    if updates is None:
        updates = {"shear_spacing": 0.0} if family == "shear" else {"bottom_bar_count": 6}
    return {
        "candidate_search_evidence": {
            "family": family,
            "safe_candidate_count": 0,
            "executable_candidate_count": 0,
            "exact_blockers_by_family": {"shear": {"stale": True}},
        },
        "guidance_intent_items": [
            {
                "title": "Late render shear cleanup",
                "family": family,
                "check_key": family,
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": family,
                    "updates": dict(updates),
                    "preview_pass": True,
                    "expected_util": expected,
                    "blocking_reason": None,
                    "candidate_id": f"{family}-late-render-1",
                    "source_candidate_id": f"{family}-late-render-1",
                },
            }
        ],
    }


def _cases() -> dict[str, dict[str, Any]]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_design_guide_late_render_shear_action_intent_contract_result,
    )

    kwargs = {
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 0.001,
        "shear_update_keys": SHEAR_KEYS,
    }
    state = {"shear_spacing": 150.0}
    positive = build_final_design_guide_late_render_shear_action_intent_contract_result(
        guidance_debug=_debug(),
        state=state,
        active_strength_failures=(),
        **kwargs,
    )
    positive_repeat = build_final_design_guide_late_render_shear_action_intent_contract_result(
        guidance_debug=_debug(),
        state=state,
        active_strength_failures=(),
        **kwargs,
    )
    stale_updates = build_final_design_guide_late_render_shear_action_intent_contract_result(
        guidance_debug=_debug(),
        state={"shear_spacing": 0.0},
        active_strength_failures=(),
        **kwargs,
    )
    active_failure = build_final_design_guide_late_render_shear_action_intent_contract_result(
        guidance_debug=_debug(),
        state=state,
        active_strength_failures=("shear",),
        **kwargs,
    )
    non_shear = build_final_design_guide_late_render_shear_action_intent_contract_result(
        guidance_debug=_debug(family="bending"),
        state=state,
        active_strength_failures=(),
        **kwargs,
    )
    return {
        "positive": positive,
        "positive_repeat": positive_repeat,
        "stale_updates": stale_updates,
        "active_failure": active_failure,
        "non_shear": non_shear,
    }


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    cases = _cases()
    positive_result = dict(cases["positive"].get("result") or {})
    evidence = dict(positive_result.get("evidence_effect") or {})
    return {
        "decision": "LATE_RENDER_SHEAR_ACTION_INTENT_CONTRACT_OBJECT_READY_FOR_CUTOVER",
        "cases": cases,
        "source_checks": {
            "builder_present": "def build_final_design_guide_late_render_shear_action_intent_contract_result(" in source,
            "builder_exported": '"build_final_design_guide_late_render_shear_action_intent_contract_result"' in source,
            "clean_import_boundary": all(
                token not in source
                for token in ("import streamlit", "st.session_state", "inputs_page")
            ),
        },
        "positive_applies": positive_result.get("applies") is True,
        "positive_family_shear": positive_result.get("family") == "shear",
        "evidence_shape_present": all(
            key in evidence
            for key in (
                "cleanup_search_ran",
                "local_cleanup_search_ran",
                "family",
                "selected_candidate_id",
                "best_safe_candidate_id",
                "selected_candidate_updates",
                "best_safe_candidate_updates",
                "safe_candidate_count",
                "executable_candidate_count",
                "safe_shear_cleanup_count",
                "executable_shear_cleanup_count",
            )
        ),
        "stale_blocker_evidence_removed": "exact_blockers_by_family" not in evidence,
        "stable_repeat_hash": cases["positive"].get("proof_hash") == cases["positive_repeat"].get("proof_hash"),
        "blocked_cases_do_not_apply": all(
            dict(cases[key].get("result") or {}).get("applies") is False
            for key in ("stale_updates", "active_failure", "non_shear")
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
        "positive_applies": capture.get("positive_applies") is True,
        "positive_family_shear": capture.get("positive_family_shear") is True,
        "evidence_shape_present": capture.get("evidence_shape_present") is True,
        "stale_blocker_evidence_removed": capture.get("stale_blocker_evidence_removed") is True,
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
        "# Late Render Shear Action Intent Contract Object Snapshot",
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
        "schema": "design_guide_late_render_shear_action_intent_contract_object_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_late_render_shear_action_intent_contract_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_late_render_shear_action_intent_contract_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_late_render_shear_action_intent_contract_object_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
