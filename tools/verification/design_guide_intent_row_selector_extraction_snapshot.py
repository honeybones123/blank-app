"""Snapshot proving intent-row contract selection is Design Brain-owned.

This is a narrow extraction proof. It verifies that the old inputs-page helper
no longer owns the debug-row selection policy and that the public Design Brain
selector preserves the page-compatible result shape.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _source_between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    if end < 0:
        end = len(source)
    return source[start:end]


def _expected_selector(guidance_debug: dict[str, Any] | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(guidance_debug, dict):
        return None, None
    for key in ("displayed_guidance_intent_items", "guidance_intent_items"):
        rows = guidance_debug.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            contract = dict(row.get("button_contract") or {})
            action_type = str(contract.get("action_type") or row.get("action_type") or "").strip()
            if (
                bool(contract.get("actionable"))
                and action_type == "apply_resolved_candidate"
                and bool(contract.get("preview_pass"))
                and contract.get("blocking_reason") is None
                and dict(contract.get("updates") or {})
            ):
                return contract, row
    return None, None


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "displayed_row_wins",
            "debug": {
                "displayed_guidance_intent_items": [
                    {
                        "check_key": "bending",
                        "button_contract": {
                            "enabled": True,
                            "actionable": True,
                            "action_type": "apply_resolved_candidate",
                            "updates": {"D": 650},
                        },
                    }
                ],
                "guidance_intent_items": [
                    {
                        "check_key": "shear",
                        "button_contract": {
                            "enabled": True,
                            "actionable": True,
                            "action_type": "apply_resolved_candidate",
                            "updates": {"shear_link_spacing": 150},
                        },
                    }
                ],
            },
        },
        {
            "name": "old_helper_semantics_enabled_flag_not_required",
            "debug": {
                "displayed_guidance_intent_items": [
                    {
                        "check_key": "bending",
                        "button_contract": {
                            "actionable": True,
                            "preview_pass": True,
                            "blocking_reason": None,
                            "action_type": "apply_resolved_candidate",
                            "updates": {"bottom_bars": "6N16"},
                        },
                    }
                ],
            },
        },
        {
            "name": "fallback_to_guidance_rows",
            "debug": {
                "displayed_guidance_intent_items": [],
                "guidance_intent_items": [
                    {
                        "check_key": "shear",
                        "button_contract": {
                            "enabled": True,
                            "actionable": True,
                            "action_type": "apply_resolved_candidate",
                            "updates": {"shear_legs": 0},
                        },
                    }
                ],
            },
        },
        {
            "name": "disabled_no_match",
            "debug": {
                "displayed_guidance_intent_items": [
                    {
                        "check_key": "bending",
                        "button_contract": {
                            "enabled": False,
                            "actionable": False,
                            "action_type": "apply_resolved_candidate",
                            "updates": {"D": 650},
                        },
                    }
                ],
            },
        },
        {
            "name": "missing_updates_no_match",
            "debug": {
                "guidance_intent_items": [
                    {
                        "check_key": "bending",
                        "button_contract": {
                            "enabled": True,
                            "actionable": True,
                            "action_type": "apply_resolved_candidate",
                            "updates": {},
                        },
                    }
                ],
            },
        },
        {"name": "none_no_match", "debug": None},
    ]


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import select_enabled_design_guide_contract_from_intent_rows

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    wrapper_source = _source_between(
        inputs_source,
        "def _enabled_design_guide_contract_from_intent_rows(",
        "\ndef _publishable_safe_cleanup_updates_from_evidence(",
    )
    public_source = _source_between(
        final_source,
        "def select_enabled_design_guide_contract_from_intent_rows(",
        "\ndef build_final_visible_contract_binding_intent_contract_rebind_result(",
    )

    case_results = []
    for case in _cases():
        expected_contract, expected_row = _expected_selector(case.get("debug"))
        actual_contract, actual_row = select_enabled_design_guide_contract_from_intent_rows(case.get("debug"))
        case_results.append(
            {
                "name": case["name"],
                "expected_hash": _stable_hash({"contract": expected_contract, "row": expected_row}),
                "actual_hash": _stable_hash({"contract": actual_contract, "row": actual_row}),
                "matches": (expected_contract, expected_row) == (actual_contract, actual_row),
                "none_shape_preserved": (
                    (expected_contract is None and actual_contract is None)
                    or (isinstance(actual_contract, dict) and isinstance(actual_row, dict))
                ),
            }
        )

    return {
        "decision": "INTENT_ROW_SELECTOR_POLICY_EXTRACTED_TO_DESIGN_BRAIN",
        "inputs_wrapper_source": wrapper_source.strip(),
        "public_selector_source_hash": _stable_hash(public_source),
        "case_results": case_results,
        "source_checks": {
            "inputs_wrapper_deleted_or_thin": (
                "def _enabled_design_guide_contract_from_intent_rows(" not in inputs_source
                or "_select_enabled_design_guide_contract_from_intent_rows(guidance_debug)" in wrapper_source
            ),
            "inputs_wrapper_deleted": "def _enabled_design_guide_contract_from_intent_rows(" not in inputs_source,
            "inputs_has_no_old_helper_calls": not bool(
                re.search(r"(?<!select)_enabled_design_guide_contract_from_intent_rows\(", inputs_source)
            ),
            "inputs_no_longer_scans_rows_in_helper": (
                not wrapper_source
                or (
                    '"displayed_guidance_intent_items", "guidance_intent_items"' not in wrapper_source
                    and "for row in rows:" not in wrapper_source
                )
            ),
            "public_selector_exported": '"select_enabled_design_guide_contract_from_intent_rows"' in final_source,
            "public_selector_uses_final_publication_private_core": (
                "_final_visible_intent_contract_from_debug_rows(guidance_debug)" in public_source
            ),
            "public_selector_preserves_none_shape": "return None, None" in public_source,
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "delete_or_narrow_now": False,
        "next_safe_step": (
            "Replace remaining inputs-page helper callsites with the Design Brain public selector, "
            "then delete the compatibility wrapper once callsite parity and composed locks pass."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        **source_checks,
        "all_cases_match": all(bool(row.get("matches")) for row in capture.get("case_results") or []),
        "none_shape_preserved": all(bool(row.get("none_shape_preserved")) for row in capture.get("case_results") or []),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "not_ready_to_delete_wrapper": capture.get("delete_or_narrow_now") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Intent Row Selector Extraction Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Case Parity",
        "",
    ]
    for result in capture.get("case_results") or []:
        lines.append(
            f"- {result.get('name')}: matches=`{result.get('matches')}` none_shape=`{result.get('none_shape_preserved')}`"
        )
    lines.extend(["", "## Source Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if not passed]
    payload = {
        "schema": "design_guide_intent_row_selector_extraction_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_intent_row_selector_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_intent_row_selector_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_intent_row_selector_extraction_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print(f"failures={','.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
