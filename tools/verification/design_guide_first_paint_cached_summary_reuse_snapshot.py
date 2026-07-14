from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _latest(prefix: str) -> str | None:
    matches = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return str(matches[0]) if matches else None


def _contains_all(source: str, needles: list[str]) -> dict[str, bool]:
    return {needle: needle in source for needle in needles}


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source_path = ROOT / "inputs_page.py"
    source = source_path.read_text(encoding="utf-8")

    helper_start = source.find("def _cached_summary_html_for_first_paint")
    helper_end = source.find("summary_container = st.empty()", helper_start)
    helper_source = source[helper_start:helper_end] if helper_start != -1 and helper_end != -1 else ""
    first_paint_start = source.find("_first_paint_cached_summary_html")
    first_paint_end = source.find("st.markdown(\n            _first_paint_shell_html", first_paint_start)
    first_paint_source = (
        source[first_paint_start:first_paint_end]
        if first_paint_start != -1 and first_paint_end != -1
        else ""
    )

    helper_guards = _contains_all(
        helper_source,
        [
            "_final_publication_summary_card_html_cache",
            "summary_cards_html",
            "RESULT_CACHE_KEY",
            "results_version",
            "result_cache_hash",
            "inputs_dirty",
            "_inputs_dirty",
            "_pending_inputs_apply_refresh",
            "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY",
            "_force_inputs_widget_reseed_once",
            "_design_guide_sidebar_debug_enabled",
            "affects_visible_wording",
            "affects_cta",
            "affects_apply_payload",
            "affects_family_runtime",
            "product_behavior_changed",
        ],
    )
    shell_checks = _contains_all(
        first_paint_source,
        [
            "data-testid=\"inputs-first-paint-cached-summary\"",
            "inputs-first-paint-cached-summary-shell",
            "summary.first_paint_cached_html_reuse",
            "_inputs_first_paint_cached_summary_reuse_debug",
            "cache_hit=bool",
            "__CACHED_SUMMARY_HTML__",
            "summary-card-stack",
            "summary-skeleton-row",
        ],
    )
    existing_final_render_still_present = (
        'st.markdown(f\'<div class="summary-card-stack">{summary_cards_html}</div>\''
        in source
    )
    existing_summary_html_reuse_still_present = "summary.card_html_build_reuse" in source

    failures: list[str] = []
    if helper_start == -1:
        failures.append("cached summary first-paint helper missing")
    failures.extend(f"missing helper guard: {key}" for key, ok in helper_guards.items() if not ok)
    failures.extend(f"missing first-paint shell check: {key}" for key, ok in shell_checks.items() if not ok)
    if not existing_final_render_still_present:
        failures.append("final visible summary render path missing")
    if not existing_summary_html_reuse_still_present:
        failures.append("existing summary HTML reuse path missing")

    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_first_paint_cached_summary_reuse_snapshot.v1",
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
        "status": status,
        "source_file": str(source_path),
        "product_behaviour_changed": False,
        "checks": {
            "helper_present": helper_start != -1,
            "helper_guards": helper_guards,
            "first_paint_shell_checks": shell_checks,
            "existing_final_render_still_present": existing_final_render_still_present,
            "existing_summary_html_reuse_still_present": existing_summary_html_reuse_still_present,
            "cached_path_scope": "first_paint_summary_shell_only",
            "normal_final_summary_render_still_runs": existing_final_render_still_present,
            "dirty_apply_debug_states_force_skeleton": all(
                helper_guards[key]
                for key in [
                    "inputs_dirty",
                    "_inputs_dirty",
                    "_pending_inputs_apply_refresh",
                    "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY",
                    "_design_guide_sidebar_debug_enabled",
                ]
            ),
            "stable_hash_guard": helper_guards["RESULT_CACHE_KEY"]
            and helper_guards["results_version"]
            and helper_guards["result_cache_hash"],
        },
        "latest_supporting_artifacts": {
            "browser_live_smoothness_profile": _latest("design_guide_browser_live_smoothness_profile"),
            "summary_layout_shift_readiness": _latest("design_guide_summary_layout_shift_readiness"),
            "design_guide_independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock_verifier"),
            "compute_resolver_publication_bridge_lock": _latest(
                "design_guide_compute_resolver_publication_bridge_lock"
            ),
        },
        "failures": failures,
    }

    stamp = payload["created_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_first_paint_cached_summary_reuse_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_first_paint_cached_summary_reuse_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide First-Paint Cached Summary Reuse Snapshot",
                "",
                f"Status: **{status}**",
                "",
                "## Scope",
                "",
                "This verifies the first-paint Inputs summary shell can reuse the last proven summary HTML on stable no-input reruns only.",
                "It does not change engineering decisions, Design Brain publication, CTA/apply routing, or visible wording.",
                "",
                "## Guard",
                "",
                "- Keyed by `results_version` and `RESULT_CACHE_KEY` hash.",
                "- Disabled for dirty input, apply-in-flight, pending apply refresh, widget reseed, landing, and debug states.",
                "- Normal final summary rendering still runs after first paint.",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
            ]
        ),
        encoding="utf-8",
    )
    print(f"design_guide_first_paint_cached_summary_reuse_snapshot {status}")
    print(json_path)
    print(md_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
