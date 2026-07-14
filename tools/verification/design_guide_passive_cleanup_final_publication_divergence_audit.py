"""Lock passive cleanup advisory truth into final publication display.

The old failure mode was a page-level cleanup advisory banner while the final
Design Guide card said the design was efficient. This verifier locks the fix:
FinalDesignGuidePublication.display must consume the engine presentation/no-
action truth, and the legacy page-owned no-action banner render path must stay
deleted.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _capture() -> dict[str, Any]:
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8", errors="replace")
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    sample_item = {
        "title_main": "Design is efficient",
        "summary_line": "All checks pass.",
        "status": "PASS",
        "bucket": "pass",
        "guidance_intent": "already_efficient",
    }
    sample_debug = {
        "user_visible_no_action_reason": (
            "Cleanup is advisory for the current all-pass state because the available move set "
            "did not preserve every governing check while moving toward the target band."
        ),
        "stop_reason": "no_actionable_cleanup_candidate",
        "design_guide_presentation": {
            "headline": "Cleanup is advisory for this design state",
            "subtext": "No directly executable local reduction kept every governing check acceptable.",
            "css_bucket": "efficiency",
            "show_apply_button": False,
        },
    }
    # This is a static audit, not an import-time product call. The expected
    # current behaviour is inferred from source: display is built from item only
    # unless build_final_design_guide_display accepts debug/presentation.
    display_builder_accepts_debug = all(
        token in final_source
        for token in (
            "def build_final_design_guide_display(",
            "item: dict[str, Any] | None = None",
            "debug: dict[str, Any] | None = None",
            "debug_d = _mapping(debug)",
        )
    )
    publication_passes_debug_to_display = "build_final_design_guide_display(item=item_d, debug=debug_d)" in final_source
    presentation_consumed = all(
        token in final_source
        for token in (
            "design_guide_presentation",
            "presentation_d",
            "presentation_title",
            "presentation_summary",
        )
    )
    old_item_only_display_call = "display = build_final_design_guide_display(item=item_d)" in final_source
    legacy_banner_render_tokens = {
        "solver_no_action_info": "st.info(str(uvr))",
        "debug_bundle_no_action_info": "st.info(passive_reason)",
        "passive_stop_reason_caption": 'st.caption(f"Reason: {passive_stop_reason}.")',
    }
    legacy_banner_path_absent = all(
        token not in inputs_source for token in legacy_banner_render_tokens.values()
    )
    sample_expected_final_display = {
        "title": sample_debug["design_guide_presentation"]["headline"],
        "summary": sample_debug["design_guide_presentation"]["subtext"],
        "bucket": sample_debug["design_guide_presentation"]["css_bucket"],
        "source": "design_brain_engine_presentation",
    }
    sample_current_risk_display = {
        "title": sample_item["title_main"],
        "summary": sample_item["summary_line"],
        "bucket": sample_item["bucket"],
        "source": "legacy_item_only",
    }
    final_publication_consumes_presentation = bool(
        display_builder_accepts_debug
        and publication_passes_debug_to_display
        and presentation_consumed
        and not old_item_only_display_call
    )
    mismatch_guard_locked = bool(final_publication_consumes_presentation and legacy_banner_path_absent)
    return {
        "latest": {
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        },
        "source_markers": {
            "legacy_banner_path_absent": legacy_banner_path_absent,
            "legacy_banner_render_tokens_absent": {
                key: token not in inputs_source for key, token in legacy_banner_render_tokens.items()
            },
            "display_builder_accepts_debug": display_builder_accepts_debug,
            "publication_passes_debug_to_display": publication_passes_debug_to_display,
            "presentation_consumed": presentation_consumed,
            "old_item_only_display_call": old_item_only_display_call,
            "final_publication_consumes_presentation": final_publication_consumes_presentation,
        },
        "sample": {
            "item": sample_item,
            "debug": sample_debug,
            "expected_final_display": sample_expected_final_display,
            "current_risk_display": sample_current_risk_display,
            "gap_exists": not final_publication_consumes_presentation,
            "mismatch_guard_locked": mismatch_guard_locked,
        },
        "decision": "PASSIVE_CLEANUP_MISMATCH_GUARDED" if mismatch_guard_locked else "PASSIVE_CLEANUP_MISMATCH_RISK",
        "recommended_next_slice": (
            "Keep this verifier in the composed locks. If it fails, do not re-add a page-level banner; "
            "restore FinalDesignGuidePublication.display consumption of design_guide_presentation."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_markers = dict(capture.get("source_markers") or {})
    sample = dict(capture.get("sample") or {})
    return {
        "legacy_page_no_action_banner_deleted": bool(source_markers.get("legacy_banner_path_absent")),
        "final_publication_consumes_engine_presentation": bool(
            source_markers.get("final_publication_consumes_presentation")
        ),
        "sample_gap_closed": sample.get("gap_exists") is False,
        "mismatch_guard_locked": sample.get("mismatch_guard_locked") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    sample = dict(capture.get("sample") or {})
    lines = [
        "# Passive Cleanup Final Publication Divergence Audit",
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
            "## Finding",
            (
                "Mismatch risk remains." if sample.get("gap_exists")
                else "Final publication display consumes the presentation/no-action truth, and legacy page banner rendering is deleted."
            ),
            "",
            "## Expected Display Source",
            "```json",
            json.dumps(sample.get("expected_final_display") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Current Risk Display",
            "```json",
            json.dumps(sample.get("current_risk_display") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Next Slice",
            str(capture.get("recommended_next_slice") or ""),
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
    json_path = ARTIFACT_DIR / f"design_guide_passive_cleanup_final_publication_divergence_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_passive_cleanup_final_publication_divergence_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_passive_cleanup_final_publication_divergence {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
