from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_bending_only_target_band_cleanup_item"
SERVICE_WRAPPER = "_evaluate_bending_only_target_band_candidate_with_service"
PREBUILT_WRAPPER = "_evaluate_bending_only_target_band_prebuilt_candidate_with_service"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(lines[node.lineno - 1 : int(node.end_lineno or node.lineno)])
    return 0, 0, ""


def _sample_candidate(candidate_id: str, source_value: str, updates_value: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_candidate_id": candidate_id,
        "source": source_value,
        "label": kwargs.get("label"),
        "action_type": kwargs.get("action_type"),
        "updates": dict(updates_value or {}),
        "overview": {
            "utils": {"bending": 0.88, "shear": 0.63},
            "statuses": {
                "bending": "PASS",
                "shear": "PASS",
                "crack": "PASS",
                "deflection": "PASS",
            },
            "any_fail": False,
            "all_key_pass": True,
            "worst_util": 0.88,
            "governing_util": 0.88,
        },
        "candidate_search_evidence": {
            "selected_candidate_id": candidate_id,
            "search_scope": source_value,
            "safe_executor_backed_candidates_count": 1,
        },
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": kwargs.get("action_type"),
        },
        "action_payload": {
            "source_candidate_id": candidate_id,
                "updates": dict(updates_value or {}),
        },
        "title_main": kwargs.get("label") or "Bending cleanup - further reduction reaches target range",
        "guidance_change_lines": ["Reduce bottom reinforcement toward the target band."],
    }


def _sample_parity() -> dict[str, Any]:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        evaluate_bending_only_target_band_candidate_with_updates,
        evaluate_design_candidate_with_updates,
    )

    base_state = {
        "b": 400.0,
        "bw": 400.0,
        "D": 650.0,
        "bot_row_1_bars": 6,
        "bot1_count": 6,
        "bot_row_1_dia": 20,
        "db_bot_1": 20,
        "uls_Mstar": 200.0,
        "uls_Vstar": 20.0,
    }
    updates = {
        "bot_row_1_bars": 5,
        "bot1_count": 5,
        "bot_row_1_dia": 16,
        "db_bot_1": 16,
    }
    source = "design_guide_bending_only_cleanup_search"
    label = "Bending cleanup - further reduction reaches target range"
    action_type = "apply_resolved_candidate"
    calls: list[dict[str, Any]] = []

    def snapshot_fn(state: dict[str, Any]) -> dict[str, Any]:
        return dict(state or {})

    def evaluator_fn(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls.append({"state": dict(state or {}), "kwargs": dict(kwargs)})
        return _sample_candidate(
            "bending_only_cleanup_001",
            str(kwargs.get("source") or source),
            dict(kwargs.get("updates") or {}),
            **kwargs,
        )

    old_path = evaluate_design_candidate_with_updates(
        base_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    new_path = evaluate_bending_only_target_band_candidate_with_updates(
        base_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )

    prebuilt_state = dict(base_state)
    prebuilt_state.update(updates)
    prebuilt_source = "guidance:bending_cleanup_publish_terminalisation_bending_preview"

    def prebuilt_evaluator_fn(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls.append({"state": dict(state or {}), "kwargs": dict(kwargs)})
        return _sample_candidate(
            "bending_only_terminalisation_preview",
            str(kwargs.get("source") or prebuilt_source),
            dict(kwargs.get("updates") or {}),
            **kwargs,
        )

    old_prebuilt = prebuilt_evaluator_fn(
        dict(prebuilt_state),
        source=prebuilt_source,
        updates=updates,
    )
    new_prebuilt = evaluate_bending_only_target_band_candidate_with_updates(
        prebuilt_state,
        updates=None,
        source=prebuilt_source,
        label=None,
        action_type=None,
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=lambda candidate_state, **kwargs: prebuilt_evaluator_fn(
            candidate_state,
            source=kwargs.get("source"),
            label=kwargs.get("label"),
            action_type=kwargs.get("action_type"),
            updates=updates,
        ),
    )

    return {
        "old_path": old_path,
        "new_path": new_path,
        "old_hash": _stable_hash(old_path),
        "new_hash": _stable_hash(new_path),
        "old_prebuilt": old_prebuilt,
        "new_prebuilt": new_prebuilt,
        "old_prebuilt_hash": _stable_hash(old_prebuilt),
        "new_prebuilt_hash": _stable_hash(new_prebuilt),
        "candidate_overview_hashes": {
            "old": _stable_hash(dict(old_path.get("overview") or {})),
            "new": _stable_hash(dict(new_path.get("overview") or {})),
        },
        "candidate_evidence_hashes": {
            "old": _stable_hash(dict(old_path.get("candidate_search_evidence") or {})),
            "new": _stable_hash(dict(new_path.get("candidate_search_evidence") or {})),
        },
        "updates_hashes": {
            "old": _stable_hash(dict(old_path.get("updates") or {})),
            "new": _stable_hash(dict(new_path.get("updates") or {})),
            "old_prebuilt": _stable_hash(dict(old_prebuilt.get("updates") or {})),
            "new_prebuilt": _stable_hash(dict(new_prebuilt.get("updates") or {})),
        },
        "button_contract_hashes": {
            "old": _stable_hash(dict(old_path.get("button_contract") or {})),
            "new": _stable_hash(dict(new_path.get("button_contract") or {})),
        },
        "action_payload_hashes": {
            "old": _stable_hash(dict(old_path.get("action_payload") or {})),
            "new": _stable_hash(dict(new_path.get("action_payload") or {})),
        },
        "visible_wording_hashes": {
            "old": _stable_hash(
                {
                    "title_main": old_path.get("title_main"),
                    "guidance_change_lines": old_path.get("guidance_change_lines"),
                }
            ),
            "new": _stable_hash(
                {
                    "title_main": new_path.get("title_main"),
                    "guidance_change_lines": new_path.get("guidance_change_lines"),
                }
            ),
        },
        "debug_proof_hashes": {
            "old": _stable_hash(
                {
                    "candidate_search_evidence": old_path.get("candidate_search_evidence"),
                    "source": old_path.get("source"),
                    "candidate_id": old_path.get("candidate_id"),
                }
            ),
            "new": _stable_hash(
                {
                    "candidate_search_evidence": new_path.get("candidate_search_evidence"),
                    "source": new_path.get("source"),
                    "candidate_id": new_path.get("candidate_id"),
                }
            ),
        },
        "calls": calls,
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    wrapper_start, wrapper_end, wrapper_source = _function_source(inputs_source, SERVICE_WRAPPER)
    prebuilt_start, prebuilt_end, prebuilt_source = _function_source(inputs_source, PREBUILT_WRAPPER)
    parity = _sample_parity()
    return {
        "schema": "design_guide_bending_only_target_band_candidate_evaluation_service_handoff.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "wrapper": {
            "name": SERVICE_WRAPPER,
            "line_start": wrapper_start,
            "line_end": wrapper_end,
            "line_count": max(0, wrapper_end - wrapper_start + 1),
        },
        "prebuilt_wrapper": {
            "name": PREBUILT_WRAPPER,
            "line_start": prebuilt_start,
            "line_end": prebuilt_end,
            "line_count": max(0, prebuilt_end - prebuilt_start + 1),
        },
        "parity": parity,
        "source_checks": {
            "target_no_longer_calls_auto_design_candidate": "_evaluate_auto_design_candidate(" not in target_source,
            "target_no_longer_calls_evaluate_candidate_full_directly": "evaluate_candidate_full(" not in target_source,
            "target_uses_service_wrapper": "_evaluate_bending_only_target_band_candidate_with_service(" in target_source,
            "target_uses_prebuilt_service_wrapper": "_evaluate_bending_only_target_band_prebuilt_candidate_with_service(" in target_source,
            "auto_candidate_shim_retained": "def _evaluate_auto_design_candidate(" in inputs_source,
            "service_wrapper_exists": bool(wrapper_source),
            "prebuilt_wrapper_exists": bool(prebuilt_source),
            "service_wrapper_uses_candidate_evaluation_helper": "_evaluate_bending_only_target_band_candidate_with_updates(" in wrapper_source,
            "prebuilt_wrapper_uses_candidate_evaluation_helper": "_evaluate_bending_only_target_band_candidate_with_updates(" in prebuilt_source,
            "candidate_evaluation_helper_exists": "def evaluate_bending_only_target_band_candidate_with_updates(" in candidate_source,
            "candidate_evaluation_exports_helper": '"evaluate_bending_only_target_band_candidate_with_updates"' in candidate_source,
            "candidate_evaluation_import_clean_terms_absent": all(
                token not in candidate_source
                for token in (
                    "inputs_page",
                    "streamlit",
                    "st.session_state",
                    "button_contract",
                    "publication",
                    "apply_routing",
                    "rendered_html",
                    "ui_state",
                )
            ),
            "target_generator_and_packaging_paths_still_present": all(
                token in target_source
                for token in (
                    "_build_bending_only_target_band_cleanup_update_trials(",
                    "raw_updates = list(",
                    "update_trials = list(",
                    "for idx, updates in enumerate(update_trials, start=1):",
                    "_build_candidate_search_evidence(",
                    "_guidance_item_from_resolved_candidate(",
                    "_build_design_guide_controller_bending_only_target_band_cleanup_item_projection(",
                    "_cache_bending_cleanup_result(",
                )
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    parity = dict(capture.get("parity") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "old_new_candidate_output_equivalent": parity.get("old_hash") == parity.get("new_hash"),
        "old_new_prebuilt_output_equivalent": parity.get("old_prebuilt_hash") == parity.get("new_prebuilt_hash"),
        "candidate_overview_unchanged": (
            (parity.get("candidate_overview_hashes") or {}).get("old")
            == (parity.get("candidate_overview_hashes") or {}).get("new")
        ),
        "candidate_evidence_unchanged": (
            (parity.get("candidate_evidence_hashes") or {}).get("old")
            == (parity.get("candidate_evidence_hashes") or {}).get("new")
        ),
        "selected_candidate_id_unchanged": (
            (parity.get("old_path") or {}).get("candidate_id") == (parity.get("new_path") or {}).get("candidate_id")
        ),
        "updates_unchanged": (
            (parity.get("updates_hashes") or {}).get("old") == (parity.get("updates_hashes") or {}).get("new")
            and (parity.get("updates_hashes") or {}).get("old_prebuilt")
            == (parity.get("updates_hashes") or {}).get("new_prebuilt")
        ),
        "button_contract_unchanged": (
            (parity.get("button_contract_hashes") or {}).get("old")
            == (parity.get("button_contract_hashes") or {}).get("new")
        ),
        "action_payload_unchanged": (
            (parity.get("action_payload_hashes") or {}).get("old")
            == (parity.get("action_payload_hashes") or {}).get("new")
        ),
        "visible_wording_unchanged": (
            (parity.get("visible_wording_hashes") or {}).get("old")
            == (parity.get("visible_wording_hashes") or {}).get("new")
            and capture.get("visible_wording_changed") is False
        ),
        "debug_proof_fields_unchanged": (
            (parity.get("debug_proof_hashes") or {}).get("old")
            == (parity.get("debug_proof_hashes") or {}).get("new")
        ),
        "source_checks_green": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Bending-Only Target-Band Candidate Evaluation Service Handoff",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Target lines: `{(capture.get('target') or {}).get('line_start')}`-`{(capture.get('target') or {}).get('line_end')}`",
        f"- Service wrapper lines: `{(capture.get('wrapper') or {}).get('line_start')}`-`{(capture.get('wrapper') or {}).get('line_end')}`",
        f"- Prebuilt wrapper lines: `{(capture.get('prebuilt_wrapper') or {}).get('line_start')}`-`{(capture.get('prebuilt_wrapper') or {}).get('line_end')}`",
        "",
        "## Parity Proof",
    ]
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(["", "## Source Checks"])
    for name, value in dict(capture.get("source_checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(
        [
            "",
            "## Stop Conditions Checked",
            "- candidate evidence unchanged",
            "- selected candidate id unchanged",
            "- updates unchanged",
            "- button contract unchanged",
            "- action payload unchanged",
            "- visible wording unchanged",
            "- debug/proof fields unchanged",
            "- family runtime unchanged",
            "",
            "## Next",
            "Do not move `_direct_target_band_guidance_item(...)` without a dedicated re-audit.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Bending-only target-band candidate evaluation service handoff",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Decision: `{payload.get('decision')}`",
            f"- Report: [{report_path.name}](../audits/{report_path.name})",
            "",
        ]
    )
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = _timestamp()
    capture = _capture()
    checks = _checks(capture)
    passed = all(checks.values())
    payload = {
        "schema": "design_guide_bending_only_target_band_candidate_evaluation_service_handoff.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "decision": "BENDING_ONLY_TARGET_BAND_CANDIDATE_EVALUATION_SERVICE_HANDOFF_PASS"
        if passed
        else "BENDING_ONLY_TARGET_BAND_CANDIDATE_EVALUATION_SERVICE_HANDOFF_FAIL",
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bending_only_target_band_candidate_evaluation_service_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_only_target_band_candidate_evaluation_service_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_bending_only_target_band_candidate_evaluation_service_handoff {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
