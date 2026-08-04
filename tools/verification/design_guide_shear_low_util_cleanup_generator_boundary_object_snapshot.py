"""Verify proof-only boundary object for shear low-util cleanup generator core."""

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
        build_design_guide_shear_low_util_cleanup_generator_boundary_proof,
    )

    source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    first = build_design_guide_shear_low_util_cleanup_generator_boundary_proof(
        input_state={"b": 400, "D": 650, "lig_legs": 2, "s_lig": 200},
        overview={"utils": {"shear": 0.32}, "statuses": {"shear": "PASS"}},
        threshold=0.85,
        target_band={"low": 0.85, "high": 0.95},
        source_updates={"lig_legs": 0, "s_lig": 9999},
        variant_count=8,
        evaluated_candidate_count=5,
        safe_candidate_count=2,
        selected_candidate_id="shear-cleanup-no-links",
        selected_updates={"lig_legs": 0, "s_lig": 9999},
        acceptance_reason="selected_safe_low_util_cleanup",
        rejection_reason=None,
    )
    second = build_design_guide_shear_low_util_cleanup_generator_boundary_proof(
        input_state={"D": 650, "b": 400, "s_lig": 200, "lig_legs": 2},
        overview={"statuses": {"shear": "PASS"}, "utils": {"shear": 0.32}},
        threshold="0.85",
        target_band={"high": 0.95, "low": 0.85},
        source_updates={"s_lig": 9999, "lig_legs": 0},
        variant_count=8,
        evaluated_candidate_count=5,
        safe_candidate_count=2,
        selected_candidate_id="shear-cleanup-no-links",
        selected_updates={"s_lig": 9999, "lig_legs": 0},
        acceptance_reason="selected_safe_low_util_cleanup",
        rejection_reason=None,
    )
    rejected = build_design_guide_shear_low_util_cleanup_generator_boundary_proof(
        input_state={"b": 400, "D": 650},
        overview={"utils": {"shear": 0.32}},
        threshold=0.85,
        target_band={"low": 0.85, "high": 0.95},
        source_updates={},
        variant_count=0,
        evaluated_candidate_count=0,
        safe_candidate_count=0,
        selected_candidate_id=None,
        selected_updates={},
        acceptance_reason=None,
        rejection_reason="no_safe_candidate",
    )
    forbidden_tokens = {
        "inputs_page": "inputs_page" in source,
        "streamlit": "streamlit" in source,
        "st_session_state": "st.session_state" in source,
        "render_final_panel": "render_final_panel" in source,
        "apply_routing": "handle_apply_buttons" in source,
    }
    return {
        "decision": "SHEAR_LOW_UTIL_GENERATOR_BOUNDARY_OBJECT_READY",
        "proof_hash_stable": _stable_hash(first) == _stable_hash(second),
        "proof": first,
        "shape": {
            "authority": first.get("authority"),
            "threshold": first.get("threshold"),
            "target_band": first.get("target_band"),
            "variant_count": first.get("variant_count"),
            "evaluated_candidate_count": first.get("evaluated_candidate_count"),
            "safe_candidate_count": first.get("safe_candidate_count"),
            "selected_candidate_id": first.get("selected_candidate_id"),
            "selected_update_keys": first.get("selected_update_keys"),
            "selected_update_hash": first.get("selected_update_hash"),
            "acceptance_reason": first.get("acceptance_reason"),
            "rejection_reason": first.get("rejection_reason"),
            "boundary_hash": first.get("boundary_hash"),
            "proof_only": first.get("proof_only"),
            "generator_owned_here": first.get("generator_owned_here"),
            "evaluator_owned_here": first.get("evaluator_owned_here"),
            "product_driving": first.get("product_driving"),
        },
        "negative_shape": {
            "rejected_selected_candidate_id": rejected.get("selected_candidate_id"),
            "rejected_selected_update_keys": rejected.get("selected_update_keys"),
            "rejected_rejection_reason": rejected.get("rejection_reason"),
        },
        "forbidden_tokens_present": forbidden_tokens,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    shape = dict(capture.get("shape") or {})
    negative = dict(capture.get("negative_shape") or {})
    return {
        "proof_hash_stable": capture.get("proof_hash_stable") is True,
        "required_shape_present": shape.get("authority")
        == "DesignGuideController.shear_low_util_cleanup_generator_boundary"
        and shape.get("threshold") == 0.85
        and shape.get("target_band") == {"low": 0.85, "high": 0.95}
        and shape.get("variant_count") == 8
        and shape.get("evaluated_candidate_count") == 5
        and shape.get("safe_candidate_count") == 2
        and shape.get("selected_candidate_id") == "shear-cleanup-no-links"
        and shape.get("selected_update_keys") == ["lig_legs", "s_lig"]
        and shape.get("acceptance_reason") == "selected_safe_low_util_cleanup"
        and shape.get("rejection_reason") is None
        and bool(shape.get("boundary_hash")),
        "negative_case_represented": negative.get("rejected_selected_candidate_id") is None
        and negative.get("rejected_selected_update_keys") == []
        and negative.get("rejected_rejection_reason") == "no_safe_candidate",
        "proof_is_non_product_driving": shape.get("proof_only") is True
        and shape.get("generator_owned_here") is False
        and shape.get("evaluator_owned_here") is False
        and shape.get("product_driving") is False,
        "no_page_ui_session_apply_imports": not any(
            (capture.get("forbidden_tokens_present") or {}).values()
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Cleanup Generator Boundary Object Snapshot",
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
            "This proof object records the generator boundary only. It does not generate variants, evaluate candidates, render UI, or route Apply.",
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
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_cleanup_generator_boundary_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_cleanup_generator_boundary_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_cleanup_generator_boundary_object_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
