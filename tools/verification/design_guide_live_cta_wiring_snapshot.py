"""Trace-only live CTA wiring snapshot.

This verifier compares current live CTA binding-shaped payloads with the
proof-only FinalDesignGuidePublication CTA adapter. It does not move CTA
authority, render buttons, route apply actions, write session payloads, or
change visible wording.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
CURRENT_CTA_FILES = (
    ROOT / "inputs_application" / "page_runtime" / "common.py",
    ROOT / "inputs_application" / "page_runtime" / "design_guide_runtime_support.py",
    ROOT / "inputs_page_modules" / "design_guide" / "primary_button_queue.py",
    ROOT / "inputs_page_modules" / "design_guide" / "panel_orchestration.py",
    ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py",
)

COMPARE_FIELDS = (
    "enabled",
    "label",
    "disabled_reason",
    "action_type",
    "apply_payload_fingerprint",
    "executor_backed_proof",
    "stale_fresh_token_proof",
    "source_precedence_proof",
    "one_click_action_handoff",
    "session_debug_payload_shape",
)

LIVE_SYMBOLS = [
    ("design_brain/final_publication.py", "def build_final_visible_render_binding_payload("),
    ("design_brain/final_publication.py", "direct_pass_through_after_adapter_identity_proof"),
    ("design_brain/final_publication.py", "pre_card_direct_pass_through_after_adapter_identity_proof"),
    ("inputs_page_modules/design_guide/primary_apply_payload_recorder.py", "def _record_rendered_design_guide_primary_apply_payload("),
    ("inputs_application/page_runtime/common.py", "def _consume_design_guide_component_cta_value("),
    ("inputs_page_modules/design_guide/primary_button_queue.py", "def _queue_primary_design_guide_button_action("),
    ("inputs_page_modules/design_guide/current_coordinators.py", "winning_button_contract_source"),
    ("inputs_page_modules/design_guide/render_coordinators.py", "def render_design_guide_component_cta("),
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _symbol_presence() -> list[dict[str, Any]]:
    rows = []
    for rel_path, token in LIVE_SYMBOLS:
        if rel_path == "inputs_page.py":
            source = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in (ROOT / "inputs_page.py", ROUTE_COORDINATORS, *CURRENT_CTA_FILES)
                if path.exists()
            )
        else:
            source = (ROOT / rel_path).read_text(encoding="utf-8")
        rows.append(
            {
                "owner_file": rel_path,
                "token": token,
                "present": token in source,
            }
        )
    return rows


def _case_definitions() -> dict[str, dict[str, Any]]:
    enabled_updates = {"bot_dia": 20, "bot_count": 4}
    combined_updates = {"s_lig": 200, "bot_dia": 20}
    return {
        "enabled_executor_backed_apply_cta": {
            "item": {
                "primary_action": "Run one-click auto design",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "bending",
                    "updates": enabled_updates,
                    "preview_pass": True,
                    "source_candidate_id": "enabled-1",
                    "executor_backed": True,
                },
                "action_payload": {"action_type": "apply_resolved_candidate", "updates": enabled_updates},
                "candidate_search_evidence": {
                    "safe_executor_backed_candidates_count": 1,
                    "winning_button_contract_source": "displayed_primary_item",
                    "winning_update_payload_source": "button_contract_updates",
                    "winning_candidate_source": "source_candidate_id",
                },
            },
            "debug": {
                "primary_button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "bending",
                    "updates": enabled_updates,
                },
                "button_contract_enabled": True,
            },
            "session_payload": {
                "action_type": "apply_resolved_candidate",
                "updates": enabled_updates,
                "button_contract_updates": enabled_updates,
                "state_fingerprint": "state-enabled",
            },
        },
        "disabled_blocker_cta": {
            "item": {
                "primary_action": "Review blocker evidence",
                "blocking_reason": "no_valid_shear_repair",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "family": "SHEAR_FAIL_GOVERNS",
                    "updates": {},
                    "blocking_reason": "no_valid_shear_repair",
                },
            },
            "debug": {"button_contract_enabled": False, "blocked_publication_type": "no_valid_shear_repair"},
            "session_payload": {},
        },
        "stale_payload_disabled_cta": {
            "item": {
                "primary_action": "Run one-click auto design",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "action_type": "apply_resolved_candidate",
                    "family": "bending",
                    "updates": enabled_updates,
                    "blocking_reason": "component_apply_token_mismatch",
                },
                "action_payload": {
                    "action_type": "apply_resolved_candidate",
                    "updates": enabled_updates,
                    "component_apply_token": "stale-token",
                    "stale_apply_payload_blocked": True,
                    "stale_apply_payload_mismatch_reason": "component_apply_token_mismatch",
                    "stale_apply_payload_expected_fingerprint": "expected-fp",
                    "stale_apply_payload_current_fingerprint": "current-fp",
                },
            },
            "debug": {
                "stale_apply_payload_blocked": True,
                "component_apply_token": "stale-token",
            },
            "session_payload": {
                "action_type": "apply_resolved_candidate",
                "updates": enabled_updates,
                "stale_apply_payload_blocked": True,
                "stale_apply_payload_mismatch_reason": "component_apply_token_mismatch",
            },
        },
        "proof_pending_cta": {
            "item": {
                "primary_action": "Review Design Guide recommendation",
                "button_contract": {},
            },
            "debug": {"publication_probe_pending": True},
            "session_payload": {},
        },
        "no_action_pass_cta": {
            "item": {
                "status": "PASS",
                "bucket": "pass",
                "title_main": "Design accepted",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "updates": {},
                    "blocking_reason": "target_band_reached_no_action",
                },
            },
            "debug": {"button_contract_enabled": False},
            "session_payload": {},
        },
        "one_click_handoff_cta": {
            "item": {
                "primary_action": "Run one-click auto design",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "combined",
                    "updates": combined_updates,
                    "preview_pass": True,
                    "candidate_id": "one-click-1",
                    "executor_backed": True,
                },
                "action_payload": {
                    "action_type": "apply_resolved_candidate",
                    "family": "combined",
                    "updates": combined_updates,
                    "candidate_id": "one-click-1",
                },
                "candidate_search_evidence": {"safe_executor_backed_candidates_count": 1},
            },
            "debug": {"button_contract_enabled": True},
            "session_payload": {
                "action_type": "apply_resolved_candidate",
                "updates": combined_updates,
                "candidate_id": "one-click-1",
                "route_target": "handle_apply_buttons",
            },
        },
        "fallback_disabled_cta": {
            "item": {
                "primary_action": "Publication blocked by family contract.",
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "family": "BENDING_FAIL_GOVERNS",
                    "updates": {},
                    "blocking_reason": "family_selection_contract_mismatch",
                },
            },
            "debug": {"button_contract_enabled": False, "family_match_passed": False},
            "session_payload": {},
        },
        "render_fallback_shell_cta": {
            "item": {
                "primary_action": "Run one-click auto design",
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "SHEAR_FAIL_GOVERNS",
                    "updates": {"s_lig": 175},
                    "preview_pass": True,
                    "source_candidate_id": "fallback-shell-1",
                    "executor_backed": True,
                },
                "action_payload": {
                    "action_type": "apply_resolved_candidate",
                    "family": "SHEAR_FAIL_GOVERNS",
                    "updates": {"s_lig": 175},
                    "source_candidate_id": "fallback-shell-1",
                },
                "candidate_search_evidence": {
                    "safe_executor_backed_candidates_count": 1,
                    "winning_button_contract_source": "debug_bundle_fallback_contract",
                    "winning_update_payload_source": "fallback_contract_updates",
                    "winning_candidate_source": "fallback_source_candidate_id",
                },
            },
            "debug": {
                "actual_card_render_probe": {
                    "marker": "fallback_enabled_contract_shell",
                    "render_button_contract_enabled": True,
                },
                "button_contract_enabled": True,
                "winning_button_contract_source": "debug_bundle_fallback_contract",
                "winning_update_payload_source": "fallback_contract_updates",
                "winning_candidate_source": "fallback_source_candidate_id",
            },
            "session_payload": {
                "action_type": "apply_resolved_candidate",
                "updates": {"s_lig": 175},
                "source_candidate_id": "fallback-shell-1",
                "render_fallback_shell": True,
            },
        },
    }


def _source_precedence_from_case(case: dict[str, Any]) -> dict[str, Any]:
    item = _mapping(case.get("item"))
    debug = _mapping(case.get("debug"))
    evidence = _mapping(item.get("candidate_search_evidence"))
    return {
        "button_contract_source": debug.get("winning_button_contract_source")
        or evidence.get("winning_button_contract_source"),
        "update_payload_source": debug.get("winning_update_payload_source")
        or evidence.get("winning_update_payload_source"),
        "candidate_source": debug.get("winning_candidate_source")
        or evidence.get("winning_candidate_source"),
    }


def _live_cta_surface(case: dict[str, Any]) -> dict[str, Any]:
    from design_brain.final_publication import stable_final_publication_hash

    item = _mapping(case.get("item"))
    debug = _mapping(case.get("debug"))
    contract = _mapping(item.get("button_contract") or debug.get("primary_button_contract") or debug.get("button_contract"))
    action_payload = _mapping(case.get("session_payload") or item.get("action_payload"))
    evidence = _mapping(item.get("candidate_search_evidence") or debug.get("candidate_search_evidence"))
    updates = _mapping(
        contract.get("updates")
        or action_payload.get("updates")
        or action_payload.get("resolved_candidate_updates")
        or item.get("updates")
    )
    apply_payload_source = action_payload or {"updates": updates}
    precedence = _source_precedence_from_case(case)
    source_precedence_proof = {
        "button_contract_source": _text(precedence.get("button_contract_source")),
        "update_payload_source": _text(precedence.get("update_payload_source")),
        "candidate_source": _text(precedence.get("candidate_source")),
        "source_precedence_hash": stable_final_publication_hash(precedence),
    }
    executor_backed_proof = {
        "executor_backed": bool(
            contract.get("executor_backed")
            or action_payload.get("executor_backed")
            or evidence.get("executor_backed")
            or evidence.get("safe_executor_backed_candidate_found")
            or int(evidence.get("safe_executor_backed_candidates_count") or 0) > 0
        ),
        "safe_executor_backed_candidates_count": evidence.get("safe_executor_backed_candidates_count"),
        "preview_pass": contract.get("preview_pass"),
        "source": _text(contract.get("executor_source"), evidence.get("executor_source"), "publication_payload"),
    }
    stale_fresh_token_proof = {
        "component_apply_token": _text(action_payload.get("component_apply_token"), debug.get("component_apply_token")),
        "stale_apply_payload_blocked": bool(
            action_payload.get("stale_apply_payload_blocked")
            or debug.get("stale_apply_payload_blocked")
        ),
        "stale_apply_payload_mismatch_reason": _text(
            action_payload.get("stale_apply_payload_mismatch_reason"),
            debug.get("stale_apply_payload_mismatch_reason"),
            debug.get("component_apply_stale_reason"),
        ),
        "expected_fingerprint": _text(
            action_payload.get("stale_apply_payload_expected_fingerprint"),
            debug.get("stale_apply_payload_expected_fingerprint"),
        ),
        "current_fingerprint": _text(
            action_payload.get("stale_apply_payload_current_fingerprint"),
            debug.get("stale_apply_payload_current_fingerprint"),
        ),
    }
    return {
        "enabled": bool(contract.get("enabled") or contract.get("actionable")),
        "label": _text(item.get("primary_action"), item.get("cta_label"), contract.get("label")),
        "disabled_reason": _text(contract.get("disabled_reason"), contract.get("blocking_reason"), item.get("blocking_reason")),
        "action_type": _text(contract.get("action_type"), item.get("action_type"), action_payload.get("action_type")),
        "apply_payload_fingerprint": stable_final_publication_hash(apply_payload_source),
        "executor_backed_proof": executor_backed_proof,
        "stale_fresh_token_proof": stale_fresh_token_proof,
        "source_precedence_proof": source_precedence_proof,
        "one_click_action_handoff": {
            "action_type": _text(contract.get("action_type"), item.get("action_type"), action_payload.get("action_type")),
            "candidate_id": _text(
                contract.get("source_candidate_id"),
                contract.get("candidate_id"),
                action_payload.get("source_candidate_id"),
                action_payload.get("candidate_id"),
                item.get("source_candidate_id"),
                item.get("candidate_id"),
            ),
            "family": _text(contract.get("family"), action_payload.get("family"), item.get("family")),
            "updates_hash": stable_final_publication_hash(updates),
            "has_updates": bool(updates),
        },
        "session_debug_payload_shape": _session_debug_payload_shape(case),
    }


def _adapter_cta_surface(case: dict[str, Any]) -> dict[str, Any]:
    from design_brain.final_publication import build_final_publication_cta_from_current_state

    item = _mapping(case.get("item"))
    cta = build_final_publication_cta_from_current_state(
        item=item,
        debug=case.get("debug"),
        button_contract=item.get("button_contract"),
        action_payload=case.get("session_payload") or item.get("action_payload"),
        candidate_search_evidence=item.get("candidate_search_evidence"),
        source_precedence=_source_precedence_from_case(case),
    ).to_dict()
    return {
        "enabled": cta["enabled"],
        "label": cta["label"],
        "disabled_reason": cta["disabled_reason"],
        "action_type": cta["action_type"],
        "apply_payload_fingerprint": cta["apply_payload_fingerprint"],
        "executor_backed_proof": cta["executor_backed_proof"],
        "stale_fresh_token_proof": cta["stale_fresh_token_proof"],
        "source_precedence_proof": cta["source_precedence_proof"],
        "one_click_action_handoff": cta["one_click_action_handoff"],
        "session_debug_payload_shape": _session_debug_payload_shape(case),
    }


def _session_debug_payload_shape(case: dict[str, Any]) -> dict[str, Any]:
    item = _mapping(case.get("item"))
    debug = _mapping(case.get("debug"))
    session_payload = _mapping(case.get("session_payload"))
    contract = _mapping(item.get("button_contract"))
    return {
        "has_session_payload": bool(session_payload),
        "session_payload_keys": sorted(session_payload.keys()),
        "debug_keys": sorted(debug.keys()),
        "contract_keys": sorted(contract.keys()),
        "has_button_contract": bool(contract),
        "has_button_contract_updates": bool(_mapping(contract.get("updates"))),
        "has_apply_updates": bool(_mapping(session_payload.get("updates"))),
        "debug_button_contract_enabled": debug.get("button_contract_enabled"),
    }


def _build_snapshot() -> dict[str, Any]:
    symbol_rows = _symbol_presence()
    inputs_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
                for path in (ROOT / "inputs_page.py", ROUTE_COORDINATORS, *CURRENT_CTA_FILES)
        if path.exists()
    )
    fallback_shell_guarded = "FinalDesignGuidePublication.cta" in inputs_source
    missing_symbols = [row for row in symbol_rows if not row["present"]]
    cases: dict[str, Any] = {}
    failures: list[str] = []
    fallback_shell_risks: list[str] = []
    for name, case in _case_definitions().items():
        live = _live_cta_surface(case)
        adapter = _adapter_cta_surface(case)
        mismatches = {
            field: {"live": live.get(field), "adapter": adapter.get(field)}
            for field in COMPARE_FIELDS
            if live.get(field) != adapter.get(field)
        }
        if mismatches:
            failures.append(f"{name}:cta_wiring_mismatch")
        if name == "render_fallback_shell_cta" and (mismatches or not fallback_shell_guarded):
            fallback_shell_risks.append(
                "render fallback shell CTA no longer matches FinalDesignGuidePublication.cta"
            )
        cases[name] = {
            "parity_status": "PASS" if not mismatches else "FAIL",
            "live": live,
            "adapter": adapter,
            "mismatches": mismatches,
            "case_hash": _stable_hash({"live": live, "adapter": adapter}),
        }
    if missing_symbols:
        failures.append("missing_live_cta_symbols")
    live_cta_wiring_parity = "PASS" if not failures else "FAIL"
    return {
        "snapshot_name": "design_guide_live_cta_wiring",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "live_cta_wiring_parity": live_cta_wiring_parity,
        "status": live_cta_wiring_parity,
        "product_behavior_changed": False,
        "cta_authority_moved": False,
        "button_rendering_changed": False,
        "apply_routing_changed": False,
        "session_payloads_changed": False,
        "visible_wording_changed": False,
        "live_symbol_presence": symbol_rows,
        "cases": cases,
        "remaining_mismatches": {
            name: case["mismatches"]
            for name, case in cases.items()
            if case["mismatches"]
        },
        "fallback_shell_guarded_non_authoritative": bool(fallback_shell_guarded),
        "fallback_shell_risks": fallback_shell_risks,
        "object_ready_for_live_cta_authority": live_cta_wiring_parity == "PASS",
        "object_ready_for_live_cta_authority_text": "yes" if live_cta_wiring_parity == "PASS" else "no",
        "required_before_live_cta_move": (
            [
                "fallback shell remains live; keep it guarded in the cutover verifier",
                "run final-publication boundary snapshot after wiring live CTA authority",
                "run CTA source-precedence and apply-button contract snapshots after cutover",
            ]
            if live_cta_wiring_parity == "PASS"
            else ["resolve remaining_mismatches before moving CTA authority"]
        ),
        "snapshot_hash": _stable_hash(
            {
                "case_hashes": {name: case["case_hash"] for name, case in cases.items()},
                "symbol_presence": symbol_rows,
                "ready": live_cta_wiring_parity == "PASS",
            }
        ),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    case_rows = []
    for name, case in snapshot["cases"].items():
        live = case["live"]
        case_rows.append(
            "| {name} | {status} | {enabled} | {label} | {reason} | {mismatches} |".format(
                name=name,
                status=case["parity_status"],
                enabled=live["enabled"],
                label=str(live["label"] or ""),
                reason=str(live["disabled_reason"] or ""),
                mismatches=len(case["mismatches"]),
            )
        )
    body = "\n".join(
        [
            "# Design Guide Live CTA Wiring Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['live_cta_wiring_parity']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "This is trace-only. It compares live CTA binding-shaped payloads to `FinalDesignGuidePublication.cta` and does not move CTA authority.",
            "",
            "## Assertions",
            "",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            f"- CTA authority moved: `{snapshot['cta_authority_moved']}`",
            f"- Button rendering changed: `{snapshot['button_rendering_changed']}`",
            f"- Apply routing changed: `{snapshot['apply_routing_changed']}`",
            f"- Session payloads changed: `{snapshot['session_payloads_changed']}`",
            f"- Visible wording changed: `{snapshot['visible_wording_changed']}`",
            "",
            "## Cases",
            "",
            "| Case | Parity | Enabled | Label | Disabled reason | Mismatches |",
            "|---|---|---|---|---|---:|",
            *case_rows,
            "",
            "## Readiness",
            "",
            f"- object_ready_for_live_cta_authority: `{snapshot['object_ready_for_live_cta_authority_text']}`",
            f"- remaining_mismatches: `{snapshot['remaining_mismatches']}`",
            f"- fallback_shell_risks: `{snapshot['fallback_shell_risks']}`",
            "",
            "Required before live CTA move:",
            "",
            *[f"- {item}" for item in snapshot["required_before_live_cta_move"]],
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_live_cta_wiring_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_cta_wiring_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_live_cta_wiring_snapshot {snapshot['live_cta_wiring_parity']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("failures=" + ", ".join(snapshot["failures"]))
    return 0 if snapshot["live_cta_wiring_parity"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
