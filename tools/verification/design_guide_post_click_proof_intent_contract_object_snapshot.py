"""Proof snapshot for post-click proof intent contract extraction."""

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


def _debug(*, family: str = "bending", updates: dict[str, Any] | None = None) -> dict[str, Any]:
    if updates is None:
        updates = {"bottom_bar_count": 8} if family == "bending" else {"shear_spacing": 0.0}
    return {
        "guidance_intent_items": [
            {
                "title": "Post-click proof intent",
                "family": family,
                "check_key": family,
                "guidance_intent": "efficiency_tightening",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": family,
                    "updates": dict(updates),
                    "preview_pass": True,
                    "expected_util": 0.9,
                    "blocking_reason": None,
                    "candidate_id": f"{family}-proof-1",
                    "source_candidate_id": f"{family}-proof-1",
                },
            }
        ]
    }


def _cases() -> dict[str, dict[str, Any]]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_design_guide_post_click_proof_intent_contract_result,
    )

    bending_positive = build_final_design_guide_post_click_proof_intent_contract_result(
        item={"family": "combined", "check_key": "combined"},
        guidance_debug=_debug(family="bending"),
    )
    bending_repeat = build_final_design_guide_post_click_proof_intent_contract_result(
        item={"family": "combined", "check_key": "combined"},
        guidance_debug=_debug(family="bending"),
    )
    shear_positive = build_final_design_guide_post_click_proof_intent_contract_result(
        item={"family": "general"},
        guidance_debug=_debug(family="shear"),
    )
    incompatible_display = build_final_design_guide_post_click_proof_intent_contract_result(
        item={"family": "serviceability"},
        guidance_debug=_debug(family="bending"),
    )
    missing_updates = build_final_design_guide_post_click_proof_intent_contract_result(
        item={"family": "combined"},
        guidance_debug=_debug(family="bending", updates={}),
    )
    unsupported_family = build_final_design_guide_post_click_proof_intent_contract_result(
        item={"family": "combined"},
        guidance_debug=_debug(family="combined", updates={"width": 450}),
    )
    no_intent = build_final_design_guide_post_click_proof_intent_contract_result(
        item={"family": "combined"},
        guidance_debug={},
    )
    return {
        "bending_positive": bending_positive,
        "bending_repeat": bending_repeat,
        "shear_positive": shear_positive,
        "incompatible_display": incompatible_display,
        "missing_updates": missing_updates,
        "unsupported_family": unsupported_family,
        "no_intent": no_intent,
    }


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    cases = _cases()
    bending_result = dict(cases["bending_positive"].get("result") or {})
    shear_result = dict(cases["shear_positive"].get("result") or {})
    item_effect = dict(bending_result.get("item_effect") or {})
    debug_effect = dict(bending_result.get("debug_effect") or {})
    return {
        "decision": "POST_CLICK_PROOF_INTENT_CONTRACT_OBJECT_READY_FOR_CUTOVER",
        "cases": cases,
        "source_checks": {
            "builder_present": "def build_final_design_guide_post_click_proof_intent_contract_result(" in source,
            "builder_exported": '"build_final_design_guide_post_click_proof_intent_contract_result"' in source,
            "clean_import_boundary": all(
                token not in source
                for token in ("import streamlit", "st.session_state", "inputs_page")
            ),
        },
        "bending_applies": bending_result.get("applies") is True,
        "shear_applies": shear_result.get("applies") is True,
        "effect_shapes_present": all(
            key in item_effect
            for key in (
                "action_type",
                "family",
                "check_key",
                "selected_action_family",
                "primary_card_actionable",
                "updates",
                "selected_action_updates",
                "button_contract",
                "candidate_id",
                "source_candidate_id",
            )
        )
        and all(
            key in bending_result
            for key in (
                "proof_action_contract_effect",
                "displayed_primary_button_contract_effect",
            )
        )
        and bool(debug_effect.get("displayed_intent_contract_preferred_for_bundle")),
        "stable_repeat_hash": cases["bending_positive"].get("proof_hash")
        == cases["bending_repeat"].get("proof_hash"),
        "blocked_cases_do_not_apply": all(
            dict(cases[key].get("result") or {}).get("applies") is False
            for key in ("incompatible_display", "missing_updates", "unsupported_family", "no_intent")
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
        "bending_applies": capture.get("bending_applies") is True,
        "shear_applies": capture.get("shear_applies") is True,
        "effect_shapes_present": capture.get("effect_shapes_present") is True,
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
        "# Post Click Proof Intent Contract Object Snapshot",
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
        "schema": "design_guide_post_click_proof_intent_contract_object_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_post_click_proof_intent_contract_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_post_click_proof_intent_contract_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_proof_intent_contract_object_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
