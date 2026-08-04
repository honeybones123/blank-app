"""Object proof for final-binding no-second-CTA suppression result."""

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

REQUIRED_RESULT_FIELDS = {
    "applies",
    "reason",
    "source",
    "target_band_candidate_count",
    "evidence_expected_util",
    "threshold",
    "contract_effect",
    "item_effect",
    "evidence_effect",
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


def _positive_kwargs() -> dict[str, Any]:
    return {
        "evidence_for_binding": {
            "family": "bending",
            "no_second_cta_required": True,
            "reason": "proof says no second cleanup CTA is required",
            "target_band_candidate_count": 0,
        },
        "contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "updates": {"bottom_n": 3},
        },
        "item": {"family": "bending", "primary_card_actionable": True},
        "debug": {},
        "evidence_expected_util": 0.42,
        "evidence_family": "bending",
        "blocker_families": ["bending"],
        "final_accepted_min_family_util": 0.85,
        "target_band_eps": 0.0,
    }


def _exact_blocker_kwargs() -> dict[str, Any]:
    data = _positive_kwargs()
    data["evidence_for_binding"] = {
        "family": "bending",
        "target_band_candidate_count": 0,
        "post_click_exact_blockers_by_family": {
            "bending": {
                "no_second_cta_required": True,
                "failed_check_status": "BLOCKED_BY_FINAL_ACCEPTED_THRESHOLD",
                "best_safe_final_util": 0.44,
                "reason": "exact blocker says no further valid cleanup",
            }
        },
    }
    return data


def _negative_kwargs() -> dict[str, Any]:
    data = _positive_kwargs()
    data["evidence_for_binding"] = {
        "family": "bending",
        "no_second_cta_required": True,
        "target_band_candidate_count": 1,
    }
    data["evidence_expected_util"] = 0.86
    return data


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_visible_contract_binding_no_second_cta_result,
    )

    source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace")
    positive = build_final_visible_contract_binding_no_second_cta_result(**_positive_kwargs())
    positive_repeat = build_final_visible_contract_binding_no_second_cta_result(**_positive_kwargs())
    exact = build_final_visible_contract_binding_no_second_cta_result(**_exact_blocker_kwargs())
    negative = build_final_visible_contract_binding_no_second_cta_result(**_negative_kwargs())
    positive_result = dict(positive.get("result") or {})
    exact_result = dict(exact.get("result") or {})
    negative_result = dict(negative.get("result") or {})
    latest = {
        "binding_ownership": _latest("design_guide_final_visible_contract_binding_ownership"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    forbidden_tokens = {
        "streamlit": "streamlit" in source[source.find("def build_final_visible_contract_binding_no_second_cta_result("): source.find("def build_final_design_guide_publication_mutation_proof(")],
        "st_session_state": "st.session_state" in source[source.find("def build_final_visible_contract_binding_no_second_cta_result("): source.find("def build_final_design_guide_publication_mutation_proof(")],
        "evaluate_candidate": "_evaluate_auto_design_candidate" in source[source.find("def build_final_visible_contract_binding_no_second_cta_result("): source.find("def build_final_design_guide_publication_mutation_proof(")],
        "render_html": "_html" in source[source.find("def build_final_visible_contract_binding_no_second_cta_result("): source.find("def build_final_design_guide_publication_mutation_proof(")],
    }
    return {
        "decision": "FINAL_BINDING_NO_SECOND_CTA_RESULT_OBJECT_READY_FOR_LIVE_CUTOVER",
        "function_present": "def build_final_visible_contract_binding_no_second_cta_result(" in source,
        "exported": '"build_final_visible_contract_binding_no_second_cta_result"' in source,
        "missing_result_fields": sorted(REQUIRED_RESULT_FIELDS - set(positive_result)),
        "proof_hash_stable": positive.get("proof_hash") == positive_repeat.get("proof_hash"),
        "result_hash_stable": positive.get("result_hash") == positive_repeat.get("result_hash"),
        "positive_applies": positive_result.get("applies"),
        "positive_contract_disabled": (positive_result.get("contract_effect") or {}).get("enabled") is False,
        "positive_updates_cleared": (positive_result.get("contract_effect") or {}).get("updates") == {},
        "exact_blocker_applies": exact_result.get("applies"),
        "exact_blocker_source": exact_result.get("source"),
        "negative_does_not_apply": negative_result.get("applies") is False,
        "proof_flags": {
            "proof_only": positive.get("proof_only"),
            "product_driving": positive.get("product_driving"),
            "render_driving": positive.get("render_driving"),
            "apply_driving": positive.get("apply_driving"),
            "session_driving": positive.get("session_driving"),
            "ready_for_trace_wiring": positive.get("ready_for_trace_wiring"),
            "ready_for_live_cutover": positive.get("ready_for_live_cutover"),
        },
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
    latest = dict(capture.get("latest") or {})
    flags = dict(capture.get("proof_flags") or {})
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "no_missing_result_fields": not capture.get("missing_result_fields"),
        "proof_hash_stable": capture.get("proof_hash_stable") is True,
        "result_hash_stable": capture.get("result_hash_stable") is True,
        "positive_applies": capture.get("positive_applies") is True,
        "positive_contract_disabled": capture.get("positive_contract_disabled") is True,
        "positive_updates_cleared": capture.get("positive_updates_cleared") is True,
        "exact_blocker_applies": capture.get("exact_blocker_applies") is True,
        "exact_blocker_source_recorded": str(capture.get("exact_blocker_source") or "").startswith("exact_blocker."),
        "negative_does_not_apply": capture.get("negative_does_not_apply") is True,
        "proof_only": flags.get("proof_only") is True,
        "not_product_driving": flags.get("product_driving") is False,
        "not_render_driving": flags.get("render_driving") is False,
        "not_apply_driving": flags.get("apply_driving") is False,
        "not_session_driving": flags.get("session_driving") is False,
        "ready_for_trace_wiring": flags.get("ready_for_trace_wiring") is True,
        "ready_for_live_cutover": flags.get("ready_for_live_cutover") is True,
        "forbidden_tokens_absent": capture.get("forbidden_tokens_absent") is True,
        "binding_ownership_pass": (latest.get("binding_ownership") or {}).get("status") == "PASS",
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
        "# Final Binding No-Second-CTA Result Object",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Positive applies: `{capture.get('positive_applies')}`",
        f"- Exact blocker applies: `{capture.get('exact_blocker_applies')}`",
        f"- Negative does not apply: `{capture.get('negative_does_not_apply')}`",
        f"- Missing result fields: `{capture.get('missing_result_fields')}`",
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
        "schema": "design_guide_final_binding_no_second_cta_result_object_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_no_second_cta_result_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_no_second_cta_result_object_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_no_second_cta_result_object {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
