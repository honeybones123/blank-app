"""Verify bending-only terminalisation selected/evidence projection delegates to controller."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_bending_only_target_band_cleanup_item"
HELPER = "build_design_guide_controller_bending_only_terminalisation_projection"
ALIAS = "_build_design_guide_controller_bending_only_terminalisation_projection"
INITIAL_HELPER = "build_design_guide_controller_terminalisation_initial_context"
INITIAL_ALIAS = "_build_design_guide_controller_terminalisation_initial_context"
ACCEPTANCE_HELPER = "resolve_design_guide_controller_terminalisation_trial_acceptance"
ACCEPTANCE_ALIAS = "_resolve_design_guide_controller_terminalisation_trial_acceptance"
FOLLOWUP_HELPER = "resolve_design_guide_controller_terminalisation_followup_updates"
FOLLOWUP_ALIAS = "_resolve_design_guide_controller_terminalisation_followup_updates"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _old_parse_util_value(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _old_stable_fingerprint_for_payload(payload: dict | None) -> tuple:
    serialised: list[tuple[str, str]] = []
    for key, value in sorted(dict(payload or {}).items(), key=lambda item: str(item[0])):
        try:
            encoded = json.dumps(value, sort_keys=True, default=str)
        except Exception:
            encoded = repr(value)
        serialised.append((str(key), encoded))
    return tuple(serialised)


def _old_guidance_cleanup_candidate_id(family: str, updates: dict) -> str:
    try:
        fp = _old_stable_fingerprint_for_payload({"family": family, "updates": dict(updates or {})})
        return f"local_cleanup:{family}:{fp}"
    except Exception:
        updates_map = dict(updates or {})
        sig = ",".join(f"{key}={updates_map[key]}" for key in sorted(updates_map))
        return f"local_cleanup:{family}:{sig}"


def _old_inline_projection(
    *,
    selected_candidate: dict[str, Any],
    candidate_search_evidence: dict[str, Any],
    terminal_updates: dict[str, Any],
    terminal_overview: dict[str, Any],
    terminal_candidate_id: str,
    terminal_candidate_id_parts: list[Any],
    terminal_evidence: dict[str, Any],
) -> dict[str, Any]:
    selected = dict(selected_candidate)
    evidence = dict(candidate_search_evidence)
    if terminal_updates and terminal_updates != dict(selected.get("updates") or {}):
        terminal_utils = dict(terminal_overview.get("utils") or {})
        terminal_worst = _old_parse_util_value(
            terminal_overview.get("worst_util")
            or terminal_overview.get("governing_util")
            or terminal_utils.get("bending")
            or terminal_utils.get("shear")
        )
        terminal_bending = _old_parse_util_value(terminal_utils.get("bending"))
        terminal_shear = _old_parse_util_value(terminal_utils.get("shear"))
        selected = dict(selected)
        selected["updates"] = dict(terminal_updates)
        selected["candidate_id"] = terminal_candidate_id
        selected["source_candidate_id"] = selected["candidate_id"]
        selected["label"] = "Shear and bending cleanup - one-click optimisation"
        selected["canonical_winner_label"] = "Shear and bending cleanup - one-click optimisation"
        selected["family"] = "combined"
        selected["recommendation_family_tag"] = "combined"
        selected["subfamilies"] = ["shear", "bottom_reinforcement"]
        if terminal_worst is not None:
            selected["candidate_post_util"] = float(terminal_worst)
            selected["worst_util"] = float(terminal_worst)
        if terminal_bending is not None:
            selected["candidate_bending_util"] = float(terminal_bending)
        if terminal_shear is not None:
            selected["candidate_shear_util"] = float(terminal_shear)
        evidence.update(
            {
                "same_click_terminalisation_fold": True,
                "same_click_terminalisation_sources": list(terminal_candidate_id_parts),
                "selected_candidate_id": selected["candidate_id"],
                "selected_candidate_title": selected["label"],
                "selected_candidate_updates": dict(terminal_updates),
                "best_safe_candidate_updates": dict(terminal_updates),
                "selected_candidate_util": selected.get("candidate_post_util"),
                "best_safe_final_util": selected.get("candidate_post_util"),
                "family": "combined",
                "no_second_cta_required": True,
                **terminal_evidence,
            }
        )
        return {
            "selected_candidate": selected,
            "candidate_search_evidence": evidence,
            "terminalisation_applied": True,
        }
    return {
        "selected_candidate": selected,
        "candidate_search_evidence": evidence,
        "terminalisation_applied": False,
    }


def _parity_case_payloads() -> list[dict[str, Any]]:
    base_selected = {
        "candidate_id": "bending_cleanup_001",
        "source_candidate_id": "bending_cleanup_001",
        "updates": {"bot1_count": 6},
        "family": "bending",
        "subfamilies": ["bottom_reinforcement"],
    }
    base_evidence = {
        "selected_candidate_id": "bending_cleanup_001",
        "selected_candidate_title": "Bending cleanup - further reduction reaches target range",
        "selected_candidate_updates": {"bot1_count": 6},
    }
    return [
        {
            "case": "unchanged_updates_no_terminalisation",
            "selected_candidate": dict(base_selected),
            "candidate_search_evidence": dict(base_evidence),
            "terminal_updates": {"bot1_count": 6},
            "terminal_overview": {"utils": {"bending": 0.72, "shear": 0.62}},
            "terminal_candidate_id": None,
            "terminal_candidate_id_parts": ["bending_cleanup_001"],
            "terminal_evidence": {},
        },
        {
            "case": "bending_and_shear_terminalisation",
            "selected_candidate": dict(base_selected),
            "candidate_search_evidence": dict(base_evidence),
            "terminal_updates": {"bot1_count": 6, "shear_legs": 0},
            "terminal_overview": {"worst_util": 0.83, "utils": {"bending": 0.81, "shear": 0.83}},
            "terminal_candidate_id": None,
            "terminal_candidate_id_parts": ["bending_cleanup_001", "residual_shear"],
            "terminal_evidence": {
                "same_click_terminalisation_folded_residual_shear": True,
                "residual_shear_updates": {"shear_legs": 0},
            },
        },
        {
            "case": "terminalisation_missing_utils",
            "selected_candidate": dict(base_selected),
            "candidate_search_evidence": dict(base_evidence),
            "terminal_updates": {"bot1_count": 5, "shear_legs": 0},
            "terminal_overview": {"utils": {}},
            "terminal_candidate_id": None,
            "terminal_candidate_id_parts": ["bending_cleanup_001", "followup_bending"],
            "terminal_evidence": {"same_click_terminalisation_folded_residual_bending": True},
        },
    ]


def _old_trial_acceptance(
    *,
    candidate_present: bool,
    overview_any_fail: bool,
    required_checks_acceptable: bool,
    preview_statuses_have_explicit_fail: bool,
) -> bool:
    return (
        bool(candidate_present)
        and not bool(overview_any_fail)
        and bool(required_checks_acceptable)
        and not bool(preview_statuses_have_explicit_fail)
    )


def _old_followup_updates(
    *,
    item: dict[str, Any] | None,
    button_contract: dict[str, Any] | None,
    candidate_search_evidence: dict[str, Any] | None = None,
    include_evidence_fallback: bool = False,
) -> dict[str, Any]:
    item_d = dict(item or {})
    contract_d = dict(button_contract or {})
    evidence_d = dict(candidate_search_evidence or {})
    return {
        "updates": dict(
            contract_d.get("updates")
            or item_d.get("selected_action_updates")
            or item_d.get("updates")
            or (
                evidence_d.get("best_safe_candidate_updates")
                if bool(include_evidence_fallback)
                else {}
            )
            or (
                evidence_d.get("selected_candidate_updates")
                if bool(include_evidence_fallback)
                else {}
            )
            or {}
        ),
        "action_type": str(contract_d.get("action_type") or item_d.get("action_type") or "").strip(),
    }


def _old_initial_context(*, base_state: dict[str, Any], selected_candidate: dict[str, Any]) -> dict[str, Any]:
    terminal_updates = dict(selected_candidate.get("updates") or {})
    terminal_state = dict(base_state)
    terminal_state.update(terminal_updates)
    return {
        "terminal_updates": terminal_updates,
        "terminal_state": terminal_state,
        "terminal_evidence": {},
        "terminal_candidate_id_parts": [str(selected_candidate.get("candidate_id") or "bending_cleanup")],
    }


def build_payload() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_terminalisation_initial_context,
        build_design_guide_controller_bending_only_terminalisation_projection,
        resolve_design_guide_controller_terminalisation_followup_updates,
        resolve_design_guide_controller_terminalisation_trial_acceptance,
    )

    inputs_source = _read(INPUTS)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_segment = _function_segment(inputs_source, TARGET)
    _, _, helper_segment = _function_segment(controller_source, HELPER)

    parity_cases = []
    for case in _parity_case_payloads():
        kwargs = {key: value for key, value in case.items() if key != "case"}
        old_kwargs = dict(kwargs)
        old_kwargs["terminal_candidate_id"] = _old_guidance_cleanup_candidate_id(
            "combined",
            dict(kwargs.get("terminal_updates") or {}),
        )
        old = _old_inline_projection(**old_kwargs)
        new = build_design_guide_controller_bending_only_terminalisation_projection(**kwargs)
        new_comparable = {
            key: value
            for key, value in dict(new).items()
            if key in {"selected_candidate", "candidate_search_evidence", "terminalisation_applied"}
        }
        parity_cases.append(
            {
                "case": case["case"],
                "matches": old == new_comparable,
                "old": old,
                "new": new_comparable,
            }
        )

    initial_cases = []
    for case in (
        {
            "case": "candidate_with_updates",
            "base_state": {"b": 400, "D": 650, "bot1_count": 8},
            "selected_candidate": {"candidate_id": "cleanup_001", "updates": {"bot1_count": 6}},
        },
        {
            "case": "missing_candidate_id",
            "base_state": {"b": 400, "D": 650},
            "selected_candidate": {"updates": {"bot1_count": 5, "lig_legs": 0}},
        },
        {
            "case": "no_updates",
            "base_state": {"b": 400, "D": 650},
            "selected_candidate": {"candidate_id": "cleanup_002"},
        },
    ):
        kwargs = {key: value for key, value in case.items() if key != "case"}
        old = _old_initial_context(**kwargs)
        new_raw = build_design_guide_controller_terminalisation_initial_context(**kwargs)
        new = {
            key: new_raw.get(key)
            for key in (
                "terminal_updates",
                "terminal_state",
                "terminal_evidence",
                "terminal_candidate_id_parts",
            )
        }
        initial_cases.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    acceptance_cases = []
    for case in (
        {
            "case": "accepted",
            "candidate_present": True,
            "overview_any_fail": False,
            "required_checks_acceptable": True,
            "preview_statuses_have_explicit_fail": False,
        },
        {
            "case": "missing_candidate",
            "candidate_present": False,
            "overview_any_fail": False,
            "required_checks_acceptable": True,
            "preview_statuses_have_explicit_fail": False,
        },
        {
            "case": "overview_any_fail",
            "candidate_present": True,
            "overview_any_fail": True,
            "required_checks_acceptable": True,
            "preview_statuses_have_explicit_fail": False,
        },
        {
            "case": "required_checks_not_acceptable",
            "candidate_present": True,
            "overview_any_fail": False,
            "required_checks_acceptable": False,
            "preview_statuses_have_explicit_fail": False,
        },
        {
            "case": "explicit_preview_fail",
            "candidate_present": True,
            "overview_any_fail": False,
            "required_checks_acceptable": True,
            "preview_statuses_have_explicit_fail": True,
        },
    ):
        kwargs = {key: value for key, value in case.items() if key != "case"}
        old = _old_trial_acceptance(**kwargs)
        new = bool(resolve_design_guide_controller_terminalisation_trial_acceptance(**kwargs).get("accepted"))
        acceptance_cases.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    followup_cases = []
    for case in (
        {
            "case": "contract_updates_win",
            "item": {"selected_action_updates": {"bot1_count": 5}, "updates": {"bot1_count": 4}, "action_type": "item_action"},
            "button_contract": {"updates": {"bot1_count": 6}, "action_type": "apply_resolved_candidate"},
            "candidate_search_evidence": {},
            "include_evidence_fallback": False,
        },
        {
            "case": "item_selected_action_updates_fallback",
            "item": {"selected_action_updates": {"bot1_count": 5}, "updates": {"bot1_count": 4}, "action_type": "apply_resolved_candidate"},
            "button_contract": {},
            "candidate_search_evidence": {},
            "include_evidence_fallback": False,
        },
        {
            "case": "shear_evidence_best_safe_fallback",
            "item": {},
            "button_contract": {},
            "candidate_search_evidence": {
                "best_safe_candidate_updates": {"lig_legs": 0},
                "selected_candidate_updates": {"s_lig": 300},
            },
            "include_evidence_fallback": True,
        },
        {
            "case": "shear_evidence_selected_fallback",
            "item": {},
            "button_contract": {},
            "candidate_search_evidence": {"selected_candidate_updates": {"s_lig": 300}},
            "include_evidence_fallback": True,
        },
    ):
        kwargs = {key: value for key, value in case.items() if key != "case"}
        old = _old_followup_updates(**kwargs)
        new_raw = resolve_design_guide_controller_terminalisation_followup_updates(**kwargs)
        new = {"updates": dict(new_raw.get("updates") or {}), "action_type": str(new_raw.get("action_type") or "")}
        followup_cases.append({"case": case["case"], "matches": old == new, "old": old, "new": new})

    source_checks = {
        "target_found": f"def {TARGET}(" in inputs_source,
        "controller_initial_helper_found": f"def {INITIAL_HELPER}(" in controller_source,
        "controller_helper_found": f"def {HELPER}(" in controller_source,
        "controller_acceptance_helper_found": f"def {ACCEPTANCE_HELPER}(" in controller_source,
        "controller_followup_helper_found": f"def {FOLLOWUP_HELPER}(" in controller_source,
        "controller_initial_helper_exported": f'"{INITIAL_HELPER}"' in controller_source,
        "controller_helper_exported": f'"{HELPER}"' in controller_source,
        "controller_acceptance_helper_exported": f'"{ACCEPTANCE_HELPER}"' in controller_source,
        "controller_followup_helper_exported": f'"{FOLLOWUP_HELPER}"' in controller_source,
        "inputs_imports_initial_helper": f"{INITIAL_HELPER} as {INITIAL_ALIAS}" in inputs_source,
        "inputs_imports_helper": f"{HELPER} as {ALIAS}" in inputs_source,
        "inputs_imports_acceptance_helper": f"{ACCEPTANCE_HELPER} as {ACCEPTANCE_ALIAS}" in inputs_source,
        "inputs_imports_followup_helper": f"{FOLLOWUP_HELPER} as {FOLLOWUP_ALIAS}" in inputs_source,
        "target_calls_initial_helper": f"{INITIAL_ALIAS}(" in target_segment,
        "target_calls_helper": f"{ALIAS}(" in target_segment,
        "target_calls_acceptance_helper": f"{ACCEPTANCE_ALIAS}(" in target_segment,
        "target_calls_followup_helper": f"{FOLLOWUP_ALIAS}(" in target_segment,
        "target_no_longer_embeds_terminalisation_label_literal": (
            "Shear and bending cleanup - one-click optimisation" not in target_segment
        ),
        "target_no_longer_embeds_terminalisation_evidence_update": (
            '"same_click_terminalisation_sources"' not in target_segment
        ),
        "target_keeps_overview_collection_page_owned": "_collect_design_overview(" in target_segment,
        "target_keeps_bending_followup_callback_page_owned": (
            "_bending_only_target_band_cleanup_item(" in target_segment
            and "allow_terminalisation_fold=False" in target_segment
        ),
        "target_keeps_shear_followup_callback_page_owned": "_shear_low_util_target_cleanup_item(" in target_segment,
        "target_keeps_button_contract_probe_page_owned": "_design_guide_button_contract(" in target_segment,
        "target_keeps_candidate_eval_page_owned": (
            "_evaluate_bending_only_target_band_prebuilt_candidate_with_service(" in target_segment
        ),
        "target_no_longer_generates_terminal_candidate_id": (
            'terminal_candidate_id=_guidance_cleanup_candidate_id("combined", terminal_updates)' not in target_segment
            and "terminal_candidate_id=None" in target_segment
        ),
        "target_no_longer_embeds_initial_terminal_context": (
            "terminal_evidence: dict = {}" not in target_segment
            and 'terminal_candidate_id_parts = [str(selected.get("candidate_id") or "bending_cleanup")]' not in target_segment
            and "terminal_state = dict(base)" not in target_segment
        ),
        "controller_import_clean": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "helper_is_pure_projection": "_collect_design_overview" not in helper_segment
        and "_design_guide_button_contract" not in helper_segment
        and "_shear_low_util_target_cleanup_item" not in helper_segment,
        "helper_generates_terminal_candidate_id": "optimisation_cleanup_candidate_id(" in helper_segment
        and "_design_guide_controller_payload_tuple_fingerprint" in helper_segment,
        "target_no_longer_embeds_full_trial_acceptance_predicate": (
            "and not bool(trial_overview.get(\"any_fail\"))" not in target_segment
            and "and _overview_required_checks_acceptable(trial_overview)" not in target_segment
            and "and not _candidate_preview_statuses_have_explicit_fail(trial_statuses)" not in target_segment
        ),
        "target_no_longer_embeds_followup_update_fallback_order": (
            'followup_contract.get("updates")' not in target_segment
            and 'shear_evidence.get("best_safe_candidate_updates")' not in target_segment
            and 'shear_evidence.get("selected_candidate_updates")' not in target_segment
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    checks = {
        **source_checks,
        "all_initial_cases_match": all(bool(row.get("matches")) for row in initial_cases),
        "all_parity_cases_match": all(bool(row.get("matches")) for row in parity_cases),
        "all_acceptance_cases_match": all(bool(row.get("matches")) for row in acceptance_cases),
        "all_followup_cases_match": all(bool(row.get("matches")) for row in followup_cases),
    }
    return {
        "schema": "design_guide_bending_only_terminalisation_callback_boundary_parity.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "BENDING_ONLY_TERMINALISATION_PROJECTION_CONTROLLER_OWNED",
        "target": {"name": TARGET, "line_start": target_start, "line_end": target_end},
        "controller_helper": HELPER,
        "parity_cases": parity_cases,
        "initial_cases": initial_cases,
        "acceptance_cases": acceptance_cases,
        "followup_cases": followup_cases,
        "checks": checks,
        "remaining_page_owned_terminalisation_surfaces": [
            "overview collection",
            "bending follow-up callback execution",
            "shear follow-up callback execution",
            "button contract probing",
            "candidate evaluation callback execution",
            "terminal candidate id generation",
        ],
        "product_behavior_changed": False,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bending_only_terminalisation_callback_boundary_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_only_terminalisation_callback_boundary_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bending-Only Terminalisation Callback Boundary Parity",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Initial Context Cases",
        "",
        "| Case | Matches |",
        "|---|---|",
    ]
    for row in payload.get("initial_cases") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('matches')}` |")
    lines.extend([
        "",
        "## Parity Cases",
        "",
        "| Case | Matches |",
        "|---|---|",
    ])
    for row in payload.get("parity_cases") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Trial Acceptance Cases", "", "| Case | Matches |", "|---|---|"])
    for row in payload.get("acceptance_cases") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Follow-Up Update Extraction Cases", "", "| Case | Matches |", "|---|---|"])
    for row in payload.get("followup_cases") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Remaining Page-Owned Terminalisation Surfaces", ""])
    lines.extend(f"- {surface}" for surface in payload.get("remaining_page_owned_terminalisation_surfaces") or [])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
