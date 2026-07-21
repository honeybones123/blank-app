"""Lock the current post-Apply smoothness root-cause classification.

Proof-only. This verifier composes the latest live post-Apply smoothness
profiles and model/diagram reuse gates so the next performance slice is aimed
at the real remaining hotspot instead of product logic that is already bounded.

It does not change product behaviour, engineering logic, family runtimes,
publication, CTA/apply routing, visible wording, widget keys, or rendering.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "payload": payload, "status": payload.get("status")}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return dict(value) if isinstance(value, dict) else {}


def _classification(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("classification")
    return dict(value) if isinstance(value, dict) else {}


def _capture() -> dict[str, Any]:
    broad = _latest("design_guide_browser_live_smoothness_profile")
    post_apply = _latest("design_guide_post_apply_settle_source_profile")
    state_write = _latest("design_guide_same_session_post_apply_state_write_profile")
    post_apply_reuse = _latest("design_guide_model_diagram_post_apply_reuse_readiness")
    stable_reuse = _latest("design_guide_model_diagram_stable_post_apply_reuse_proof")
    reuse_trace = _latest("design_guide_model_diagram_render_reuse_trace")
    reuse_impl = _latest("design_guide_model_diagram_render_reuse_implementation")
    family_fuzz = _latest("family_10_fuzz_audit")
    render_lock = _latest("design_guide_render_bridge_lock")
    independence_lock = _latest("design_guide_independence_lock")

    post_summary = _summary(post_apply.get("payload") or {})
    broad_hotspots = list((broad.get("payload") or {}).get("top_hotspots") or [])
    state_cls = _classification(state_write.get("payload") or {})

    return {
        "broad_smoothness": {
            "path": broad.get("path"),
            "status": broad.get("status"),
            "top_hotspots": broad_hotspots[:3],
        },
        "post_apply_source_profile": {
            "path": post_apply.get("path"),
            "status": post_apply.get("status"),
            "decision": post_summary.get("decision"),
            "focused_post_click_top_owner": post_summary.get("focused_post_click_top_owner"),
            "focused_post_click_owner_totals": post_summary.get("focused_post_click_owner_totals"),
            "candidate_count": post_summary.get("candidate_count"),
            "candidate_product_ms_estimate": post_summary.get("candidate_product_ms_estimate"),
            "post_apply_elapsed_ms": post_summary.get("post_apply_elapsed_ms"),
            "post_apply_milestones_ms": post_summary.get("post_apply_milestones_ms"),
            "risks": post_summary.get("risks"),
            "recommended_next_slice": post_summary.get("recommended_next_slice"),
        },
        "same_session_state_write_profile": {
            "path": state_write.get("path"),
            "status": state_write.get("status"),
            "decision": state_cls.get("decision"),
            "likely_sources": state_cls.get("likely_sources"),
            "pending_after_apply": state_cls.get("pending_after_apply"),
            "pending_after_rerun": state_cls.get("pending_after_rerun"),
            "rebuild_deltas_after_stable_post_apply_rerun": state_cls.get(
                "rebuild_deltas_after_stable_post_apply_rerun"
            ),
            "stable_post_apply_to_rerun_authority": state_cls.get("stable_post_apply_to_rerun_authority"),
        },
        "model_diagram_reuse_gates": {
            "post_apply_reuse_readiness": {
                "path": post_apply_reuse.get("path"),
                "status": post_apply_reuse.get("status"),
                "decision": (post_apply_reuse.get("payload") or {}).get("decision")
                or _summary(post_apply_reuse.get("payload") or {}).get("decision"),
            },
            "stable_post_apply_reuse_proof": {
                "path": stable_reuse.get("path"),
                "status": stable_reuse.get("status"),
                "decision": _summary(stable_reuse.get("payload") or {}).get("decision"),
            },
            "render_reuse_trace": {
                "path": reuse_trace.get("path"),
                "status": reuse_trace.get("status"),
                "classification": _classification(reuse_trace.get("payload") or {}),
            },
            "render_reuse_implementation": {
                "path": reuse_impl.get("path"),
                "status": reuse_impl.get("status"),
                "classification": _classification(reuse_impl.get("payload") or {}),
            },
        },
        "locks": {
            "family_10_fuzz": {
                "path": family_fuzz.get("path"),
                "result": (family_fuzz.get("payload") or {}).get("result"),
                "summary": (family_fuzz.get("payload") or {}).get("summary"),
            },
            "render_bridge_lock": {
                "path": render_lock.get("path"),
                "status": render_lock.get("status"),
            },
            "independence_lock": {
                "path": independence_lock.get("path"),
                "status": independence_lock.get("status"),
            },
        },
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    post = dict(capture.get("post_apply_source_profile") or {})
    state = dict(capture.get("same_session_state_write_profile") or {})
    gates = dict(capture.get("model_diagram_reuse_gates") or {})
    locks = dict(capture.get("locks") or {})
    family_summary = dict((locks.get("family_10_fuzz") or {}).get("summary") or {})

    checks = {
        "post_apply_profile_passed": post.get("status") == "PASS",
        "post_apply_model_or_chart_hotspot": post.get("decision") == "POST_APPLY_MODEL_OR_CHART_MUTATION_HOTSPOT",
        "post_apply_candidate_work_bounded": int(post.get("candidate_count") or 0) == 0
        and float(post.get("candidate_product_ms_estimate") or 0.0) == 0.0,
        "plotly_or_chart_is_top_focused_owner": post.get("focused_post_click_top_owner") == "plotly_or_chart",
        "state_write_profile_passed": state.get("status") == "PASS",
        "stable_post_apply_authority_holds": state.get("stable_post_apply_to_rerun_authority") is True,
        "pending_flags_clear": state.get("pending_after_apply") is False and state.get("pending_after_rerun") is False,
        "post_apply_changed_model_render_is_required": (
            (gates.get("post_apply_reuse_readiness") or {}).get("status") == "PASS"
            and (gates.get("post_apply_reuse_readiness") or {}).get("decision")
            == "INITIAL_POST_APPLY_RENDER_REQUIRED_BY_CHANGED_MODEL_FINGERPRINT"
        ),
        "stable_reuse_proof_passed": (
            (gates.get("stable_post_apply_reuse_proof") or {}).get("status") == "PASS"
        ),
        "model_render_reuse_trace_passed": (gates.get("render_reuse_trace") or {}).get("status") == "PASS",
        "model_render_reuse_implementation_passed": (
            (gates.get("render_reuse_implementation") or {}).get("status") == "PASS"
        ),
        "family_live_fuzz_passed": (locks.get("family_10_fuzz") or {}).get("result") == "LIVE_EXECUTION_PASS"
        and int(family_summary.get("button_action_failures") or 0) == 0,
        "render_bridge_lock_passed": (locks.get("render_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_passed": (locks.get("independence_lock") or {}).get("status") == "PASS",
    }
    missing = [key for key, ok in checks.items() if not ok]

    if missing:
        decision = "POST_APPLY_SMOOTHNESS_ROOT_CAUSE_NOT_LOCKED"
        next_slice = "Resolve missing proof checks before implementing another smoothness change."
    else:
        decision = "POST_APPLY_MODEL_REPAINT_ROOT_CAUSE_LOCKED"
        next_slice = (
            "Do not bypass the first post-Apply model redraw when the model fingerprint changes. "
            "Next safe performance slice is a visual-only model panel stability/placeholder proof or "
            "Plotly render-cost profiling, with final publication/family/apply logic untouched."
        )

    return {
        "status": "PASS" if not missing else "FAIL",
        "decision": decision,
        "checks": checks,
        "missing_checks": missing,
        "product_behaviour_changed": False,
        "blocked_wrong_fix_paths": [
            "Do not skip changed-fingerprint model render after Apply.",
            "Do not optimize candidate evaluation from this profile; product candidate count is zero.",
            "Do not change family runtimes, CTA/apply routing, publication, or wording for this hotspot.",
        ],
        "recommended_next_slice": next_slice,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["timestamp"])
    json_path = ARTIFACT_DIR / f"app_stability_post_apply_smoothness_root_cause_lock_{stamp}.json"
    md_path = AUDIT_DIR / f"app_stability_post_apply_smoothness_root_cause_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    cls = dict(payload.get("classification") or {})
    lines = [
        "# App Stability Post-Apply Smoothness Root Cause Lock",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{cls.get('decision')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (cls.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Root Cause Evidence",
            "",
            "```json",
            json.dumps(
                {
                    "post_apply_source_profile": payload.get("post_apply_source_profile"),
                    "same_session_state_write_profile": payload.get("same_session_state_write_profile"),
                    "model_diagram_reuse_gates": payload.get("model_diagram_reuse_gates"),
                },
                indent=2,
                sort_keys=True,
                default=str,
            )[:14000],
            "```",
            "",
            "## Blocked Wrong Fix Paths",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in cls.get("blocked_wrong_fix_paths") or [])
    lines.extend(["", "## Recommended Next Slice", "", str(cls.get("recommended_next_slice") or ""), ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    capture = _capture()
    classification = _classify(capture)
    payload = {
        "schema": "app_stability_post_apply_smoothness_root_cause_lock.v1",
        "timestamp": _stamp(),
        "status": classification["status"],
        "product_behaviour_changed": False,
        **capture,
        "classification": classification,
    }
    json_path, md_path = _write(payload)
    print(f"app_stability_post_apply_smoothness_root_cause_lock {payload['status']}")
    print(f"decision={classification['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
