from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _slice_between(source: str, start: str, end: str) -> str:
    start_idx = source.index(start)
    end_idx = source.index(end, start_idx)
    return source[start_idx:end_idx]


def main() -> int:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    cleanup_body = _slice_between(
        source,
        "def _bending_only_target_band_cleanup_item(",
        "\ndef _post_click_low_bending_resolution_item(",
    )
    fallback_body = _slice_between(
        source,
        "design_guide_page.render_final_panel(",
        "\n    # --- 5. RENDER UI ---",
    )
    pre_render_body = _slice_between(
        source,
        "def _render_fresh_design_guide_panel() -> None:",
        "design_guide_page.render_final_panel(",
    )

    target_assignment = re.search(
        r'cand\["candidate_reaches_target_band"\]\s*=\s*bool\((.*?)\)',
        cleanup_body,
        flags=re.DOTALL,
    )
    target_expr = target_assignment.group(1).strip() if target_assignment else ""
    post_util_uses_bending = 'cand["candidate_post_util"] = float(candidate_bending_util)' in cleanup_body
    target_uses_bending = "candidate_bending_util" in target_expr
    target_does_not_use_governing_preview = "preview_util" not in target_expr
    governing_util_preserved = 'cand["candidate_governing_util"] = float(preview_util)' in cleanup_body

    pre_render_deleted_marker_present = '"pre_render_enabled_contract_shell_deleted"' in pre_render_body
    pre_render_marker_present = '"marker": "browser_enabled_contract_pre_render_shell_deleted"' in pre_render_body
    pre_render_renders_no_streamlit_button = "st.button(" not in pre_render_body
    pre_render_renders_no_direct_shell_card = "_design_guide_direct_action_shell_card_html(" not in pre_render_body
    pre_render_marker_idx = pre_render_body.index('"marker": "browser_enabled_contract_pre_render_shell_deleted"')
    pre_render_deleted_branch = pre_render_body[pre_render_marker_idx:]
    pre_render_does_not_return_before_final_panel = "\n            return\n" not in pre_render_deleted_branch
    direct_shell_call_lines = [
        line
        for line in source.splitlines()
        if "_design_guide_direct_action_shell_card_html(" in line
        and not line.lstrip().startswith("def _design_guide_direct_action_shell_card_html(")
    ]
    no_direct_shell_html_calls_remain = not direct_shell_call_lines
    direct_shell_helper_deleted = "def _design_guide_direct_action_shell_card_html(" not in source
    early_shear_direct_shell_deleted = '"marker": "early_shear_overdesign_direct_action_shell_deleted"' in source

    deleted_marker_present = '"fallback_enabled_contract_shell_deleted"' in fallback_body
    fallback_marker_present = '"marker": "fallback_enabled_contract_shell_deleted"' in fallback_body
    fallback_branch = _slice_between(
        fallback_body,
        '"marker": "fallback_enabled_contract_shell_deleted"',
        "st.session_state.pop(DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY, None)",
    )
    fallback_renders_no_streamlit_button = "st.button(" not in fallback_branch
    fallback_renders_no_direct_shell_card = "_design_guide_direct_action_shell_card_html(" not in fallback_branch

    checks = {
        "bending_cleanup_target_uses_bending_util": bool(target_uses_bending),
        "bending_cleanup_target_does_not_use_governing_preview_util": bool(target_does_not_use_governing_preview),
        "bending_cleanup_candidate_post_util_uses_bending_util": bool(post_util_uses_bending),
        "bending_cleanup_governing_util_preserved_for_debug": bool(governing_util_preserved),
        "pre_render_direct_cta_deleted_marker_present": bool(pre_render_deleted_marker_present),
        "pre_render_direct_cta_probe_marker_is_deleted": bool(pre_render_marker_present),
        "pre_render_direct_cta_renders_no_streamlit_button": bool(pre_render_renders_no_streamlit_button),
        "pre_render_direct_cta_renders_no_direct_shell_card": bool(pre_render_renders_no_direct_shell_card),
        "pre_render_direct_cta_does_not_return_before_final_panel": bool(pre_render_does_not_return_before_final_panel),
        "early_shear_overdesign_direct_shell_deleted_marker_present": bool(early_shear_direct_shell_deleted),
        "no_direct_shell_html_call_sites_remain": bool(no_direct_shell_html_calls_remain),
        "direct_shell_html_helper_deleted": bool(direct_shell_helper_deleted),
        "post_render_fallback_deleted_marker_present": bool(deleted_marker_present),
        "post_render_fallback_probe_marker_is_deleted": bool(fallback_marker_present),
        "post_render_fallback_renders_no_streamlit_button": bool(fallback_renders_no_streamlit_button),
        "post_render_fallback_renders_no_direct_shell_card": bool(fallback_renders_no_direct_shell_card),
    }
    failures = [name for name, ok in checks.items() if not ok]
    status = "PASS" if not failures else "FAIL"

    payload = {
        "status": status,
        "checks": checks,
        "failures": failures,
        "target_expression": target_expr,
        "direct_shell_call_lines": direct_shell_call_lines,
        "scope": {
            "bending_cleanup": "inputs_page.py:_bending_only_target_band_cleanup_item",
            "pre_render_direct_cta": "inputs_page.py:_render_fresh_design_guide_panel browser-test pre-render shell",
            "post_render_fallback": "inputs_page.py:_render_fresh_design_guide_panel after render_final_panel",
            "early_shear_direct_shell": "inputs_page.py early shear overdesign direct action shell",
        },
        "product_behaviour_intent": (
            "Bending-only cleanup may only claim target-band reach when bending utilisation itself "
            "is in range; legacy pre-render and post-render direct CTA shells must not draw duplicate CTAs."
        ),
    }

    stamp = _utc_stamp()
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    verification_path = VERIFICATION_DIR / f"design_guide_bending_cleanup_target_and_duplicate_cta_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_bending_cleanup_target_and_duplicate_cta_{stamp}.md"
    verification_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    audit_path.write_text(
        "\n".join(
            [
                "# Design Guide bending cleanup target and duplicate CTA snapshot",
                "",
                f"Result: **{status}**",
                "",
                "Checks:",
                *[f"- {name}: {'PASS' if ok else 'FAIL'}" for name, ok in checks.items()],
                "",
                f"Target expression: `{target_expr}`",
                "",
                "This verifier is intentionally narrow. It proves the regression boundary only:",
                "bending-only cleanup target acceptance and removal of duplicate direct CTA render branches.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"design guide bending cleanup target/duplicate CTA snapshot {status}")
    print(f"verification: {verification_path}")
    print(f"audit: {audit_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
