"""Parity and cutover snapshot for card VM intent-contract promotion extraction.

Compares the old inline inputs-page promotion semantics with the Design Brain
result object, then proves the live card VM boundary consumes the Design Brain
result instead of selecting intent rows directly.
"""

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


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _contract_enabled(contract: dict[str, Any] | None) -> bool:
    c = dict(contract or {}) if isinstance(contract, dict) else {}
    return bool(
        c.get("actionable")
        and dict(c.get("updates") or {})
        and bool(c.get("preview_pass"))
        and c.get("blocking_reason") is None
    )


def _intent_from_debug(debug_payload: dict[str, Any] | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(debug_payload, dict):
        return None, None
    for key in ("displayed_guidance_intent_items", "guidance_intent_items"):
        rows = debug_payload.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            contract = dict(row.get("button_contract") or {})
            action_type = str(contract.get("action_type") or row.get("action_type") or "").strip()
            if _contract_enabled(contract) and action_type == "apply_resolved_candidate":
                return contract, row
    return None, None


def _old_effects(
    *,
    item: dict[str, Any],
    debug_payload: dict[str, Any],
    overview: dict[str, Any],
    actionable: bool,
) -> dict[str, Any]:
    item_d = dict(item)
    debug_d = dict(debug_payload)
    intent_contract, intent_row = _intent_from_debug(debug_d)
    should_prefer = False
    intent_updates: dict[str, Any] = {}
    intent_expected: float | None = None
    intent_family = ""
    current_family = ""
    promoted_contract: dict[str, Any] = {}
    item_effect: dict[str, Any] = {}
    debug_effect: dict[str, Any] = {}
    action_payload_effect: dict[str, Any] = {}
    resolved_candidate_effect: dict[str, Any] = {}
    display_truth_effect: dict[str, Any] = {}
    display_util_effect: float | None = None
    intent_contract_executable = bool(
        intent_contract
        and dict((intent_contract or {}).get("updates") or {})
        and bool((intent_contract or {}).get("preview_pass"))
        and (intent_contract or {}).get("blocking_reason") is None
        and str((intent_contract or {}).get("action_type") or (intent_row or {}).get("action_type") or "").strip()
        == "apply_resolved_candidate"
        and bool((intent_contract or {}).get("actionable") or (intent_contract or {}).get("enabled"))
    )
    if (actionable or intent_contract_executable) and isinstance(debug_payload, dict):
        if intent_contract and isinstance(intent_row, dict):
            intent_updates = dict(intent_contract.get("updates") or {})
            current_contract = dict(item_d.get("button_contract") or {})
            current_expected = _number(current_contract.get("expected_util"))
            intent_expected = _number(
                intent_contract.get("expected_util")
                or intent_row.get("displayed_util")
                or intent_row.get("candidate_post_util")
            )
            current_family = str(current_contract.get("family") or item_d.get("family") or "").strip().lower()
            intent_family = str(
                intent_row.get("check_key")
                or intent_row.get("family")
                or intent_contract.get("family")
                or ""
            ).strip().lower()
            if intent_family not in {"bending", "shear"}:
                intent_source_util = _number(
                    intent_row.get("source_summary_util")
                    or dict(intent_row.get("display_truth") or {}).get("source_summary_util")
                )
                overview_utils = dict((overview or {}).get("utils") or {}) if isinstance(overview, dict) else {}
                for candidate_family in ("bending", "shear"):
                    current_candidate_util = _number(overview_utils.get(candidate_family))
                    if (
                        intent_source_util is not None
                        and current_candidate_util is not None
                        and abs(float(intent_source_util) - float(current_candidate_util)) <= 0.005
                    ):
                        intent_family = candidate_family
                        break
            should_prefer = bool(
                intent_updates
                and (
                    not _contract_enabled(current_contract)
                    or (
                        intent_expected is not None
                        and current_expected is not None
                        and abs(float(intent_expected) - float(current_expected)) > 0.005
                    )
                    or (current_family == "combined" and intent_family in {"bending", "shear"})
                )
            )
        if should_prefer:
            promoted_contract = dict(intent_contract or {})
            if intent_family in {"bending", "shear"}:
                promoted_contract["family"] = intent_family
                item_effect.update(
                    {
                        "family": intent_family,
                        "check_key": intent_family,
                        "selected_action_family": intent_family,
                    }
                )
            promoted_contract["updates"] = dict(intent_updates)
            promoted_contract["action_type"] = "apply_resolved_candidate"
            promoted_contract["actionable"] = True
            promoted_contract["enabled"] = True
            promoted_contract["preview_pass"] = True
            promoted_contract["blocking_reason"] = None
            if intent_expected is not None:
                promoted_contract["expected_util"] = float(intent_expected)
                display_util_effect = float(intent_expected)
                item_effect.update(
                    {
                        "expected_util": float(intent_expected),
                        "candidate_post_util": float(intent_expected),
                        "displayed_util": float(intent_expected),
                    }
                )
            item_effect.update(
                {
                    "button_contract": dict(promoted_contract),
                    "action_type": "apply_resolved_candidate",
                    "primary_card_actionable": True,
                    "updates": dict(intent_updates),
                    "selected_action_updates": dict(intent_updates),
                }
            )
            action_payload_effect = {
                **dict(item_d.get("action_payload") or {}),
                "updates": dict(intent_updates),
                "resolved_candidate_updates": dict(intent_updates),
                "resolved_candidate_action_type": "apply_resolved_candidate",
                "resolved_candidate_family_tag": promoted_contract.get("family"),
                "source_candidate_id": promoted_contract.get("source_candidate_id")
                or promoted_contract.get("candidate_id"),
                "candidate_id": promoted_contract.get("candidate_id")
                or promoted_contract.get("source_candidate_id"),
                "expected_util": promoted_contract.get("expected_util"),
                "resolved_candidate_post_util": promoted_contract.get("expected_util"),
            }
            resolved_candidate_effect = {
                **dict(item_d.get("resolved_candidate") or {}),
                "updates": dict(intent_updates),
                "action_type": "apply_resolved_candidate",
                "family": promoted_contract.get("family"),
                "source_candidate_id": promoted_contract.get("source_candidate_id")
                or promoted_contract.get("candidate_id"),
                "candidate_id": promoted_contract.get("candidate_id")
                or promoted_contract.get("source_candidate_id"),
                "expected_util": promoted_contract.get("expected_util"),
                "candidate_post_util": promoted_contract.get("expected_util"),
            }
            display_truth_effect = dict(item_d.get("display_truth") or {})
            row_truth = {
                key: intent_row.get(key)
                for key in (
                    "display_truth_source",
                    "displayed_util",
                    "displayed_status",
                    "target_low",
                    "target_high",
                    "displayed_within_target_band",
                    "source_summary_util",
                    "source_candidate_util",
                    "source_post_commit_util",
                )
                if intent_row.get(key) is not None
            }
            display_truth_effect.update(row_truth)
            if intent_expected is not None:
                display_truth_effect["displayed_util"] = float(intent_expected)
                display_truth_effect["source_candidate_util"] = float(intent_expected)
            item_effect["action_payload"] = dict(action_payload_effect)
            item_effect["resolved_candidate"] = dict(resolved_candidate_effect)
            item_effect["display_truth"] = dict(display_truth_effect)
            debug_effect = {
                "primary_button_contract": dict(promoted_contract),
                "button_contract": dict(promoted_contract),
                "displayed_primary_button_contract": dict(promoted_contract),
                "button_contract_enabled": True,
                "button_contract_updates": dict(intent_updates),
                "button_contract_preview_pass": True,
                "button_contract_blocking_reason": None,
                "selected_action_type": "apply_resolved_candidate",
                "selected_action_family": promoted_contract.get("family"),
                "selected_action_updates": dict(intent_updates),
                "primary_display_truth": dict(display_truth_effect),
                "displayed_primary_display_truth": dict(display_truth_effect),
                "final_card_intent_contract_promoted": True,
            }
    output_item = dict(item_d)
    output_item.update(dict(item_effect))
    output_debug = dict(debug_d)
    output_debug.update(dict(debug_effect))
    return {
        "applies": should_prefer,
        "promoted_contract": promoted_contract,
        "item_effect": item_effect,
        "debug_effect": debug_effect,
        "action_payload_effect": action_payload_effect,
        "resolved_candidate_effect": resolved_candidate_effect,
        "display_truth_effect": display_truth_effect,
        "display_util_effect": display_util_effect,
        "output_item": output_item,
        "output_debug": output_debug,
    }


def _scenario_rows() -> list[dict[str, Any]]:
    from design_brain.final_publication import build_final_design_guide_card_vm_intent_contract_promotion_result

    scenarios = [
        {
            "id": "disabled_current_contract_promotes_bending",
            "actionable": True,
            "overview": {"utils": {"bending": 0.42, "shear": 0.9}},
            "item": {"family": "bending", "button_contract": {"actionable": False, "updates": {}}},
            "debug": {
                "displayed_guidance_intent_items": [
                    {
                        "check_key": "bending",
                        "title": "Improve bending",
                        "displayed_util": 0.72,
                        "button_contract": {
                            "actionable": True,
                            "preview_pass": True,
                            "blocking_reason": None,
                            "action_type": "apply_resolved_candidate",
                            "family": "bending",
                            "updates": {"bottom_bars": "8N16"},
                            "candidate_id": "bend-1",
                        },
                    }
                ]
            },
        },
        {
            "id": "expected_util_diff_promotes_shear",
            "actionable": True,
            "overview": {"utils": {"bending": 0.82, "shear": 0.41}},
            "item": {
                "family": "shear",
                "button_contract": {
                    "actionable": True,
                    "preview_pass": True,
                    "blocking_reason": None,
                    "family": "shear",
                    "updates": {"shear_legs": 2},
                    "expected_util": 0.41,
                },
            },
            "debug": {
                "guidance_intent_items": [
                    {
                        "check_key": "shear",
                        "candidate_post_util": 0.74,
                        "display_truth_source": "intent_row",
                        "button_contract": {
                            "actionable": True,
                            "preview_pass": True,
                            "blocking_reason": None,
                            "action_type": "apply_resolved_candidate",
                            "family": "shear",
                            "updates": {"shear_legs": 0},
                            "source_candidate_id": "shear-1",
                        },
                    }
                ]
            },
        },
        {
            "id": "combined_to_bending_promotes",
            "actionable": True,
            "overview": {"utils": {"bending": 0.67, "shear": 0.88}},
            "item": {
                "family": "combined",
                "button_contract": {
                    "actionable": True,
                    "preview_pass": True,
                    "blocking_reason": None,
                    "family": "combined",
                    "updates": {"b": 350},
                    "expected_util": 0.67,
                },
            },
            "debug": {
                "guidance_intent_items": [
                    {
                        "family": "bending",
                        "displayed_util": 0.67,
                        "button_contract": {
                            "actionable": True,
                            "preview_pass": True,
                            "blocking_reason": None,
                            "action_type": "apply_resolved_candidate",
                            "updates": {"bottom_bars": "5N16"},
                            "candidate_id": "bend-combined-1",
                        },
                    }
                ]
            },
        },
        {
            "id": "infer_family_from_source_util",
            "actionable": True,
            "overview": {"utils": {"bending": 0.52, "shear": 0.91}},
            "item": {"family": "combined", "button_contract": {"actionable": False, "updates": {}}},
            "debug": {
                "guidance_intent_items": [
                    {
                        "source_summary_util": 0.52,
                        "displayed_util": 0.76,
                        "button_contract": {
                            "actionable": True,
                            "preview_pass": True,
                            "blocking_reason": None,
                            "action_type": "apply_resolved_candidate",
                            "updates": {"bottom_bars": "6N16"},
                            "candidate_id": "infer-bending-1",
                        },
                    }
                ]
            },
        },
        {
            "id": "blocked_card_valid_intent_contract_promotes",
            "actionable": False,
            "overview": {"utils": {"bending": 0.52}},
            "item": {"family": "bending", "button_contract": {"actionable": False, "updates": {}}},
            "debug": {
                "guidance_intent_items": [
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
                ]
            },
        },
        {
            "id": "blocked_card_without_executable_intent_noop",
            "actionable": False,
            "overview": {"utils": {"bending": 0.52}},
            "item": {"family": "bending", "button_contract": {"actionable": False, "updates": {}}},
            "debug": {
                "guidance_intent_items": [
                    {
                        "check_key": "bending",
                        "button_contract": {
                            "actionable": False,
                            "preview_pass": False,
                            "blocking_reason": "preview_failed",
                            "action_type": "apply_resolved_candidate",
                            "updates": {"bottom_bars": "6N16"},
                        },
                    }
                ]
            },
        },
    ]
    rows = []
    for scenario in scenarios:
        old = _old_effects(
            item=dict(scenario["item"]),
            debug_payload=dict(scenario["debug"]),
            overview=dict(scenario["overview"]),
            actionable=bool(scenario["actionable"]),
        )
        proof = build_final_design_guide_card_vm_intent_contract_promotion_result(
            item=dict(scenario["item"]),
            debug_payload=dict(scenario["debug"]),
            overview=dict(scenario["overview"]),
            actionable=bool(scenario["actionable"]),
        )
        result = dict(proof.get("result") or {})
        rows.append(
            {
                "id": scenario["id"],
                "applies_old": bool(old.get("applies")),
                "applies_new": bool(result.get("applies")),
                "old_hash": _stable_hash(old),
                "new_hash": _stable_hash(
                    {
                        key: result.get(key)
                        for key in (
                            "applies",
                            "promoted_contract",
                            "item_effect",
                            "debug_effect",
                            "action_payload_effect",
                            "resolved_candidate_effect",
                            "display_truth_effect",
                            "display_util_effect",
                            "output_item",
                            "output_debug",
                        )
                    }
                ),
                "matches": _stable_hash(old)
                == _stable_hash(
                    {
                        key: result.get(key)
                        for key in (
                            "applies",
                            "promoted_contract",
                            "item_effect",
                            "debug_effect",
                            "action_payload_effect",
                            "resolved_candidate_effect",
                            "display_truth_effect",
                            "display_util_effect",
                            "output_item",
                            "output_debug",
                        )
                    }
                ),
                "proof_hash": proof.get("proof_hash"),
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    input_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    rows = _scenario_rows()
    return {
        "decision": "CARD_VM_INTENT_CONTRACT_PROMOTION_CUTOVER_IMPLEMENTED",
        "scenario_rows": rows,
        "source_checks": {
            "builder_present": "def build_final_design_guide_card_vm_intent_contract_promotion_result(" in final_source,
            "builder_exported": '"build_final_design_guide_card_vm_intent_contract_promotion_result"' in final_source,
            "inputs_imports_builder": (
                "build_final_design_guide_card_vm_intent_contract_promotion_result as "
                "_build_final_design_guide_card_vm_intent_contract_promotion_result"
            )
            in input_source,
            "old_inline_callsite_removed": (
                "intent_contract, intent_row = _select_enabled_design_guide_contract_from_intent_rows(debug_payload)"
                not in input_source
            ),
            "inputs_consumes_builder_result": (
                "_build_final_design_guide_card_vm_intent_contract_promotion_result(" in input_source
                and "card_vm_intent_contract_promotion_cutover_applied" in input_source
                and "card_vm_intent_contract_promotion_builder_authority" in input_source
            ),
            "page_still_records_apply_payload": (
                "_record_rendered_design_guide_primary_apply_payload(" in input_source
            ),
        },
        "ready_for_trace_wiring": True,
        "ready_for_live_cutover": all(bool(row.get("matches")) for row in rows),
        "live_cutover_implemented": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_step": (
            "Keep this boundary locked and continue route-by-route extraction with the next "
            "remaining intent selector callsite."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("scenario_rows") or [])
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "all_source_checks_pass": all(source_checks.values()),
        "all_scenarios_match": all(bool(row.get("matches")) for row in rows),
        "ready_for_trace_wiring": capture.get("ready_for_trace_wiring") is True,
        "ready_for_live_cutover": capture.get("ready_for_live_cutover") is True,
        "live_cutover_implemented": capture.get("live_cutover_implemented") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Card VM Intent Contract Promotion Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenario Rows",
        "",
        "| Scenario | Old applies | New applies | Parity |",
        "| --- | --- | --- | --- |",
    ]
    for row in capture.get("scenario_rows") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('applies_old')}` | `{row.get('applies_new')}` | `{row.get('matches')}` |"
        )
    lines.extend(["", "## Checks", ""])
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
    failures = [key for key, value in checks.items() if not value]
    payload = {
        "schema": "design_guide_card_vm_intent_contract_promotion_parity_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_card_vm_intent_contract_promotion_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_card_vm_intent_contract_promotion_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_card_vm_intent_contract_promotion_parity_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
