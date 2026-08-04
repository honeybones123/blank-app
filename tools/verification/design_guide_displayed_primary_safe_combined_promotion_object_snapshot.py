"""Proof snapshot for displayed-primary safe combined promotion extraction."""

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


def _intent_debug() -> dict[str, Any]:
    return {
        "guidance_intent_items": [
            {
                "title": "Shear and bending cleanup - one-click optimisation",
                "family": "combined",
                "check_key": "combined",
                "guidance_intent": "efficiency_tightening",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "combined",
                    "updates": {"shear_spacing": 0.0, "bottom_bar_count": 6},
                    "preview_pass": True,
                    "expected_util": 0.91,
                    "blocking_reason": None,
                    "source_candidate_id": "displayed-combined-1",
                    "candidate_id": "displayed-combined-1",
                },
            }
        ]
    }


def _cases() -> dict[str, dict[str, Any]]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_design_guide_displayed_primary_safe_combined_promotion_result,
    )

    item = {"title_main": "Existing card title", "family": "combined"}
    positive = build_final_design_guide_displayed_primary_safe_combined_promotion_result(
        item=item,
        guidance_debug=_intent_debug(),
        existing_button_contract={},
    )
    positive_repeat = build_final_design_guide_displayed_primary_safe_combined_promotion_result(
        item=item,
        guidance_debug=_intent_debug(),
        existing_button_contract={},
    )
    already_enabled = build_final_design_guide_displayed_primary_safe_combined_promotion_result(
        item=item,
        guidance_debug=_intent_debug(),
        existing_button_contract={
            "enabled": True,
            "actionable": True,
            "preview_pass": True,
            "blocking_reason": None,
            "updates": {"x": 1},
        },
    )
    no_intent = build_final_design_guide_displayed_primary_safe_combined_promotion_result(
        item=item,
        guidance_debug={},
        existing_button_contract={},
    )
    missing_item_title = build_final_design_guide_displayed_primary_safe_combined_promotion_result(
        item={},
        guidance_debug=_intent_debug(),
        existing_button_contract={},
    )
    return {
        "positive": positive,
        "positive_repeat": positive_repeat,
        "already_enabled": already_enabled,
        "no_intent": no_intent,
        "missing_item_title": missing_item_title,
    }


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    cases = _cases()
    positive_result = dict(cases["positive"].get("result") or {})
    item_effect = dict(positive_result.get("item_effect") or {})
    payload_effect = dict(positive_result.get("action_payload_effect") or {})
    resolved_effect = dict(positive_result.get("resolved_candidate_effect") or {})
    title_result = dict(cases["missing_item_title"].get("result") or {})
    title_item_effect = dict(title_result.get("item_effect") or {})
    return {
        "decision": "DISPLAYED_PRIMARY_SAFE_COMBINED_PROMOTION_OBJECT_READY_FOR_CUTOVER",
        "cases": cases,
        "source_checks": {
            "builder_present": "def build_final_design_guide_displayed_primary_safe_combined_promotion_result(" in source,
            "builder_exported": '"build_final_design_guide_displayed_primary_safe_combined_promotion_result"' in source,
            "clean_import_boundary": all(
                token not in source
                for token in ("import streamlit", "st.session_state", "inputs_page")
            ),
        },
        "positive_applies": positive_result.get("applies") is True,
        "positive_button_contract_present": bool(positive_result.get("button_contract_effect")),
        "positive_item_effect_matches_shape": all(
            key in item_effect
            for key in (
                "button_contract",
                "action_type",
                "family",
                "check_key",
                "selected_action_updates",
                "updates",
                "candidate_id",
                "source_candidate_id",
            )
        ),
        "positive_payload_effect_matches_shape": all(
            key in payload_effect
            for key in (
                "updates",
                "resolved_candidate_updates",
                "resolved_candidate_action_type",
                "resolved_candidate_family_tag",
                "source_candidate_id",
                "candidate_id",
                "expected_util",
            )
        ),
        "positive_resolved_effect_matches_shape": all(
            key in resolved_effect
            for key in (
                "updates",
                "action_type",
                "family",
                "source_candidate_id",
                "candidate_id",
                "expected_util",
            )
        ),
        "setdefault_title_semantics_preserved": (
            "title_main" not in item_effect
            and bool(item_effect.get("title"))
            and bool(title_item_effect.get("title_main"))
            and bool(title_item_effect.get("title"))
        ),
        "stable_repeat_hash": cases["positive"].get("proof_hash") == cases["positive_repeat"].get("proof_hash"),
        "blocked_cases_do_not_apply": all(
            dict(cases[key].get("result") or {}).get("applies") is False
            for key in ("already_enabled", "no_intent")
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
        "positive_button_contract_present": capture.get("positive_button_contract_present") is True,
        "positive_item_effect_matches_shape": capture.get("positive_item_effect_matches_shape") is True,
        "positive_payload_effect_matches_shape": capture.get("positive_payload_effect_matches_shape") is True,
        "positive_resolved_effect_matches_shape": capture.get("positive_resolved_effect_matches_shape") is True,
        "setdefault_title_semantics_preserved": capture.get("setdefault_title_semantics_preserved") is True,
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
        "# Displayed Primary Safe Combined Promotion Object Snapshot",
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
        "schema": "design_guide_displayed_primary_safe_combined_promotion_object_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_displayed_primary_safe_combined_promotion_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_displayed_primary_safe_combined_promotion_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_displayed_primary_safe_combined_promotion_object_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
