"""Verify controller proof object for combined low-util cleanup route policy."""

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
        build_design_guide_controller_combined_low_util_cleanup_route_policy_proof,
    )

    source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    final_overview = {
        "utils": {"bending": 0.42, "shear": 0.38},
        "status": "pass",
    }
    first = build_design_guide_controller_combined_low_util_cleanup_route_policy_proof(
        final_overview=dict(final_overview),
        final_accepted_min_family_util=0.85,
        final_bending_util=0.42,
        final_shear_util=0.38,
        shear_seed_updates={"lig_legs": 0, "lig_spacing": 0},
    )
    second = build_design_guide_controller_combined_low_util_cleanup_route_policy_proof(
        final_overview=dict(final_overview),
        final_accepted_min_family_util=0.85,
        final_bending_util=0.42,
        final_shear_util=0.38,
        shear_seed_updates={"lig_spacing": 0, "lig_legs": 0},
    )
    no_seed = build_design_guide_controller_combined_low_util_cleanup_route_policy_proof(
        final_overview=dict(final_overview),
        final_accepted_min_family_util=0.85,
        final_bending_util=0.42,
        final_shear_util=0.38,
        shear_seed_updates={},
    )
    above_threshold = build_design_guide_controller_combined_low_util_cleanup_route_policy_proof(
        final_overview=dict(final_overview),
        final_accepted_min_family_util=0.85,
        final_bending_util=0.91,
        final_shear_util=0.38,
        shear_seed_updates={"lig_legs": 0},
    )
    forbidden_tokens = {
        "inputs_page": "inputs_page" in source,
        "streamlit": "streamlit" in source,
        "st_session_state": "st.session_state" in source,
        "render_final_panel": "render_final_panel" in source,
        "apply_routing": "handle_apply_buttons" in source,
    }
    return {
        "decision": "COMBINED_LOW_UTIL_ROUTE_POLICY_OBJECT_READY",
        "proof_hash_stable": _stable_hash(first) == _stable_hash(second),
        "proof": first,
        "negative_cases": {
            "no_seed_allows_candidate_generation": no_seed.get(
                "route_policy_allows_candidate_generation"
            ),
            "above_threshold_allows_candidate_generation": above_threshold.get(
                "route_policy_allows_candidate_generation"
            ),
        },
        "shape": {
            "authority": first.get("authority"),
            "threshold": first.get("threshold"),
            "bending_util": first.get("bending_util"),
            "shear_util": first.get("shear_util"),
            "bending_below_threshold": first.get("bending_below_threshold"),
            "shear_below_threshold": first.get("shear_below_threshold"),
            "route_policy_allows_candidate_generation": first.get(
                "route_policy_allows_candidate_generation"
            ),
            "shear_seed_updates_present": first.get("shear_seed_updates_present"),
            "shear_seed_update_keys": list(first.get("shear_seed_update_keys") or []),
            "shear_seed_update_hash": first.get("shear_seed_update_hash"),
            "final_overview_hash": first.get("final_overview_hash"),
            "route_policy_hash": first.get("route_policy_hash"),
            "proof_only": first.get("proof_only"),
            "candidate_generation_owned_here": first.get("candidate_generation_owned_here"),
            "product_driving": first.get("product_driving"),
        },
        "forbidden_tokens_present": forbidden_tokens,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    shape = dict(capture.get("shape") or {})
    negative = dict(capture.get("negative_cases") or {})
    return {
        "proof_hash_stable": capture.get("proof_hash_stable") is True,
        "required_shape_present": shape.get("authority")
        == "DesignGuideController.combined_low_util_cleanup_route_policy"
        and shape.get("threshold") == 0.85
        and shape.get("bending_util") == 0.42
        and shape.get("shear_util") == 0.38
        and shape.get("bending_below_threshold") is True
        and shape.get("shear_below_threshold") is True
        and shape.get("route_policy_allows_candidate_generation") is True
        and shape.get("shear_seed_updates_present") is True
        and shape.get("shear_seed_update_keys") == ["lig_legs", "lig_spacing"]
        and bool(shape.get("shear_seed_update_hash"))
        and bool(shape.get("final_overview_hash"))
        and bool(shape.get("route_policy_hash")),
        "negative_cases_block_candidate_generation": negative.get(
            "no_seed_allows_candidate_generation"
        )
        is False
        and negative.get("above_threshold_allows_candidate_generation") is False,
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
        "# Design Guide Combined Low-Util Cleanup Route Policy Object Snapshot",
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
            "This proof object represents route-policy inputs only. It does not generate cleanup candidates, rank recommendations, render UI, or route Apply.",
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
        / f"design_guide_combined_low_util_cleanup_route_policy_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_cleanup_route_policy_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_cleanup_route_policy_object_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
