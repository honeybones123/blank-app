"""Verify controller object for combined low-util candidate-generation handoff."""

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

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_combined_low_util_candidate_generation_handoff_proof,
    )

    source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    first = build_design_guide_controller_combined_low_util_candidate_generation_handoff_proof(
        source_updates={"lig_legs": 0, "lig_spacing": 0, "b": 300},
        shear_seed_updates={"lig_legs": 0, "lig_spacing": 0},
        generator_names=[
            "shear_low_util_target_cleanup_item_fn",
            "combine_best_safe_shear_with_bending_cleanup_item_fn",
        ],
        selected_candidate_id="combined-cleanup-sample",
        selected_updates={"lig_legs": 0, "b": 300},
        contract_enabled=True,
        contract_updates={"lig_legs": 0, "b": 300},
        updates_match_current_state=False,
    )
    second = build_design_guide_controller_combined_low_util_candidate_generation_handoff_proof(
        source_updates={"b": 300, "lig_spacing": 0, "lig_legs": 0},
        shear_seed_updates={"lig_spacing": 0, "lig_legs": 0},
        generator_names=[
            "combine_best_safe_shear_with_bending_cleanup_item_fn",
            "shear_low_util_target_cleanup_item_fn",
        ],
        selected_candidate_id="combined-cleanup-sample",
        selected_updates={"b": 300, "lig_legs": 0},
        contract_enabled=True,
        contract_updates={"b": 300, "lig_legs": 0},
        updates_match_current_state=False,
    )
    current_state_match = build_design_guide_controller_combined_low_util_candidate_generation_handoff_proof(
        source_updates={"lig_legs": 0},
        shear_seed_updates={"lig_legs": 0},
        generator_names=["shear_low_util_target_cleanup_item_fn"],
        selected_candidate_id="same-state",
        selected_updates={"lig_legs": 0},
        contract_enabled=True,
        contract_updates={"lig_legs": 0},
        updates_match_current_state=True,
    )
    disabled_contract = build_design_guide_controller_combined_low_util_candidate_generation_handoff_proof(
        source_updates={"lig_legs": 0},
        shear_seed_updates={"lig_legs": 0},
        generator_names=["shear_low_util_target_cleanup_item_fn"],
        selected_candidate_id="disabled",
        selected_updates={"lig_legs": 0},
        contract_enabled=False,
        contract_updates={"lig_legs": 0},
        updates_match_current_state=False,
    )
    forbidden_tokens = {
        "inputs_page": "inputs_page" in source,
        "streamlit": "streamlit" in source,
        "st_session_state": "st.session_state" in source,
        "render_final_panel": "render_final_panel" in source,
        "apply_routing": "handle_apply_buttons" in source,
    }
    return {
        "decision": "CANDIDATE_GENERATION_HANDOFF_OBJECT_READY",
        "proof_hash_stable": _stable_hash(first) == _stable_hash(second),
        "proof": first,
        "shape": {
            "authority": first.get("authority"),
            "source_update_keys": first.get("source_update_keys"),
            "source_update_hash": first.get("source_update_hash"),
            "shear_seed_update_keys": first.get("shear_seed_update_keys"),
            "shear_seed_update_hash": first.get("shear_seed_update_hash"),
            "generator_names": first.get("generator_names"),
            "selected_candidate_id": first.get("selected_candidate_id"),
            "selected_update_keys": first.get("selected_update_keys"),
            "selected_update_hash": first.get("selected_update_hash"),
            "contract_enabled": first.get("contract_enabled"),
            "contract_update_keys": first.get("contract_update_keys"),
            "contract_update_hash": first.get("contract_update_hash"),
            "updates_match_current_state": first.get("updates_match_current_state"),
            "applicability_gate_allows_result": first.get("applicability_gate_allows_result"),
            "handoff_hash": first.get("handoff_hash"),
            "proof_only": first.get("proof_only"),
            "candidate_generation_owned_here": first.get("candidate_generation_owned_here"),
            "product_driving": first.get("product_driving"),
        },
        "negative_cases": {
            "current_state_match_allows_result": current_state_match.get(
                "applicability_gate_allows_result"
            ),
            "disabled_contract_allows_result": disabled_contract.get(
                "applicability_gate_allows_result"
            ),
        },
        "forbidden_tokens_present": forbidden_tokens,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    shape = dict(capture.get("shape") or {})
    negative = dict(capture.get("negative_cases") or {})
    return {
        "proof_hash_stable": capture.get("proof_hash_stable") is True,
        "required_shape_present": shape.get("authority")
        == "DesignGuideController.combined_low_util_candidate_generation_handoff"
        and shape.get("source_update_keys") == ["b", "lig_legs", "lig_spacing"]
        and shape.get("shear_seed_update_keys") == ["lig_legs", "lig_spacing"]
        and shape.get("generator_names")
        == [
            "combine_best_safe_shear_with_bending_cleanup_item_fn",
            "shear_low_util_target_cleanup_item_fn",
        ]
        and shape.get("selected_candidate_id") == "combined-cleanup-sample"
        and shape.get("selected_update_keys") == ["b", "lig_legs"]
        and shape.get("contract_enabled") is True
        and shape.get("contract_update_keys") == ["b", "lig_legs"]
        and shape.get("updates_match_current_state") is False
        and shape.get("applicability_gate_allows_result") is True
        and bool(shape.get("handoff_hash")),
        "negative_cases_block_result": negative.get("current_state_match_allows_result") is False
        and negative.get("disabled_contract_allows_result") is False,
        "proof_is_non_product_driving": shape.get("proof_only") is True
        and shape.get("candidate_generation_owned_here") is False
        and shape.get("product_driving") is False,
        "no_page_ui_session_apply_imports": not any(
            (capture.get("forbidden_tokens_present") or {}).values()
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Candidate Generation Handoff Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "This proof object records candidate-generation handoff data only. It does not call candidate generators, evaluate candidates, render UI, or route Apply.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_low_util_candidate_generation_handoff_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_candidate_generation_handoff_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_candidate_generation_handoff_object_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
