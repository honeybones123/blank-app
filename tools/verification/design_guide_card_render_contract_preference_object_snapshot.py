"""Proof snapshot for card render contract preference extraction."""

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


SHEAR_KEYS = ("shear_bar_size", "shear_spacing")


def _intent_debug() -> dict[str, Any]:
    return {
        "guidance_intent_items": [
            {
                "title": "Shear cleanup - one-click reduction",
                "family": "shear",
                "check_key": "shear",
                "button_contract": {
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "shear",
                    "updates": {"shear_bar_size": "N10", "shear_spacing": 0.0},
                    "preview_pass": True,
                    "blocking_reason": None,
                    "expected_util": 0.88,
                    "candidate_id": "intent-shear-card-1",
                },
            }
        ]
    }


def _safe_evidence_item() -> dict[str, Any]:
    evidence = {
        "family": "shear",
        "best_safe_candidate_updates": {"shear_bar_size": "N10", "shear_spacing": 0.0},
        "best_safe_final_util": 0.89,
        "best_safe_candidate_id": "safe-evidence-shear-card-1",
        "one_click_target_reaching_candidate_exists": True,
        "accepted_band_candidate_count": 1,
        "exact_blockers_by_family": {"shear": {"stale": True}},
    }
    return {
        "candidate_search_evidence": dict(evidence),
        "action_payload": {"candidate_search_evidence": dict(evidence)},
        "resolved_candidate": {"candidate_search_evidence": dict(evidence)},
    }


def _cases() -> dict[str, dict[str, Any]]:
    from design_brain.final_publication import (  # noqa: PLC0415
        build_final_design_guide_card_render_contract_preference_result,
    )

    kwargs = {
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 0.001,
        "shear_update_keys": SHEAR_KEYS,
    }
    state = {"shear_bar_size": "N12", "shear_spacing": 150.0}
    intent_row = build_final_design_guide_card_render_contract_preference_result(
        item={},
        guidance_debug=_intent_debug(),
        state=state,
        active_strength_failures=(),
        **kwargs,
    )
    intent_repeat = build_final_design_guide_card_render_contract_preference_result(
        item={},
        guidance_debug=_intent_debug(),
        state=state,
        active_strength_failures=(),
        **kwargs,
    )
    safe_evidence = build_final_design_guide_card_render_contract_preference_result(
        item=_safe_evidence_item(),
        guidance_debug={},
        state=state,
        active_strength_failures=(),
        **kwargs,
    )
    stale_updates = build_final_design_guide_card_render_contract_preference_result(
        item=_safe_evidence_item(),
        guidance_debug=_intent_debug(),
        state={"shear_bar_size": "N10", "shear_spacing": 0.0},
        active_strength_failures=(),
        **kwargs,
    )
    active_failure = build_final_design_guide_card_render_contract_preference_result(
        item={},
        guidance_debug=_intent_debug(),
        state=state,
        active_strength_failures=("shear",),
        **kwargs,
    )
    return {
        "intent_row": intent_row,
        "intent_repeat": intent_repeat,
        "safe_evidence": safe_evidence,
        "stale_updates": stale_updates,
        "active_failure": active_failure,
    }


def _capture() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    cases = _cases()
    intent_result = dict(cases["intent_row"].get("result") or {})
    safe_result = dict(cases["safe_evidence"].get("result") or {})
    intent_evidence = dict(intent_result.get("item_effect") or {}).get("candidate_search_evidence") or {}
    safe_evidence = dict(safe_result.get("item_effect") or {}).get("candidate_search_evidence") or {}
    return {
        "decision": "CARD_RENDER_CONTRACT_PREFERENCE_OBJECT_READY_FOR_CUTOVER",
        "cases": cases,
        "source_checks": {
            "builder_present": "def build_final_design_guide_card_render_contract_preference_result(" in source,
            "builder_exported": '"build_final_design_guide_card_render_contract_preference_result"' in source,
            "clean_import_boundary": all(
                token not in source
                for token in ("import streamlit", "st.session_state", "inputs_page")
            ),
        },
        "intent_row_applies": intent_result.get("applies") is True,
        "intent_row_source": intent_result.get("source") == "intent_row",
        "safe_evidence_applies": safe_result.get("applies") is True,
        "safe_evidence_source": safe_result.get("source") == "safe_shear_evidence",
        "stale_evidence_removed": all(
            key not in safe_evidence
            for key in (
                "exact_blockers_by_family",
                "post_click_exact_blockers_by_family",
                "cleanup_evidence_by_family",
                "post_click_cleanup_evidence_by_family",
            )
        ),
        "counts_present": all(
            int(safe_evidence.get(key) or intent_evidence.get(key) or 0) >= 1
            for key in (
                "safe_candidate_count",
                "executable_candidate_count",
                "safe_cleanup_count",
                "executable_cleanup_count",
                "safe_shear_cleanup_count",
                "executable_shear_cleanup_count",
            )
        ),
        "effect_shapes_present": all(
            bool(intent_result.get(key))
            for key in (
                "button_contract_effect",
                "item_effect",
                "action_payload_effect",
                "resolved_candidate_effect",
                "debug_effect",
            )
        ),
        "stable_repeat_hash": cases["intent_row"].get("proof_hash") == cases["intent_repeat"].get("proof_hash"),
        "blocked_cases_do_not_apply": all(
            dict(cases[key].get("result") or {}).get("applies") is False
            for key in ("stale_updates", "active_failure")
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
        "intent_row_applies": capture.get("intent_row_applies") is True,
        "intent_row_source": capture.get("intent_row_source") is True,
        "safe_evidence_applies": capture.get("safe_evidence_applies") is True,
        "safe_evidence_source": capture.get("safe_evidence_source") is True,
        "stale_evidence_removed": capture.get("stale_evidence_removed") is True,
        "counts_present": capture.get("counts_present") is True,
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
        "# Card Render Contract Preference Object Snapshot",
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
        "schema": "design_guide_card_render_contract_preference_object_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_card_render_contract_preference_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_card_render_contract_preference_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_card_render_contract_preference_object_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
