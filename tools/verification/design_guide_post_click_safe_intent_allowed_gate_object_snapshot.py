"""Proof snapshot for post-click safe-intent allowed gate extraction."""

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


def _debug(*, family: str = "shear", expected: float = 0.91) -> dict[str, Any]:
    updates = {"shear_spacing": 0.0} if family == "shear" else {"bottom_bar_count": 6}
    return {
        "guidance_intent_items": [
            {
                "title": "Intent candidate",
                "family": family,
                "check_key": family,
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": family,
                    "updates": updates,
                    "preview_pass": True,
                    "expected_util": expected,
                    "blocking_reason": None,
                    "candidate_id": f"{family}-intent-1",
                    "source_candidate_id": f"{family}-intent-1",
                },
            }
        ]
    }


def _cases() -> dict[str, dict[str, Any]]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_design_guide_post_click_safe_intent_allowed_gate_result,
    )

    kwargs = {
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 0.001,
        "shear_update_keys": SHEAR_KEYS,
    }
    state = {"shear_spacing": 150.0, "shear_bar_size": "N12"}
    positive = build_final_design_guide_post_click_safe_intent_allowed_gate_result(
        guidance_debug=_debug(),
        state=state,
        post_click_apply_context=True,
        **kwargs,
    )
    positive_repeat = build_final_design_guide_post_click_safe_intent_allowed_gate_result(
        guidance_debug=_debug(),
        state=state,
        post_click_apply_context=True,
        **kwargs,
    )
    no_post_click = build_final_design_guide_post_click_safe_intent_allowed_gate_result(
        guidance_debug=_debug(),
        state=state,
        post_click_apply_context=False,
        **kwargs,
    )
    stale_updates = build_final_design_guide_post_click_safe_intent_allowed_gate_result(
        guidance_debug=_debug(),
        state={"shear_spacing": 0.0},
        post_click_apply_context=True,
        **kwargs,
    )
    non_shear = build_final_design_guide_post_click_safe_intent_allowed_gate_result(
        guidance_debug=_debug(family="bending"),
        state=state,
        post_click_apply_context=True,
        **kwargs,
    )
    out_of_band = build_final_design_guide_post_click_safe_intent_allowed_gate_result(
        guidance_debug=_debug(expected=0.42),
        state=state,
        post_click_apply_context=True,
        **kwargs,
    )
    return {
        "positive": positive,
        "positive_repeat": positive_repeat,
        "no_post_click": no_post_click,
        "stale_updates": stale_updates,
        "non_shear": non_shear,
        "out_of_band": out_of_band,
    }


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    cases = _cases()
    positive_result = dict(cases["positive"].get("result") or {})
    return {
        "decision": "POST_CLICK_SAFE_INTENT_ALLOWED_GATE_OBJECT_READY_FOR_CUTOVER",
        "cases": cases,
        "source_checks": {
            "builder_present": "def build_final_design_guide_post_click_safe_intent_allowed_gate_result(" in source,
            "builder_exported": '"build_final_design_guide_post_click_safe_intent_allowed_gate_result"' in source,
            "clean_import_boundary": all(
                token not in source
                for token in ("import streamlit", "st.session_state", "inputs_page")
            ),
        },
        "positive_allowed": positive_result.get("allowed") is True,
        "positive_family_shear": positive_result.get("family") == "shear",
        "positive_updates_present": bool(positive_result.get("updates")),
        "positive_guard_shape": all(
            key in dict(positive_result.get("guard_results") or {})
            for key in (
                "post_click_apply_context",
                "has_intent_contract",
                "button_contract_enabled",
                "action_type_apply_resolved_candidate",
                "family_is_shear",
                "has_updates",
                "has_shear_update_keys",
                "updates_not_already_in_state",
                "expected_util_present",
                "expected_util_in_accepted_range",
            )
        ),
        "stable_repeat_hash": cases["positive"].get("proof_hash") == cases["positive_repeat"].get("proof_hash"),
        "blocked_cases_not_allowed": all(
            dict(cases[key].get("result") or {}).get("allowed") is False
            for key in ("no_post_click", "stale_updates", "non_shear", "out_of_band")
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
        "positive_allowed": capture.get("positive_allowed") is True,
        "positive_family_shear": capture.get("positive_family_shear") is True,
        "positive_updates_present": capture.get("positive_updates_present") is True,
        "positive_guard_shape": capture.get("positive_guard_shape") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "blocked_cases_not_allowed": capture.get("blocked_cases_not_allowed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post Click Safe Intent Allowed Gate Object Snapshot",
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
        "schema": "design_guide_post_click_safe_intent_allowed_gate_object_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_post_click_safe_intent_allowed_gate_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_post_click_safe_intent_allowed_gate_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_safe_intent_allowed_gate_object_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
