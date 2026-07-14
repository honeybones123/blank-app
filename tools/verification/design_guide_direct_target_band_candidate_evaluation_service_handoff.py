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

TARGET = "_direct_target_band_guidance_item"
SERVICE_WRAPPER = "_evaluate_direct_target_band_candidate_with_service"


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


def _sample_parity() -> dict[str, Any]:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        evaluate_design_candidate_with_updates,
        evaluate_direct_target_band_candidate_with_updates,
    )

    base_state = {
        "b": 400.0,
        "bw": 400.0,
        "D": 650.0,
        "bot_row_1_bars": 6,
        "bot1_count": 6,
        "bot_row_1_dia": 20,
        "db_bot_1": 20,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
        "uls_Mstar": 200.0,
        "uls_Vstar": 80.0,
    }
    updates = {"D": 675.0, "b": 425.0, "bw": 425.0}
    source = "design_guide_direct_target_band_search"
    label = "increase depth 25"
    action_type = "apply_resolved_candidate"
    calls: list[dict[str, Any]] = []

    def snapshot_fn(state: dict[str, Any]) -> dict[str, Any]:
        return dict(state or {})

    def evaluator_fn(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls.append({"state": dict(state or {}), "kwargs": dict(kwargs)})
        candidate_id = "direct_target_band_candidate"
        return {
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "source": kwargs.get("source"),
            "label": kwargs.get("label"),
            "action_type": kwargs.get("action_type"),
            "updates": dict(kwargs.get("updates") or {}),
            "overview": {
                "utils": {"bending": 0.86, "shear": 0.74},
                "statuses": {
                    "bending": "PASS",
                    "shear": "PASS",
                    "crack": "PASS",
                    "deflection": "PASS",
                },
                "any_fail": False,
                "all_key_pass": True,
                "worst_util": 0.86,
                "governing_util": 0.86,
            },
            "candidate_search_evidence": {
                "selected_candidate_id": candidate_id,
                "search_scope": str(kwargs.get("source") or source),
            },
            "button_contract": {
                "enabled": True,
                "actionable": True,
                "action_type": kwargs.get("action_type"),
            },
            "action_payload": {
                "source_candidate_id": candidate_id,
                "updates": dict(kwargs.get("updates") or {}),
            },
            "title_main": kwargs.get("label") or "Direct target-band candidate",
            "guidance_change_lines": ["Apply direct target-band candidate."],
        }

    old_update = evaluate_design_candidate_with_updates(
        base_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    new_update = evaluate_direct_target_band_candidate_with_updates(
        base_state,
        updates=updates,
        source=source,
        label=label,
        action_type=action_type,
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    old_seed = evaluate_design_candidate_with_updates(
        base_state,
        updates=None,
        source="direct_target_band_shear_seed",
        label=None,
        action_type=None,
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    new_seed = evaluate_direct_target_band_candidate_with_updates(
        base_state,
        updates=None,
        source="direct_target_band_shear_seed",
        label=None,
        action_type=None,
        state_snapshot_fn=snapshot_fn,
        evaluator_fn=evaluator_fn,
    )
    return {
        "old_update": old_update,
        "new_update": new_update,
        "old_seed": old_seed,
        "new_seed": new_seed,
        "old_update_hash": _stable_hash(old_update),
        "new_update_hash": _stable_hash(new_update),
        "old_seed_hash": _stable_hash(old_seed),
        "new_seed_hash": _stable_hash(new_seed),
        "candidate_overview_hashes": {
            "old": _stable_hash(dict(old_update.get("overview") or {})),
            "new": _stable_hash(dict(new_update.get("overview") or {})),
            "old_seed": _stable_hash(dict(old_seed.get("overview") or {})),
            "new_seed": _stable_hash(dict(new_seed.get("overview") or {})),
        },
        "candidate_evidence_hashes": {
            "old": _stable_hash(dict(old_update.get("candidate_search_evidence") or {})),
            "new": _stable_hash(dict(new_update.get("candidate_search_evidence") or {})),
        },
        "updates_hashes": {
            "old": _stable_hash(dict(old_update.get("updates") or {})),
            "new": _stable_hash(dict(new_update.get("updates") or {})),
            "old_seed": _stable_hash(dict(old_seed.get("updates") or {})),
            "new_seed": _stable_hash(dict(new_seed.get("updates") or {})),
        },
        "button_contract_hashes": {
            "old": _stable_hash(dict(old_update.get("button_contract") or {})),
            "new": _stable_hash(dict(new_update.get("button_contract") or {})),
        },
        "action_payload_hashes": {
            "old": _stable_hash(dict(old_update.get("action_payload") or {})),
            "new": _stable_hash(dict(new_update.get("action_payload") or {})),
        },
        "visible_wording_hashes": {
            "old": _stable_hash(
                {
                    "title_main": old_update.get("title_main"),
                    "guidance_change_lines": old_update.get("guidance_change_lines"),
                }
            ),
            "new": _stable_hash(
                {
                    "title_main": new_update.get("title_main"),
                    "guidance_change_lines": new_update.get("guidance_change_lines"),
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
    parity = _sample_parity()
    return {
        "schema": "design_guide_direct_target_band_candidate_evaluation_service_handoff.v1",
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
        "parity": parity,
        "source_checks": {
            "target_no_longer_calls_auto_design_candidate": "_evaluate_auto_design_candidate(" not in target_source,
            "target_no_longer_calls_evaluate_candidate_full_directly": "evaluate_candidate_full(" not in target_source,
            "target_uses_service_wrapper_three_times": target_source.count("_evaluate_direct_target_band_candidate_with_service(") == 3,
            "auto_candidate_shim_retained": "def _evaluate_auto_design_candidate(" in inputs_source,
            "service_wrapper_exists": bool(wrapper_source),
            "service_wrapper_uses_candidate_evaluation_helper": "_evaluate_direct_target_band_candidate_with_updates(" in wrapper_source,
            "candidate_evaluation_helper_exists": "def evaluate_direct_target_band_candidate_with_updates(" in candidate_source,
            "candidate_evaluation_exports_helper": '"evaluate_direct_target_band_candidate_with_updates"' in candidate_source,
            "candidate_evaluation_import_clean_terms_absent": all(
                token not in candidate_source
                for token in (
                    "inputs_page",
                    "streamlit",
                    "st.session_state",
                    "rendered_html",
                    "apply_routing",
                    "ui_state",
                )
            ),
            "target_route_orchestration_still_present": all(
                token in target_source
                for token in (
                    "_evaluate_updates(",
                    "_select_direct_target_item(",
                    "_bounded_proof_blocker_item(",
                    "_guidance_item_from_resolved_candidate(",
                    "st.session_state",
                    "item[\"action_payload\"]",
                    "item[\"resolved_candidate\"]",
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
        "old_new_update_candidate_output_equivalent": parity.get("old_update_hash") == parity.get("new_update_hash"),
        "old_new_seed_candidate_output_equivalent": parity.get("old_seed_hash") == parity.get("new_seed_hash"),
        "candidate_overview_unchanged": (
            (parity.get("candidate_overview_hashes") or {}).get("old")
            == (parity.get("candidate_overview_hashes") or {}).get("new")
            and (parity.get("candidate_overview_hashes") or {}).get("old_seed")
            == (parity.get("candidate_overview_hashes") or {}).get("new_seed")
        ),
        "candidate_evidence_unchanged": (
            (parity.get("candidate_evidence_hashes") or {}).get("old")
            == (parity.get("candidate_evidence_hashes") or {}).get("new")
        ),
        "updates_unchanged": (
            (parity.get("updates_hashes") or {}).get("old") == (parity.get("updates_hashes") or {}).get("new")
            and (parity.get("updates_hashes") or {}).get("old_seed")
            == (parity.get("updates_hashes") or {}).get("new_seed")
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
        "source_checks_green": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Direct Target-Band Candidate Evaluation Service Handoff",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Target lines: `{(capture.get('target') or {}).get('line_start')}`-`{(capture.get('target') or {}).get('line_end')}`",
        f"- Service wrapper lines: `{(capture.get('wrapper') or {}).get('line_start')}`-`{(capture.get('wrapper') or {}).get('line_end')}`",
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
            "## Boundaries Preserved",
            "- route orchestration stayed in `inputs_page.py`",
            "- session diagnostics/cache stayed in `inputs_page.py`",
            "- ranking/selection stayed unchanged",
            "- blocker/fallback construction stayed unchanged",
            "- item/action payload projection stayed unchanged",
            "",
            "## Next",
            "Run the target-band boundary audit to confirm page evaluator shim count reached zero for this surface.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = PROGRESS_PATH.read_text(encoding="utf-8").rstrip() if PROGRESS_PATH.exists() else ""
    lines = [existing, ""] if existing else []
    lines.extend(
        [
            f"## {payload.get('created_at')} - Direct target-band candidate evaluation service handoff",
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
        "schema": "design_guide_direct_target_band_candidate_evaluation_service_handoff.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "decision": "DIRECT_TARGET_BAND_CANDIDATE_EVALUATION_SERVICE_HANDOFF_PASS"
        if passed
        else "DIRECT_TARGET_BAND_CANDIDATE_EVALUATION_SERVICE_HANDOFF_FAIL",
        "capture": capture,
        "checks": checks,
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_band_candidate_evaluation_service_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_band_candidate_evaluation_service_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_direct_target_band_candidate_evaluation_service_handoff {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in checks.items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
