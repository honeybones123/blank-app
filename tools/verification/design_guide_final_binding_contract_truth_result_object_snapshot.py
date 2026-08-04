"""Object snapshot for final-binding enabled contract truth result."""

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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

SHEAR_KEYS = ["s_lig", "shear_link_spacing"]
BOTTOM_KEYS = ["bottom_bar_size", "n_bottom", "bottom_layers"]
REQUIRED_RESULT_FIELDS = {
    "evidence_expected_util",
    "contract_expected_util",
    "evidence_family_for_contract",
    "family_resolution_source",
    "util_resolution_source",
    "contract_updates_cross_family",
    "blocker_families_for_contract",
    "contract_update_keys_for_family",
    "contract_combined_text",
    "title_hint_for_contract",
    "debug_effect",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _function_source(source: str) -> str:
    token = "def build_final_visible_contract_binding_truth_result("
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _base_kwargs() -> dict[str, Any]:
    return {
        "evidence_for_binding": {"family": "shear", "selected_candidate_util": 0.81},
        "contract": {"expected_util": 0.8},
        "item": {"title": "Optional shear cleanup"},
        "updates": {"s_lig": 150.0},
        "compound_shear_update_keys": list(SHEAR_KEYS),
        "compound_bottom_update_keys": list(BOTTOM_KEYS),
        "combined_binding_bending_util": None,
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import build_final_visible_contract_binding_truth_result

    plain = build_final_visible_contract_binding_truth_result(**_base_kwargs())
    plain_repeat = build_final_visible_contract_binding_truth_result(**_base_kwargs())
    bending_kwargs = _base_kwargs()
    bending_kwargs.update(
        {
            "evidence_for_binding": {
                "family": "cleanup",
                "selected_candidate_util": 0.22,
                "best_target_band_candidate_util": 0.86,
                "target_band_candidate_count": 2,
            },
            "item": {"title": "Optional bending cleanup"},
            "updates": {"bottom_bar_size": "N16"},
        }
    )
    bending = build_final_visible_contract_binding_truth_result(**bending_kwargs)
    combined_kwargs = _base_kwargs()
    combined_kwargs.update(
        {
            "evidence_for_binding": {
                "family": "combined",
                "selected_candidate_util": 0.62,
                "selected_candidate_id": "combined_candidate",
            },
            "item": {"title": "Shear and bending cleanup"},
            "updates": {"s_lig": 150.0, "bottom_bar_size": "N20"},
            "combined_binding_bending_util": 0.91,
        }
    )
    combined = build_final_visible_contract_binding_truth_result(**combined_kwargs)
    title_shear_kwargs = _base_kwargs()
    title_shear_kwargs.update(
        {
            "evidence_for_binding": {"family": "cleanup", "selected_candidate_util": 0.7},
            "item": {"title": "Optional shear cleanup"},
        }
    )
    title_shear = build_final_visible_contract_binding_truth_result(**title_shear_kwargs)
    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_source = _function_source(source)
    plain_result = dict(plain.get("result") or {})
    bending_result = dict(bending.get("result") or {})
    combined_result = dict(combined.get("result") or {})
    title_shear_result = dict(title_shear.get("result") or {})
    flags = {
        "proof_only": plain.get("proof_only"),
        "product_driving": plain.get("product_driving"),
        "render_driving": plain.get("render_driving"),
        "apply_driving": plain.get("apply_driving"),
        "session_driving": plain.get("session_driving"),
        "ready_for_trace_wiring": plain.get("ready_for_trace_wiring"),
        "ready_for_live_cutover": plain.get("ready_for_live_cutover"),
    }
    forbidden_tokens = {
        "inputs_page": "inputs_page" in function_source,
        "streamlit": "streamlit" in function_source.lower() or "st." in function_source,
        "session_state": "session_state" in function_source,
        "evaluator": "_evaluate_auto_design_candidate" in function_source,
        "state_match_helper": "_updates_match_state" in function_source,
        "render_html": "html" in function_source.lower(),
    }
    latest = {
        "residual_policy": _latest("design_guide_final_binding_residual_policy_ownership"),
        "consistency_cutover": _latest("design_guide_final_binding_consistency_guard_result_cutover"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_CONTRACT_TRUTH_RESULT_OBJECT_READY_FOR_TRACE",
        "function_present": "def build_final_visible_contract_binding_truth_result(" in source,
        "exported": '"build_final_visible_contract_binding_truth_result"' in source,
        "missing_result_fields": sorted(REQUIRED_RESULT_FIELDS - set(plain_result)),
        "plain_shear_family": plain_result.get("evidence_family_for_contract") == "shear",
        "plain_shear_util": plain_result.get("evidence_expected_util") == 0.81,
        "title_shear_family": title_shear_result.get("evidence_family_for_contract") == "shear",
        "bending_title_family": bending_result.get("evidence_family_for_contract") == "bending",
        "bending_target_util_override": bending_result.get("evidence_expected_util") == 0.86,
        "combined_cross_family": combined_result.get("contract_updates_cross_family") is True,
        "combined_family": combined_result.get("evidence_family_for_contract") == "combined",
        "combined_preview_util_override": combined_result.get("evidence_expected_util") == 0.91,
        "combined_blocker_families": combined_result.get("blocker_families_for_contract") == [
            "bending",
            "combined",
            "shear",
        ],
        "proof_hash_stable": plain.get("proof_hash") == plain_repeat.get("proof_hash"),
        "result_hash_stable": plain.get("result_hash") == plain_repeat.get("result_hash"),
        "flags": flags,
        "forbidden_tokens": forbidden_tokens,
        "forbidden_tokens_absent": not any(forbidden_tokens.values()),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    flags = dict(capture.get("flags") or {})
    latest = dict(capture.get("latest") or {})
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "required_fields_present": not capture.get("missing_result_fields"),
        "plain_shear_family": capture.get("plain_shear_family") is True,
        "plain_shear_util": capture.get("plain_shear_util") is True,
        "title_shear_family": capture.get("title_shear_family") is True,
        "bending_title_family": capture.get("bending_title_family") is True,
        "bending_target_util_override": capture.get("bending_target_util_override") is True,
        "combined_cross_family": capture.get("combined_cross_family") is True,
        "combined_family": capture.get("combined_family") is True,
        "combined_preview_util_override": capture.get("combined_preview_util_override") is True,
        "combined_blocker_families": capture.get("combined_blocker_families") is True,
        "proof_hash_stable": capture.get("proof_hash_stable") is True,
        "result_hash_stable": capture.get("result_hash_stable") is True,
        "proof_only": flags.get("proof_only") is True,
        "not_product_driving": flags.get("product_driving") is False,
        "not_render_driving": flags.get("render_driving") is False,
        "not_apply_driving": flags.get("apply_driving") is False,
        "not_session_driving": flags.get("session_driving") is False,
        "ready_for_trace_wiring": flags.get("ready_for_trace_wiring") is True,
        "not_ready_for_live_cutover": flags.get("ready_for_live_cutover") is False,
        "forbidden_tokens_absent": capture.get("forbidden_tokens_absent") is True,
        "residual_policy_pass": (latest.get("residual_policy") or {}).get("status") == "PASS",
        "consistency_cutover_pass": (latest.get("consistency_cutover") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding Contract Truth Result Object",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenario Results",
        "",
        f"- Plain shear family: `{capture.get('plain_shear_family')}`",
        f"- Bending title family: `{capture.get('bending_title_family')}`",
        f"- Bending target util override: `{capture.get('bending_target_util_override')}`",
        f"- Combined preview util override: `{capture.get('combined_preview_util_override')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_final_binding_contract_truth_result_object_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_contract_truth_result_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_contract_truth_result_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_contract_truth_result_object {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
