"""Focused snapshot for CTA/button-contract source precedence.

Coverage-only verifier. It records candidate CTA/button sources and the
winning source across representative compute/publication paths before any
source-precedence movement.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"
TRACE_DIR = REPO / "artifacts" / "traces"
CTA_CONTRACT_MODULE_PATH = REPO / "design_brain" / "contracts" / "cta_button_contract.py"


def _load_cta_contract_module() -> Any:
    spec = importlib.util.spec_from_file_location("cta_button_contract_file", CTA_CONTRACT_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load CTA contract module: {CTA_CONTRACT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CTA_CONTRACT = _load_cta_contract_module()
load_cta_button_contract = _CTA_CONTRACT.load_cta_button_contract
cta_button_source_precedence_order = _CTA_CONTRACT.cta_button_source_precedence_order
cta_payload_source_precedence_order = _CTA_CONTRACT.cta_payload_source_precedence_order
required_cta_proof_fields = _CTA_CONTRACT.required_cta_proof_fields
required_cta_source_record_fields = _CTA_CONTRACT.required_cta_source_record_fields
allowed_cta_states = _CTA_CONTRACT.allowed_cta_states
required_cta_gates = _CTA_CONTRACT.required_cta_gates
cta_candidate_source_keys = _CTA_CONTRACT.cta_candidate_source_keys
cta_focused_scenario_expected_winners = _CTA_CONTRACT.cta_focused_scenario_expected_winners
cta_source_payload_labels = _CTA_CONTRACT.cta_source_payload_labels


def _stable_hash(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _contract(
    *,
    family: str,
    updates: dict[str, Any] | None,
    enabled: bool,
    action_type: str | None = "apply_resolved_candidate",
    candidate_id: str | None = None,
    expected_util: float | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "actionable": bool(enabled),
        "action_type": action_type if enabled else None,
        "family": family,
        "updates": dict(updates or {}),
        "preview_pass": bool(enabled),
        "expected_util": expected_util,
        "blocking_reason": reason if not enabled else None,
        "source_candidate_id": candidate_id,
        "candidate_id": candidate_id,
    }


def _contract_summary(contract: Any) -> dict[str, Any]:
    contract_d = dict(contract or {}) if isinstance(contract, dict) else {}
    return {
        "present": bool(contract_d),
        "enabled": bool(contract_d.get("enabled")),
        "actionable": bool(contract_d.get("actionable")),
        "action_type": contract_d.get("action_type"),
        "family": contract_d.get("family"),
        "updates": dict(contract_d.get("updates") or {}),
        "updates_hash": _stable_hash(contract_d.get("updates") or {}),
        "candidate_id": contract_d.get("candidate_id"),
        "source_candidate_id": contract_d.get("source_candidate_id"),
        "expected_util": contract_d.get("expected_util"),
        "disabled_reason": contract_d.get("blocking_reason") or contract_d.get("disabled_reason"),
        "hash": _stable_hash(contract_d),
    }


def _item_summary(item: Any) -> dict[str, Any]:
    item_d = dict(item or {}) if isinstance(item, dict) else {}
    contract = dict(item_d.get("button_contract") or {})
    payload = dict(item_d.get("action_payload") or {})
    resolved = dict(item_d.get("resolved_candidate") or {})
    evidence = dict(item_d.get("candidate_search_evidence") or {})
    return {
        "id": item_d.get("id"),
        "family": item_d.get("family") or item_d.get("check_key"),
        "title": item_d.get("title_main") or item_d.get("title"),
        "status": item_d.get("status"),
        "identity_hash": _stable_hash(item_d),
        "button_contract": _contract_summary(contract),
        "action_type": item_d.get("action_type") or payload.get("action_type"),
        "action_payload_hash": _stable_hash(payload),
        "resolved_candidate_hash": _stable_hash(resolved),
        "evidence_hash": _stable_hash(evidence),
        "selected_action_updates": dict(item_d.get("selected_action_updates") or {}),
        "updates": dict(item_d.get("updates") or {}),
        "candidate_id": item_d.get("candidate_id")
        or payload.get("candidate_id")
        or resolved.get("candidate_id"),
        "source_candidate_id": item_d.get("source_candidate_id")
        or payload.get("source_candidate_id")
        or resolved.get("source_candidate_id"),
    }


def _action_payload_summary(payload: Any) -> dict[str, Any]:
    payload_d = dict(payload or {}) if isinstance(payload, dict) else {}
    updates = dict(
        payload_d.get("updates")
        or payload_d.get("resolved_candidate_updates")
        or payload_d.get("selected_action_updates")
        or {}
    )
    return {
        "action_type": payload_d.get("action_type") or payload_d.get("resolved_candidate_action_type"),
        "updates": dict(updates),
        "updates_hash": _stable_hash(updates),
        "candidate_id": payload_d.get("candidate_id"),
        "source_candidate_id": payload_d.get("source_candidate_id"),
        "family": payload_d.get("family") or payload_d.get("resolved_candidate_family_tag"),
        "payload_hash": _stable_hash(payload_d),
    }


def _source_matrix(
    *,
    item: dict[str, Any] | None = None,
    debug: dict[str, Any] | None = None,
    session_contract: dict[str, Any] | None = None,
    evidence_contract: dict[str, Any] | None = None,
    intent_contract: dict[str, Any] | None = None,
    publication_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    debug_d = dict(debug or {})
    return {
        "item_contract": _contract_summary((item or {}).get("button_contract") if isinstance(item, dict) else {}),
        "debug_displayed_primary_button_contract": _contract_summary(
            debug_d.get("displayed_primary_button_contract")
        ),
        "debug_primary_button_contract": _contract_summary(debug_d.get("primary_button_contract")),
        "debug_button_contract": _contract_summary(debug_d.get("button_contract")),
        "session_primary_contract": _contract_summary(session_contract or {}),
        "evidence_rehydration_source": _contract_summary(evidence_contract or {}),
        "intent_row_fallback_source": _contract_summary(intent_contract or {}),
        "publication_recovery_source": _contract_summary(publication_contract or {}),
    }


def _add_typed_resolution(module: Any, row: dict[str, Any]) -> dict[str, Any]:
    final_item = dict(row.get("final_published_item") or {})
    source_candidates = copy.deepcopy(dict(row.get("source_candidates") or {}))
    source_records = module._build_design_guide_button_contract_source_records(
        displayed_primary_item=dict(row.get("displayed_primary_item") or final_item),
        primary_item=dict(row.get("primary_item") or final_item),
        guidance_debug=dict(row.get("guidance_debug") or row.get("debug_fields") or {}),
        pending_recommendation=dict(row.get("pending_recommendation") or {}),
        apply_payload_session_keys=dict(row.get("apply_payload_session_keys") or {}),
        button_contract_session_keys=dict(row.get("button_contract_session_keys") or {}),
        source_candidates=source_candidates,
        publication_recovery_sources=dict(row.get("publication_recovery_sources") or {}),
    )
    selector_kwargs = {
        "source_records": source_records,
        "button_contract_source_precedence_order": cta_button_source_precedence_order(),
        "payload_source_precedence_order": cta_payload_source_precedence_order(),
        "candidate_source_keys": cta_candidate_source_keys(),
        "source_payload_labels": cta_source_payload_labels(),
    }
    selector_resolution = module._select_design_guide_button_contract_source_precedence(**selector_kwargs)
    resolution = module._resolve_design_guide_button_contract_source_precedence(
        final_published_item=final_item,
        source_candidates=source_candidates,
        winning_button_contract_source=str(row.get("winning_button_contract_source") or ""),
        winning_update_payload_source=str(row.get("winning_update_payload_source") or ""),
        winning_action_type_source=str(row.get("winning_action_type_source") or ""),
        winning_candidate_source=str(row.get("winning_candidate_source") or ""),
        apply_state=dict(row.get("apply_state") or {}),
        final_cta_action_payload=dict(row.get("final_cta_action_payload") or {}),
        **selector_kwargs,
    )
    out = dict(row)
    out["typed_source_resolution"] = asdict(resolution)
    out["typed_selector_resolution"] = asdict(selector_resolution)
    out["typed_source_records"] = asdict(source_records)
    return out


@contextmanager
def _patched(module: Any, replacements: dict[str, Any]):
    old_values: dict[str, Any] = {}
    missing: set[str] = set()
    for name, value in replacements.items():
        if hasattr(module, name):
            old_values[name] = getattr(module, name)
        else:
            missing.add(name)
        setattr(module, name, value)
    try:
        yield
    finally:
        for name in replacements:
            if name in old_values:
                setattr(module, name, old_values[name])
            elif name in missing:
                delattr(module, name)


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 600.0,
        "L": 6000.0,
        "fc": 40.0,
        "fsy": 500.0,
        "uls_Mstar": 210.0,
        "uls_Vstar": 260.0,
        "bot1_count": 4,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 220,
    }


def _publication_item(
    *,
    item_id: str,
    family: str,
    contract: dict[str, Any],
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updates = dict(contract.get("updates") or {})
    candidate_id = contract.get("candidate_id") or contract.get("source_candidate_id")
    return {
        "id": item_id,
        "family": family,
        "check_key": family,
        "title_main": f"Synthetic {family} CTA source precedence",
        "title": f"Synthetic {family} CTA source precedence",
        "status": "WARN" if contract.get("enabled") else "FAIL",
        "guidance_intent": "required_fix",
        "primary_card_actionable": bool(contract.get("enabled")),
        "final_state_class": "action" if contract.get("enabled") else "blocked",
        "action_type": contract.get("action_type"),
        "button_contract": dict(contract),
        "updates": dict(updates),
        "selected_action_updates": dict(updates),
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "candidate_search_evidence": dict(evidence or {}),
        "action_payload": {
            "action_type": contract.get("action_type"),
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "candidate_search_evidence": dict(evidence or {}),
        },
        "resolved_candidate": {
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "family": family,
            "updates": dict(updates),
            "candidate_search_evidence": dict(evidence or {}),
        },
    }


def _run_contract_rebound_scenario(module: Any, trace_path: Path) -> dict[str, Any]:
    from tools.verification import compute_late_contract_rebound_source_precedence_snapshot as rebound

    previous_env = {
        key: os.environ.get(key)
        for key in (
            "DESIGN_GUIDE_RUNTIME_TRACE",
            "DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO",
            "DESIGN_GUIDE_RUNTIME_TRACE_PATH",
        )
    }
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE"] = "1"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_SCENARIO"] = "CTA_BUTTON_SOURCE_PRECEDENCE_REBOUND"
    os.environ["DESIGN_GUIDE_RUNTIME_TRACE_PATH"] = str(trace_path)
    try:
        output = rebound._run_scenario(module)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    output_items = list(output.get("guidance_items") or []) if isinstance(output, dict) else []
    primary = output_items[0] if output_items and isinstance(output_items[0], dict) else {}
    debug = dict(output.get("debug_trace") or {}) if isinstance(output, dict) else {}
    final_contract = dict(primary.get("button_contract") or {})
    initial_item = rebound._item(rebound._candidate_search_evidence(), rebound._disabled_contract())
    evidence_contract = dict(final_contract)
    session_contract = {}
    try:
        session_contract = dict(module.st.session_state.get("design_guide_primary_button_contract") or {})
    except Exception:
        session_contract = {}

    return {
        "scenario": "compute_contract_rebound",
        "status": "PASS",
        "source_candidates": _source_matrix(
            item=initial_item,
            debug={
                "primary_button_contract": rebound._disabled_contract(),
                "button_contract": rebound._disabled_contract(),
            },
            session_contract=session_contract,
            evidence_contract=evidence_contract,
        ),
        "winning_button_contract_source": "evidence_rehydration_source",
        "winning_update_payload_source": "candidate_search_evidence.best_safe_candidate_updates",
        "winning_action_type_source": "rebuilt_late_evidence_contract",
        "winning_candidate_source": "candidate_search_evidence.selected_candidate_id",
        "apply_state": {
            "enabled": bool(final_contract.get("enabled")),
            "actionable": bool(final_contract.get("actionable")),
            "disabled_reason": final_contract.get("blocking_reason") or final_contract.get("disabled_reason"),
        },
        "displayed_primary_item": copy.deepcopy(primary),
        "primary_item": copy.deepcopy(initial_item),
        "guidance_debug": {
            "primary_button_contract": rebound._disabled_contract(),
            "button_contract": rebound._disabled_contract(),
            **dict(debug),
        },
        "pending_recommendation": {},
        "apply_payload_session_keys": {},
        "button_contract_session_keys": {
            "design_guide_primary_button_contract": dict(session_contract),
        },
        "publication_recovery_sources": {
            "evidence_rehydration_contract": _contract_summary(evidence_contract),
        },
        "final_cta_action_payload": dict(primary.get("action_payload") or {}),
        "final_published_item": _item_summary(primary),
        "debug_fields": {
            "selected_action_type": debug.get("selected_action_type"),
            "selected_action_updates": dict(debug.get("selected_action_updates") or {}),
            "button_contract_enabled": debug.get("button_contract_enabled"),
            "button_contract_updates": dict(debug.get("button_contract_updates") or {}),
            "late_evidence_cleanup_contract_rebound": bool(
                debug.get("late_evidence_cleanup_contract_rebound")
            ),
        },
    }


def _run_intent_row_fallback_scenario(module: Any) -> dict[str, Any]:
    state = _base_state()
    item_contract = _contract(
        family="shear",
        updates={},
        enabled=False,
        action_type=None,
        candidate_id=None,
        reason="Synthetic disabled item contract before intent fallback.",
    )
    item = _publication_item(
        item_id="synthetic_cta_intent_fallback_primary",
        family="shear",
        contract=item_contract,
        evidence={"family": "shear", "search_scope": "synthetic_cta_source_precedence_intent"},
    )
    intent_updates = {"s_lig": 150}
    intent_contract = _contract(
        family="shear",
        updates=intent_updates,
        enabled=True,
        candidate_id="synthetic_intent_row_candidate",
        expected_util=0.91,
    )
    debug = {
        "button_contract": _contract(
            family="shear",
            updates={},
            enabled=False,
            action_type=None,
            reason="Synthetic disabled debug button contract.",
        ),
        "primary_button_contract": _contract(
            family="shear",
            updates={},
            enabled=False,
            action_type=None,
            reason="Synthetic disabled debug primary contract.",
        ),
        "displayed_primary_button_contract": _contract(
            family="shear",
            updates={},
            enabled=False,
            action_type=None,
            reason="Synthetic disabled displayed contract.",
        ),
        "displayed_guidance_intent_items": [
            {
                "title": "Synthetic intent-row fallback",
                "check_key": "shear",
                "action_type": "apply_resolved_candidate",
                "button_contract": dict(intent_contract),
            }
        ],
    }
    session_contract = _contract(
        family="shear",
        updates={"s_lig": 175},
        enabled=True,
        candidate_id="synthetic_session_candidate",
        expected_util=0.93,
    )
    try:
        module.st.session_state["design_guide_primary_button_contract"] = dict(session_contract)
        module.st.session_state["design_guide_primary_button_contract_enabled"] = True
    except Exception:
        pass

    with _patched(module, {"_bending_fail_publication_snapshot_for_state": lambda *a, **k: None}):
        out = module._publish_final_visible_design_guide_contract_binding(
            item=copy.deepcopy(item),
            state=dict(state),
            debug_sink=debug,
            rec={},
        )
    final_contract = dict(out.get("button_contract") or {})
    return {
        "scenario": "publication_intent_row_fallback",
        "status": "PASS",
        "source_candidates": _source_matrix(
            item=item,
            debug=debug,
            session_contract=session_contract,
            intent_contract=intent_contract,
        ),
        "winning_button_contract_source": "intent_row_fallback_source",
        "winning_update_payload_source": "intent_row_contract.updates",
        "winning_action_type_source": "intent_row_contract.action_type",
        "winning_candidate_source": "intent_row_contract.candidate_id",
        "apply_state": {
            "enabled": bool(final_contract.get("enabled")),
            "actionable": bool(final_contract.get("actionable")),
            "disabled_reason": final_contract.get("blocking_reason") or final_contract.get("disabled_reason"),
        },
        "displayed_primary_item": copy.deepcopy(out),
        "primary_item": copy.deepcopy(item),
        "guidance_debug": dict(debug),
        "pending_recommendation": {},
        "apply_payload_session_keys": {},
        "button_contract_session_keys": {
            "design_guide_primary_button_contract": dict(session_contract),
        },
        "publication_recovery_sources": {
            "intent_contract": _contract_summary(intent_contract),
        },
        "final_cta_action_payload": dict(out.get("action_payload") or {}),
        "final_published_item": _item_summary(out),
        "debug_fields": {
            "final_binding_intent_contract_preferred": bool(
                debug.get("final_binding_intent_contract_preferred")
            ),
            "button_contract_updates": dict(debug.get("button_contract_updates") or {}),
            "selected_action_updates": dict(debug.get("selected_action_updates") or {}),
            "button_contract_enabled": debug.get("button_contract_enabled"),
        },
    }


def _run_publication_recovery_scenario(module: Any) -> dict[str, Any]:
    state = _base_state()
    item_contract = _contract(
        family="bending",
        updates={},
        enabled=False,
        action_type=None,
        reason="Synthetic disabled item contract before publication recovery.",
    )
    item = _publication_item(
        item_id="synthetic_cta_publication_recovery_primary",
        family="bending",
        contract=item_contract,
        evidence={"family": "bending", "search_scope": "synthetic_cta_source_precedence_recovery"},
    )
    recovery_updates = {"bot1_count": 5}
    recovery_contract = _contract(
        family="bending",
        updates=recovery_updates,
        enabled=True,
        candidate_id="synthetic_publication_recovery_candidate",
        expected_util=0.9,
    )
    recovery_item = _publication_item(
        item_id="synthetic_publication_recovery_item",
        family="bending",
        contract=recovery_contract,
        evidence={"family": "bending", "search_scope": "synthetic_publication_recovery_source"},
    )
    debug = {
        "button_contract": dict(item_contract),
        "primary_button_contract": dict(item_contract),
        "displayed_primary_button_contract": dict(item_contract),
    }

    def _snapshot_for_state(*_: Any, debug_sink: dict | None = None, **__: Any) -> dict[str, Any]:
        if isinstance(debug_sink, dict):
            debug_sink["bending_fail_publication_snapshot_hit"] = True
        return copy.deepcopy(recovery_item)

    with _patched(module, {"_bending_fail_publication_snapshot_for_state": _snapshot_for_state}):
        out = module._publish_final_visible_design_guide_contract_binding(
            item=copy.deepcopy(item),
            state=dict(state),
            debug_sink=debug,
            rec={},
        )
    final_contract = dict(out.get("button_contract") or {})
    return {
        "scenario": "publication_recovery_snapshot",
        "status": "PASS",
        "source_candidates": _source_matrix(
            item=item,
            debug=debug,
            publication_contract=recovery_contract,
        ),
        "winning_button_contract_source": "publication_recovery_source",
        "winning_update_payload_source": "publication_recovery_source.updates",
        "winning_action_type_source": "publication_recovery_source.action_type",
        "winning_candidate_source": "publication_recovery_source.candidate_id",
        "apply_state": {
            "enabled": bool(final_contract.get("enabled")),
            "actionable": bool(final_contract.get("actionable")),
            "disabled_reason": final_contract.get("blocking_reason") or final_contract.get("disabled_reason"),
        },
        "displayed_primary_item": copy.deepcopy(out),
        "primary_item": copy.deepcopy(item),
        "guidance_debug": dict(debug),
        "pending_recommendation": {},
        "apply_payload_session_keys": {},
        "button_contract_session_keys": {},
        "publication_recovery_sources": {
            "publication_recovery_contract": _contract_summary(recovery_contract),
            "publication_recovery_item": _item_summary(recovery_item),
        },
        "final_cta_action_payload": dict(out.get("action_payload") or {}),
        "final_published_item": _item_summary(out),
        "debug_fields": {
            "bending_fail_publication_snapshot_reused": bool(
                debug.get("bending_fail_publication_snapshot_reused")
            ),
            "bending_fail_publication_snapshot_hit": bool(debug.get("bending_fail_publication_snapshot_hit")),
            "button_contract_updates": dict(debug.get("button_contract_updates") or {}),
            "selected_action_updates": dict(debug.get("selected_action_updates") or {}),
            "button_contract_enabled": debug.get("button_contract_enabled"),
        },
    }


def _validate_scenarios(scenarios: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    by_name = {str(row.get("scenario")): row for row in scenarios}
    expected_winners = cta_focused_scenario_expected_winners()
    for name, winner in expected_winners.items():
        row = by_name.get(name)
        if not row:
            failures.append(f"missing_scenario:{name}")
            continue
        if row.get("winning_button_contract_source") != winner:
            failures.append(f"{name}:winner:{row.get('winning_button_contract_source')}")
        if not (row.get("apply_state") or {}).get("enabled"):
            failures.append(f"{name}:apply_not_enabled")
        item_hash = ((row.get("final_published_item") or {}).get("identity_hash") or "")
        if not item_hash:
            failures.append(f"{name}:missing_final_item_hash")
        typed = dict(row.get("typed_source_resolution") or {})
        if not typed:
            failures.append(f"{name}:missing_typed_source_resolution")
            continue
        selector_typed = dict(row.get("typed_selector_resolution") or {})
        if not selector_typed:
            failures.append(f"{name}:missing_typed_selector_resolution")
        elif selector_typed != typed:
            failures.append(f"{name}:typed_selector_resolution_mismatch")
        missing_proof = [field for field in required_cta_proof_fields() if field not in typed]
        failures.extend(f"{name}:missing_required_proof_field:{field}" for field in missing_proof)
        final_item = dict(row.get("final_published_item") or {})
        final_contract = dict(final_item.get("button_contract") or {})
        final_updates = dict(final_contract.get("updates") or final_item.get("selected_action_updates") or {})
        apply_state = dict(row.get("apply_state") or {})
        if typed.get("winning_button_contract_source") != row.get("winning_button_contract_source"):
            failures.append(f"{name}:typed_contract_source_mismatch")
        if typed.get("winning_update_payload_source") != row.get("winning_update_payload_source"):
            failures.append(f"{name}:typed_update_source_mismatch")
        if typed.get("winning_update_payload") != final_updates:
            failures.append(f"{name}:typed_update_payload_mismatch")
        if typed.get("winning_action_type") != final_item.get("action_type"):
            failures.append(f"{name}:typed_action_type_mismatch")
        if typed.get("winning_action_type_source") != row.get("winning_action_type_source"):
            failures.append(f"{name}:typed_action_type_source_mismatch")
        typed_candidate = dict(typed.get("winning_candidate") or {})
        if typed_candidate.get("candidate_id") != final_item.get("candidate_id"):
            failures.append(f"{name}:typed_candidate_id_mismatch")
        if typed_candidate.get("source_candidate_id") != final_item.get("source_candidate_id"):
            failures.append(f"{name}:typed_source_candidate_id_mismatch")
        if typed.get("winning_candidate_source") != row.get("winning_candidate_source"):
            failures.append(f"{name}:typed_candidate_source_mismatch")
        if bool(typed.get("apply_enabled")) != bool(apply_state.get("enabled")):
            failures.append(f"{name}:typed_apply_enabled_mismatch")
        if bool(typed.get("apply_actionable")) != bool(apply_state.get("actionable")):
            failures.append(f"{name}:typed_apply_actionable_mismatch")
        if typed.get("disabled_reason") != apply_state.get("disabled_reason"):
            failures.append(f"{name}:typed_disabled_reason_mismatch")
        if typed.get("final_published_item_hash") != item_hash:
            failures.append(f"{name}:typed_final_item_hash_mismatch")
        if typed.get("source_candidates") != row.get("source_candidates"):
            failures.append(f"{name}:typed_source_candidates_mismatch")
        source_records = dict(row.get("typed_source_records") or {})
        if not source_records:
            failures.append(f"{name}:missing_typed_source_records")
            continue
        missing_records = [field for field in required_cta_source_record_fields() if field not in source_records]
        failures.extend(f"{name}:missing_required_source_record_field:{field}" for field in missing_records)
        if source_records.get("source_candidates") != row.get("source_candidates"):
            failures.append(f"{name}:source_records_source_candidates_mismatch")
        if source_records.get("source_candidates") != typed.get("source_candidates"):
            failures.append(f"{name}:source_records_typed_resolution_source_candidates_mismatch")
        if source_records.get("displayed_primary_item") != row.get("displayed_primary_item"):
            failures.append(f"{name}:source_records_displayed_primary_item_mismatch")
        if source_records.get("primary_item") != row.get("primary_item"):
            failures.append(f"{name}:source_records_primary_item_mismatch")
        if source_records.get("guidance_debug") != row.get("guidance_debug"):
            failures.append(f"{name}:source_records_guidance_debug_mismatch")
        if source_records.get("pending_recommendation") != row.get("pending_recommendation"):
            failures.append(f"{name}:source_records_pending_recommendation_mismatch")
        if source_records.get("apply_payload_session_keys") != row.get("apply_payload_session_keys"):
            failures.append(f"{name}:source_records_apply_payload_session_mismatch")
        if source_records.get("button_contract_session_keys") != row.get("button_contract_session_keys"):
            failures.append(f"{name}:source_records_button_contract_session_mismatch")
        if source_records.get("publication_recovery_sources") != row.get("publication_recovery_sources"):
            failures.append(f"{name}:source_records_publication_recovery_mismatch")
        records_candidate_sources = dict(source_records.get("candidate_sources") or {})
        if records_candidate_sources.get("displayed_primary_candidate_id") != final_item.get("candidate_id"):
            failures.append(f"{name}:source_records_displayed_candidate_id_mismatch")
        if (
            records_candidate_sources.get("displayed_primary_source_candidate_id")
            != final_item.get("source_candidate_id")
        ):
            failures.append(f"{name}:source_records_displayed_source_candidate_id_mismatch")
        records_update_sources = dict(source_records.get("update_payload_sources") or {})
        if (
            dict(records_update_sources.get("displayed_primary_button_contract_updates") or {})
            != dict(final_contract.get("updates") or {})
        ):
            failures.append(f"{name}:source_records_displayed_contract_updates_mismatch")
        records_action_sources = dict(source_records.get("action_payload_sources") or {})
        if (
            dict(records_action_sources.get("displayed_primary_action_payload") or {})
            != dict((row.get("displayed_primary_item") or {}).get("action_payload") or {})
        ):
            failures.append(f"{name}:source_records_displayed_action_payload_mismatch")
    intent = by_name.get("publication_intent_row_fallback") or {}
    if not (intent.get("debug_fields") or {}).get("final_binding_intent_contract_preferred"):
        failures.append("intent_row_fallback_not_recorded")
    rebound = by_name.get("compute_contract_rebound") or {}
    if not (rebound.get("debug_fields") or {}).get("late_evidence_cleanup_contract_rebound"):
        failures.append("contract_rebound_not_recorded")
    recovery = by_name.get("publication_recovery_snapshot") or {}
    if not (recovery.get("debug_fields") or {}).get("bending_fail_publication_snapshot_reused"):
        failures.append("publication_recovery_not_recorded")
    required_source_keys = set(cta_candidate_source_keys())
    observed_keys: set[str] = set()
    for row in scenarios:
        matrix = dict(row.get("source_candidates") or {})
        observed_keys.update(key for key, value in matrix.items() if (value or {}).get("present"))
    missing_sources = sorted(required_source_keys - observed_keys)
    if missing_sources:
        failures.append(f"missing_candidate_sources:{','.join(missing_sources)}")
    return failures


def _write_audit_report(path: Path, snapshot: dict[str, Any]) -> None:
    lines = [
        "# CTA/Button Source-Precedence Snapshot",
        "",
        f"Status: {snapshot['status']}",
        "",
        "## Scope",
        "",
        "- Coverage only.",
        "- No extraction performed.",
        "- No product behaviour changes intended.",
        "- Serviceability fallback and locked family internals were not touched.",
        "",
        "## Artifacts",
        "",
        f"- Snapshot artifact: `{snapshot['snapshot_path']}`",
        f"- Trace artifact: `{snapshot['trace_path']}`",
        "",
        "## Candidate Source Coverage",
        "",
        "```json",
        json.dumps(snapshot["candidate_source_coverage"], indent=2, sort_keys=True),
        "```",
        "",
        "## Scenario Winners",
        "",
        "```json",
        json.dumps(snapshot["scenario_winners"], indent=2, sort_keys=True),
        "```",
        "",
        "## Decision",
        "",
        (
            "PROVEN: the focused snapshot records the full CTA/button source chain needed before movement."
            if snapshot["status"] == "PASS"
            else "NOT_PROVEN: do not move CTA/button source precedence."
        ),
        "",
        "## Next Move",
        "",
        (
            "Audit a page-local `_resolve_design_guide_button_contract_source_precedence(...)` boundary, then type it before extraction."
            if snapshot["status"] == "PASS"
            else "Repair the focused snapshot or add missing source coverage before any extraction."
        ),
        "",
    ]
    if snapshot.get("failures"):
        lines.extend(["## Failures", "", "```json", json.dumps(snapshot["failures"], indent=2), "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    import importlib

    module = importlib.import_module("inputs_page")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    output_path = ARTIFACT_DIR / f"compute_cta_button_source_precedence_snapshot_{stamp}.json"
    audit_path = AUDIT_DIR / f"compute_cta_button_source_precedence_snapshot_{stamp}.md"
    trace_path = TRACE_DIR / f"compute_cta_button_source_precedence_trace_{stamp}.jsonl"

    scenarios = [
        _run_contract_rebound_scenario(module, trace_path),
        _run_intent_row_fallback_scenario(module),
        _run_publication_recovery_scenario(module),
    ]
    scenarios = [_add_typed_resolution(module, row) for row in scenarios]
    failures = _validate_scenarios(scenarios)
    candidate_source_coverage: dict[str, bool] = {}
    for row in scenarios:
        for key, value in dict(row.get("source_candidates") or {}).items():
            candidate_source_coverage[key] = bool(candidate_source_coverage.get(key) or (value or {}).get("present"))
    snapshot = {
        "schema": "compute_cta_button_source_precedence_snapshot.v1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "snapshot_path": str(output_path),
        "audit_path": str(audit_path),
        "trace_path": str(trace_path),
        "contract_path": str(_CTA_CONTRACT.CONTRACT_PATH),
        "contract_source_precedence_order": list(cta_button_source_precedence_order()),
        "contract_payload_source_precedence_order": {
            key: list(value) for key, value in cta_payload_source_precedence_order().items()
        },
        "required_proof_fields": list(required_cta_proof_fields()),
        "required_source_record_fields": list(required_cta_source_record_fields()),
        "allowed_cta_states": list(allowed_cta_states()),
        "required_gates": list(required_cta_gates()),
        "candidate_source_coverage": candidate_source_coverage,
        "scenario_winners": {
            str(row.get("scenario")): {
                "winning_button_contract_source": row.get("winning_button_contract_source"),
                "winning_update_payload_source": row.get("winning_update_payload_source"),
                "winning_action_type_source": row.get("winning_action_type_source"),
                "winning_candidate_source": row.get("winning_candidate_source"),
                "apply_state": row.get("apply_state"),
                "final_published_item": row.get("final_published_item"),
                "typed_source_resolution": row.get("typed_source_resolution"),
                "typed_selector_resolution": row.get("typed_selector_resolution"),
                "typed_source_records": row.get("typed_source_records"),
            }
            for row in scenarios
        },
        "scenarios": scenarios,
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_audit_report(audit_path, snapshot)
    print(f"{snapshot['status']}: {output_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
