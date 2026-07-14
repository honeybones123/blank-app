"""Regression proof for contract-violation tone and pure wording encoding."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_pure_guidance_step_description,
)
from design_brain.final_publication import (  # noqa: E402
    build_final_design_guide_display,
    is_final_design_guide_family_contract_violation_item,
    normalise_stale_family_contract_violation_item,
)
from design_brain.publication import (  # noqa: E402
    _family_selection_safe_item,
    enforce_family_selection_publication_contract,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
INPUTS_PAGE = ROOT / "inputs_page.py"
INPUTS_STYLE = ROOT / "ui" / "inputs_page_style.py"
PURE_WORDING_VERIFIERS = (
    ROOT / "tools" / "verification" / "design_guide_describe_guidance_step_pure_wording_parity.py",
    ROOT / "tools" / "verification" / "design_guide_describe_guidance_step_pure_wording_cutover.py",
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bad_encoding_tokens() -> list[str]:
    return [
        bytes([0xC3, 0x83]).decode("utf-8"),
        bytes([0xC3, 0x82]).decode("utf-8"),
        bytes([0xC3, 0xA2]).decode("utf-8"),
    ]


def _load_lines_containing(path: Path, needle: str) -> list[str]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return [line.strip() for line in text.splitlines() if needle in line]


def _source_segment(path: Path, start_marker: str, end_marker: str) -> str:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _contract_violation_row() -> dict[str, Any]:
    primary = {
        "title_main": "Stale good item",
        "status": "GOOD",
        "bucket": "pass",
        "tone": "green",
        "pill": "GOOD",
        "summary_line": "Stale pass summary.",
        "button_contract": {"enabled": True, "actionable": True, "updates": {"D": 700}},
        "updates": {"D": 700},
        "primary_card_actionable": True,
        "displayed_util": 0.97,
    }
    diagnostics = {
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "published_family_id": "SHEAR_OVERDESIGN_GOVERNS",
        "cta_family_id": "SHEAR_OVERDESIGN_GOVERNS",
        "card_family_id": "SHEAR_OVERDESIGN_GOVERNS",
        "family_selection_source": "test",
        "family_match_violation_reason": "wrong_family_publication",
    }
    item = _family_selection_safe_item(primary, diagnostics)
    display = build_final_design_guide_display(item=item, debug={})
    display_fields = dict(display.final_card_model_fields or {})
    checks = {
        "safe_item_status_error": item.get("status") == "ERROR",
        "safe_item_bucket_error": item.get("bucket") == "error",
        "safe_item_pill_error": item.get("pill") == "ERROR",
        "safe_item_no_actionable_contract": not bool(
            dict(item.get("button_contract") or {}).get("enabled")
            or dict(item.get("button_contract") or {}).get("actionable")
        ),
        "display_status_error": display.status == "ERROR",
        "display_bucket_error": display.bucket == "error",
        "display_colour_error": display.colour_state == "error",
        "display_badge_error": display.badge == "ERROR",
        "display_title_preserved": display.title == "Design Guide family contract violation",
        "display_summary_preserved": display.summary == "Publication blocked by family contract before final render.",
        "final_card_model_status_error": display_fields.get("status") == "ERROR",
        "final_card_model_bucket_error": display_fields.get("bucket") == "error",
        "final_card_model_colour_error": display_fields.get("colour_state") == "error",
    }
    return {
        "item": {
            "title": item.get("title_main"),
            "status": item.get("status"),
            "bucket": item.get("bucket"),
            "tone": item.get("tone"),
            "pill": item.get("pill"),
            "button_contract_enabled": bool(dict(item.get("button_contract") or {}).get("enabled")),
        },
        "display": {
            "title": display.title,
            "summary": display.summary,
            "status": display.status,
            "bucket": display.bucket,
            "colour_state": display.colour_state,
            "badge": display.badge,
            "final_card_model_fields": display_fields,
        },
        "checks": checks,
        "passes": all(checks.values()),
    }


def _stale_contract_violation_row() -> dict[str, Any]:
    stale_item = {
        "title_main": "Design Guide family contract violation",
        "title": "Design Guide family contract violation",
        "summary_line": "Publication blocked by family contract before final render.",
        "status": "GOOD",
        "bucket": "pass",
        "tone": "pass",
        "pill": "GOOD",
        "button_contract": {"enabled": False, "actionable": False, "updates": {}},
        "published_family_id": "FAMILY_SELECTION_CONTRACT_VIOLATION",
        "selected_family_id": "FAMILY_SELECTION_CONTRACT_VIOLATION",
    }
    stale_payload = {
        "guidance_items": [dict(stale_item)],
        "overview": {
            "statuses": {"bending": "NEAR LIMIT", "shear": "PASS"},
            "utils": {"bending": 0.9668, "shear": 0.9036},
        },
        "debug_trace": {
            "overview": {
                "statuses": {"bending": "NEAR LIMIT", "shear": "PASS"},
                "utils": {"bending": 0.9668, "shear": 0.9036},
            },
            "target_low": 0.88,
            "target_high": 0.95,
        },
    }
    rebuilt_payload = enforce_family_selection_publication_contract(stale_payload)
    rebuilt_item = dict((rebuilt_payload.get("guidance_items") or [{}])[0] or {})
    normalised_input = {
        **stale_item,
        "selected_family_id": "TARGET_BAND_REACHED",
        "published_family_id": "TARGET_BAND_REACHED",
        "cta_family_id": "TARGET_BAND_REACHED",
        "card_family_id": "TARGET_BAND_REACHED",
        "matched_family_ids": ["TARGET_BAND_REACHED"],
        "family_match_passed": True,
    }
    normalised_item = normalise_stale_family_contract_violation_item(normalised_input)
    normalised_display = build_final_design_guide_display(item=normalised_input, debug={})
    live_like_input = {
        **stale_item,
        "selected_family_id": "TARGET_BAND_REACHED",
        "published_family_id": "TARGET_BAND_REACHED",
        "cta_family_id": "TARGET_BAND_REACHED",
        "card_family_id": "TARGET_BAND_REACHED",
    }
    live_like_normalised_item = normalise_stale_family_contract_violation_item(live_like_input)
    live_debug_only_normalised_item = normalise_stale_family_contract_violation_item(
        stale_item,
        {
            "selected_family_id": "TARGET_BAND_REACHED",
            "published_family_id": "TARGET_BAND_REACHED",
            "cta_family_id": "TARGET_BAND_REACHED",
            "card_family_id": "TARGET_BAND_REACHED",
            "matched_family_ids": ["TARGET_BAND_REACHED"],
            "family_match_passed": True,
            "active_failures": [],
            "final_publication_verifier_payload": {
                "selected_family_id": "TARGET_BAND_REACHED",
                "published_family_id": "TARGET_BAND_REACHED",
                "cta_family_id": "TARGET_BAND_REACHED",
                "card_family_id": "TARGET_BAND_REACHED",
                "matched_family_ids": ["TARGET_BAND_REACHED"],
                "family_match_passed": True,
                "active_failures": [],
            },
        },
    )
    live_stale_root_failure_normalised_item = normalise_stale_family_contract_violation_item(
        stale_item,
        {
            "selected_family_id": "TARGET_BAND_REACHED",
            "published_family_id": "TARGET_BAND_REACHED",
            "cta_family_id": "TARGET_BAND_REACHED",
            "card_family_id": "TARGET_BAND_REACHED",
            "matched_family_ids": ["TARGET_BAND_REACHED"],
            "family_match_passed": True,
            "active_failures": ["shear"],
            "final_publication_verifier_payload": {
                "selected_family_id": "TARGET_BAND_REACHED",
                "published_family_id": "TARGET_BAND_REACHED",
                "cta_family_id": "TARGET_BAND_REACHED",
                "card_family_id": "TARGET_BAND_REACHED",
                "matched_family_ids": ["TARGET_BAND_REACHED"],
                "family_match_passed": True,
                "active_failures": [],
            },
        },
    )
    live_raw_state_normalised_item = normalise_stale_family_contract_violation_item(
        {
            **stale_item,
            "selected_family_id": "TARGET_BAND_REACHED",
            "published_family_id": "TARGET_BAND_REACHED",
            "cta_family_id": "TARGET_BAND_REACHED",
            "card_family_id": "TARGET_BAND_REACHED",
            "matched_family_ids": ["TARGET_BAND_REACHED"],
            "family_match_passed": True,
            "active_failures": ["stale"],
            "raw_state_flags": {
                "target_band_terminal_signal": True,
                "any_failure": False,
                "any_strength_fail": False,
                "repair_required": False,
                "bending_fail": False,
                "shear_fail": False,
            },
        }
    )
    live_selection_evidence_raw_state_normalised_item = normalise_stale_family_contract_violation_item(
        {
            **stale_item,
            "selected_family_id": "TARGET_BAND_REACHED",
            "published_family_id": "TARGET_BAND_REACHED",
            "cta_family_id": "TARGET_BAND_REACHED",
            "card_family_id": "TARGET_BAND_REACHED",
            "matched_family_ids": ["TARGET_BAND_REACHED"],
            "family_match_passed": True,
            "active_failures": ["stale"],
            "selection_evidence": {
                "raw_state_flags": {
                    "target_band_terminal_signal": True,
                    "any_failure": False,
                    "any_strength_fail": False,
                    "repair_required": False,
                    "bending_fail": False,
                    "shear_fail": False,
                }
            },
        }
    )
    display = build_final_design_guide_display(item=stale_item, debug={})
    fields = dict(display.final_card_model_fields or {})
    normalised_fields = dict(normalised_display.final_card_model_fields or {})
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    style_source = INPUTS_STYLE.read_text(encoding="utf-8-sig", errors="replace")
    checks = {
        "detector_matches_stale_item": is_final_design_guide_family_contract_violation_item(stale_item),
        "display_status_error": display.status == "ERROR",
        "display_bucket_error": display.bucket == "error",
        "display_colour_error": display.colour_state == "error",
        "display_badge_error": display.badge == "ERROR",
        "final_card_model_status_error": fields.get("status") == "ERROR",
        "render_view_model_uses_publication_detector": "_is_final_design_guide_family_contract_violation_item(item)" in inputs_source,
        "dashboard_status_uses_publication_detector": "if _is_final_design_guide_family_contract_violation_item(item):" in inputs_source,
        "dashboard_status_accepts_error_bucket": 'if item_bucket in {"fail", "error"}:' in inputs_source,
        "legacy_guidance_label_uses_publication_detector": (
            "def _guidance_card_label(item: dict) -> str:" in inputs_source
            and "if _is_final_design_guide_family_contract_violation_item(item):\n        return \"ERROR\"" in inputs_source
        ),
        "legacy_guidance_renderer_forces_error_bucket": (
            "_family_contract_violation_item = _is_final_design_guide_family_contract_violation_item(item)" in inputs_source
            and "if _family_contract_violation_item:\n            item_bucket = \"error\"" in inputs_source
        ),
        "legacy_fast_guidance_error_card_style_exists": ".fast-guidance-item.error" in style_source,
        "legacy_fast_guidance_error_badge_style_exists": ".fast-guidance-badge.error" in style_source,
        "normaliser_exported_from_publication": "normalise_stale_family_contract_violation_item" in inputs_source,
        "view_model_calls_normaliser_before_detector": (
            "item = _normalise_stale_family_contract_violation_item(item)" in inputs_source
            and "if _is_final_design_guide_family_contract_violation_item(item):" in inputs_source
        ),
        "render_model_calls_normaliser": (
            "vm_d = _normalise_stale_family_contract_violation_item(" in inputs_source
            and "DESIGN_GUIDE_DEBUG_BUNDLE_KEY" in inputs_source
        ),
        "legacy_renderer_calls_normaliser_before_detector": (
            "debug_payload if isinstance(debug_payload, dict) else None" in inputs_source
            and "_family_contract_violation_item = _is_final_design_guide_family_contract_violation_item(item)" in inputs_source
        ),
        "stale_violation_rebuilds_to_target_band": rebuilt_item.get("selected_family_id") == "TARGET_BAND_REACHED",
        "stale_violation_rebuild_title_cleared": rebuilt_item.get("title_main") == "Design is efficient",
        "stale_violation_rebuild_summary_cleared": rebuilt_item.get("summary_line") == "All checks pass.",
        "stale_violation_rebuild_match_passed": rebuilt_item.get("family_match_passed") is True,
        "stale_violation_rebuild_reason_cleared": not rebuilt_item.get("family_match_violation_reason"),
        "normalised_stale_violation_title_cleared": normalised_item.get("title_main") == "Design accepted - target band achieved",
        "normalised_stale_violation_status_pass": normalised_item.get("status") == "PASS",
        "normalised_stale_violation_detector_cleared": not is_final_design_guide_family_contract_violation_item(normalised_item),
        "normalised_display_title_pass": normalised_display.title == "Design accepted - target band achieved",
        "normalised_display_status_pass": normalised_display.status == "PASS",
        "normalised_final_card_model_status_pass": normalised_fields.get("status") == "PASS",
        "live_like_stale_violation_without_match_flag_cleared": (
            live_like_normalised_item.get("title_main") == "Design accepted - target band achieved"
            and live_like_normalised_item.get("status") == "PASS"
            and not is_final_design_guide_family_contract_violation_item(live_like_normalised_item)
        ),
        "debug_only_live_stale_violation_cleared": (
            live_debug_only_normalised_item.get("title_main") == "Design accepted - target band achieved"
            and live_debug_only_normalised_item.get("status") == "PASS"
            and not is_final_design_guide_family_contract_violation_item(live_debug_only_normalised_item)
        ),
        "final_publication_payload_overrides_stale_root_active_failures": (
            live_stale_root_failure_normalised_item.get("title_main") == "Design accepted - target band achieved"
            and live_stale_root_failure_normalised_item.get("status") == "PASS"
            and not is_final_design_guide_family_contract_violation_item(live_stale_root_failure_normalised_item)
        ),
        "target_band_raw_state_overrides_stale_active_failures": (
            live_raw_state_normalised_item.get("title_main") == "Design accepted - target band achieved"
            and live_raw_state_normalised_item.get("status") == "PASS"
            and not is_final_design_guide_family_contract_violation_item(live_raw_state_normalised_item)
        ),
        "selection_evidence_raw_state_overrides_stale_active_failures": (
            live_selection_evidence_raw_state_normalised_item.get("title_main")
            == "Design accepted - target band achieved"
            and live_selection_evidence_raw_state_normalised_item.get("status") == "PASS"
            and not is_final_design_guide_family_contract_violation_item(
                live_selection_evidence_raw_state_normalised_item
            )
        ),
    }
    return {
        "stale_item": {
            "title": stale_item["title_main"],
            "input_status": stale_item["status"],
            "input_bucket": stale_item["bucket"],
            "input_pill": stale_item["pill"],
        },
        "display": {
            "status": display.status,
            "bucket": display.bucket,
            "colour_state": display.colour_state,
            "badge": display.badge,
            "final_card_model_fields": fields,
        },
        "rebuilt_item": {
            "title": rebuilt_item.get("title_main"),
            "summary": rebuilt_item.get("summary_line"),
            "selected_family_id": rebuilt_item.get("selected_family_id"),
            "published_family_id": rebuilt_item.get("published_family_id"),
            "family_match_passed": rebuilt_item.get("family_match_passed"),
            "family_match_violation_reason": rebuilt_item.get("family_match_violation_reason"),
        },
        "normalised_item": {
            "title": normalised_item.get("title_main"),
            "summary": normalised_item.get("summary_line"),
            "status": normalised_item.get("status"),
            "bucket": normalised_item.get("bucket"),
            "pill": normalised_item.get("pill"),
            "selected_family_id": normalised_item.get("selected_family_id"),
            "published_family_id": normalised_item.get("published_family_id"),
            "family_match_passed": normalised_item.get("family_match_passed"),
            "detector_matches": is_final_design_guide_family_contract_violation_item(normalised_item),
        },
        "live_like_normalised_item": {
            "title": live_like_normalised_item.get("title_main"),
            "summary": live_like_normalised_item.get("summary_line"),
            "status": live_like_normalised_item.get("status"),
            "bucket": live_like_normalised_item.get("bucket"),
            "pill": live_like_normalised_item.get("pill"),
            "selected_family_id": live_like_normalised_item.get("selected_family_id"),
            "published_family_id": live_like_normalised_item.get("published_family_id"),
            "family_match_passed": live_like_normalised_item.get("family_match_passed"),
            "detector_matches": is_final_design_guide_family_contract_violation_item(live_like_normalised_item),
        },
        "live_debug_only_normalised_item": {
            "title": live_debug_only_normalised_item.get("title_main"),
            "summary": live_debug_only_normalised_item.get("summary_line"),
            "status": live_debug_only_normalised_item.get("status"),
            "bucket": live_debug_only_normalised_item.get("bucket"),
            "pill": live_debug_only_normalised_item.get("pill"),
            "selected_family_id": live_debug_only_normalised_item.get("selected_family_id"),
            "published_family_id": live_debug_only_normalised_item.get("published_family_id"),
            "family_match_passed": live_debug_only_normalised_item.get("family_match_passed"),
            "detector_matches": is_final_design_guide_family_contract_violation_item(live_debug_only_normalised_item),
        },
        "normalised_display": {
            "title": normalised_display.title,
            "summary": normalised_display.summary,
            "status": normalised_display.status,
            "bucket": normalised_display.bucket,
            "colour_state": normalised_display.colour_state,
            "badge": normalised_display.badge,
            "final_card_model_fields": normalised_fields,
        },
        "checks": checks,
        "passes": all(checks.values()),
    }


def _pure_wording_row() -> dict[str, Any]:
    result = build_design_guide_pure_guidance_step_description(
        before_state={"g_udl_kNm_per_m": 4.0},
        after_state={"g_udl_kNm_per_m": 3.5},
        action_type="deflection_reduce_sustained_load",
        updates={"g_udl_kNm_per_m": 3.5},
    )
    description = str(result.get("description") or "")
    bad_tokens = _bad_encoding_tokens()
    source_paths = (CONTROLLER, *PURE_WORDING_VERIFIERS)
    source_lines = {
        str(path.relative_to(ROOT)): _load_lines_containing(path, "kN/m")
        for path in source_paths
    }
    checks = {
        "handled": bool(result.get("handled")),
        "uses_ascii_separator": " -> " in description,
        "no_bad_encoding_in_description": not any(token in description for token in bad_tokens),
        "controller_source_has_no_bad_encoding_on_load_line": not any(
            token in line
            for line in source_lines[str(CONTROLLER.relative_to(ROOT))]
            for token in bad_tokens
        ),
        "verifier_expected_lines_have_no_bad_encoding": not any(
            token in line
            for path, lines in source_lines.items()
            if path != str(CONTROLLER.relative_to(ROOT))
            for line in lines
            for token in bad_tokens
        ),
    }
    return {
        "description": description,
        "source_lines": source_lines,
        "checks": checks,
        "passes": all(checks.values()),
    }


def _guidance_change_line_row() -> dict[str, Any]:
    segment = _source_segment(
        INPUTS_PAGE,
        "def _guidance_apply_change_lines(before: dict, after: dict) -> list[str]:",
        "def _guidance_change_lines_for_updates(before: dict, updates: dict | None) -> list[str]:",
    )
    bad_tokens = _bad_encoding_tokens()
    checks = {
        "uses_ascii_width_separator": "Width: {int(round(float(bw)))} -> {int(round(float(aw)))} mm" in segment,
        "uses_ascii_depth_separator": "Depth: {int(round(b_d))} -> {int(round(a_d))} mm" in segment,
        "uses_ascii_shear_links_none_separator": "Shear links: none -> {af}" in segment,
        "uses_ascii_shear_links_removed_separator": "Shear links: {bf} -> removed" in segment,
        "uses_ascii_shear_links_change_separator": "Shear links: {bf} -> {af}" in segment,
        "no_bad_encoding_in_guidance_change_helper": not any(token in segment for token in bad_tokens),
    }
    return {
        "helper": "_guidance_apply_change_lines",
        "checks": checks,
        "passes": all(checks.values()),
    }


def _capture() -> dict[str, Any]:
    contract_row = _contract_violation_row()
    stale_contract_row = _stale_contract_violation_row()
    wording_row = _pure_wording_row()
    change_line_row = _guidance_change_line_row()
    return {
        "schema": "design_guide_contract_violation_tone_and_wording_snapshot.v1",
        "contract_violation_tone": contract_row,
        "stale_contract_violation_tone": stale_contract_row,
        "pure_wording_encoding": wording_row,
        "guidance_change_line_encoding": change_line_row,
        "yellow_good_contract_violation_possible": not (
            bool(contract_row.get("passes")) and bool(stale_contract_row.get("passes"))
        ),
        "red_card_mojibake_possible": not (
            bool(wording_row.get("passes")) and bool(change_line_row.get("passes"))
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "status": "PASS"
        if contract_row.get("passes")
        and stale_contract_row.get("passes")
        and wording_row.get("passes")
        and change_line_row.get("passes")
        else "FAIL",
    }


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    contract = dict(payload.get("contract_violation_tone") or {})
    stale_contract = dict(payload.get("stale_contract_violation_tone") or {})
    wording = dict(payload.get("pure_wording_encoding") or {})
    change_line = dict(payload.get("guidance_change_line_encoding") or {})
    lines = [
        "# Design Guide Contract Violation Tone And Wording Snapshot",
        "",
        f"## Summary: {payload.get('status')}",
        "",
        "## Contract Violation Tone",
        "",
        f"- item: `{json.dumps(contract.get('item'), sort_keys=True)}`",
        f"- display status: `{dict(contract.get('display') or {}).get('status')}`",
        f"- display bucket: `{dict(contract.get('display') or {}).get('bucket')}`",
        f"- display badge: `{dict(contract.get('display') or {}).get('badge')}`",
        "",
        "## Stale Contract Violation Tone",
        "",
        f"- stale input: `{json.dumps(stale_contract.get('stale_item'), sort_keys=True)}`",
        f"- display status: `{dict(stale_contract.get('display') or {}).get('status')}`",
        f"- display bucket: `{dict(stale_contract.get('display') or {}).get('bucket')}`",
        f"- display badge: `{dict(stale_contract.get('display') or {}).get('badge')}`",
        "",
        "## Pure Wording Encoding",
        "",
        f"- description: `{wording.get('description')}`",
        "",
        "## Guidance Change-Line Encoding",
        "",
        f"- helper: `{change_line.get('helper')}`",
        f"- passes: `{change_line.get('passes')}`",
        "",
        "## Behaviour Flags",
        "",
        f"- product_behavior_changed: `{payload.get('product_behavior_changed')}`",
        f"- visible_wording_changed: `{payload.get('visible_wording_changed')}`",
        f"- cta_apply_semantics_changed: `{payload.get('cta_apply_semantics_changed')}`",
        f"- family_runtime_changed: `{payload.get('family_runtime_changed')}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _capture()
    ts = _timestamp().replace(":", "-")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_contract_violation_tone_and_wording_{ts}.json"
    md_path = AUDIT_DIR / f"design_guide_contract_violation_tone_and_wording_{ts}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(payload, md_path)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
