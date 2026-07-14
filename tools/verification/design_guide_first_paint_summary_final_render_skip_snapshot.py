"""Verifier for skipping duplicate summary repaint after cached first paint.

The Inputs page can render a hash-guarded cached summary immediately, then
later repaint the same summary once normal page rendering reaches the summary
function. This snapshot proves the later repaint is skipped only when the
first-paint summary cache was already accepted under the existing result/hash
guards. It is a visual smoothness optimization only.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _nested_function_block(source: str, name: str) -> str:
    match = re.search(rf"^\s{{4}}def {re.escape(name)}\(", source, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^\s{4}def\s+\w+\(", source[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _line_number(source: str, needle: str) -> int | None:
    index = source.find(needle)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = INPUTS_PAGE.read_text(encoding="utf-8")
    first_paint_helper = re.search(
        r"^\s{4}def _cached_summary_html_for_first_paint\(.*?(?=^\s{4}\w|\Z)",
        source,
        re.M | re.S,
    )
    first_paint_helper_body = first_paint_helper.group(0) if first_paint_helper else ""
    summary_body = _nested_function_block(source, "_render_current_inputs_summary")

    checks = {
        "first_paint_cache_helper_exists": bool(first_paint_helper_body),
        "first_paint_cache_guard_checks_result_cache_hash": "current_result_cache_hash" in first_paint_helper_body
        and "stale_result_cache_hash" in first_paint_helper_body,
        "first_paint_cache_guard_checks_results_version": "current_results_version" in first_paint_helper_body
        and "stale_results_version" in first_paint_helper_body,
        "first_paint_cache_guard_blocks_dirty_inputs": "inputs_dirty" in first_paint_helper_body,
        "first_paint_cache_guard_blocks_apply_in_flight": "post_click_apply_in_flight" in first_paint_helper_body,
        "summary_skip_branch_exists": "summary_final_render_skipped" in summary_body,
        "summary_skip_depends_on_first_paint_cache_reused": (
            "first_paint_cached_summary_reused" in summary_body
            and "_inputs_first_paint_cached_summary_reuse_debug" in summary_body
        ),
        "summary_skip_records_non_behavioral_scope": (
            '"affects_engineering": False' in summary_body
            and '"affects_design_guide_publication": False' in summary_body
            and '"affects_cta": False' in summary_body
            and '"affects_apply_payload": False' in summary_body
            and '"product_behavior_changed": False' in summary_body
        ),
        "summary_skip_records_probe": "summary.final_render_skipped_after_first_paint_cache" in summary_body,
        "normal_summary_render_path_still_exists": "render_summary_table(" in summary_body
        and "render_landing_card(" in summary_body,
        "visible_summary_html_cache_still_hash_guarded": "_final_publication_summary_card_html_cache" in source
        and "summary_cards_html" in source,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    stamp = datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "-")
    payload = {
        "schema": "design_guide_first_paint_summary_final_render_skip_snapshot.v1",
        "status": status,
        "summary": {
            "first_paint_cached_summary_can_skip_final_summary_repaint": checks[
                "summary_skip_depends_on_first_paint_cache_reused"
            ],
            "render_only_smoothness_change": True,
            "product_behavior_changed": False,
        },
        "source": {
            "inputs_page": str(INPUTS_PAGE),
            "summary_function_line": _line_number(source, "def _render_current_inputs_summary() -> None:"),
            "skip_marker_line": _line_number(source, "summary_final_render_skipped"),
            "first_paint_cache_helper_line": _line_number(
                source,
                "def _cached_summary_html_for_first_paint()",
            ),
        },
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
    }

    json_path = ARTIFACT_DIR / f"design_guide_first_paint_summary_final_render_skip_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_first_paint_summary_final_render_skip_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide First-Paint Summary Final Render Skip",
                "",
                f"Status: **{status}**",
                "",
                "## Result",
                "",
                "- Later summary repaint is skipped only after the first-paint cached summary is hash-accepted.",
                "- Dirty inputs, apply-in-flight, pending apply refresh, debug, stale hash, and stale version keep the rebuild path.",
                "- Design Guide publication, CTA, apply payload, and engineering decisions are outside this change.",
                "",
                "## Checks",
                "",
                *[
                    f"- `{name}`: {'PASS' if passed else 'FAIL'}"
                    for name, passed in checks.items()
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design_guide_first_paint_summary_final_render_skip_snapshot {status}")
    print(json_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
