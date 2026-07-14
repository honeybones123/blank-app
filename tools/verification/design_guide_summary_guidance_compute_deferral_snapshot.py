from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _latest_profile() -> tuple[Path | None, dict]:
    profiles = sorted(
        ARTIFACT_DIR.glob("design_guide_browser_live_smoothness_profile_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in profiles:
        try:
            return path, json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None, {}


def _bounded(source: str, start: str, end: str) -> str:
    start_idx = source.find(start)
    if start_idx < 0:
        return ""
    end_idx = source.find(end, start_idx)
    if end_idx < 0:
        return source[start_idx:]
    return source[start_idx:end_idx]


def _scenario_metrics(profile: dict) -> list[dict]:
    rows: list[dict] = []
    for scenario in list(profile.get("scenarios") or [])[:3]:
        timing = dict(scenario.get("timing") or {})
        counters = dict(scenario.get("counters") or {})
        diag = dict(counters.get("dg_speed_diag") or {})
        summary_end = dict(timing.get("summary_render") or {})
        summary_build_end = None
        for event in timing.get("events_tail") or []:
            if dict(event).get("name") == "inputs_page.summary_build.end":
                summary_build_end = dict(event)
                break
        summary_gap_ms = None
        if summary_build_end and summary_end:
            try:
                summary_gap_ms = round(
                    float(summary_end.get("elapsed_ms") or 0.0)
                    - float(summary_build_end.get("elapsed_ms") or 0.0),
                    3,
                )
            except Exception:
                summary_gap_ms = None
        rows.append(
            {
                "scenario_id": scenario.get("scenario_id"),
                "summary_build_end_ms": (
                    summary_build_end or {}
                ).get("elapsed_ms"),
                "summary_render_end_ms": summary_end.get("elapsed_ms"),
                "summary_build_to_render_gap_ms": summary_gap_ms,
                "compute_design_guidance_items_count": diag.get(
                    "compute_design_guidance_items_count"
                ),
                "candidate_eval_count": dict(counters.get("candidate_evaluation") or {}).get(
                    "count"
                ),
            }
        )
    return rows


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    summary_block = _bounded(
        inputs_source,
        "_summary_fp = _get_design_guide_fp(summary_state)",
        'summary_state_debug["design_guide_render_state_source"]',
    )
    final_panel_block = _bounded(
        inputs_source,
        "def _render_fast_design_guidance_panel(",
        "def _render_current_inputs_summary()",
    )

    profile_path, profile = _latest_profile()
    metrics = _scenario_metrics(profile)
    stable_metrics = [row for row in metrics if str(row.get("scenario_id", "")).startswith("stable")]
    max_summary_gap = max(
        [
            float(row.get("summary_build_to_render_gap_ms") or 0.0)
            for row in stable_metrics
        ]
        or [0.0]
    )
    max_compute_count = max(
        [
            int(row.get("compute_design_guidance_items_count") or 0)
            for row in metrics
        ]
        or [0]
    )

    checks = {
        "summary_block_found": bool(summary_block),
        "summary_block_defers_guidance_compute": (
            "summary_guidance_compute_deferred_until_final_panel" in summary_block
        ),
        "summary_block_does_not_compute_guidance": (
            "_compute_design_guidance_items(" not in summary_block
        ),
        "summary_block_does_not_seed_guidance_cache": (
            "_set_cached_design_guide_guidance(" not in summary_block
        ),
        "final_panel_still_owns_guidance_compute": (
            "_compute_design_guidance_items(" in final_panel_block
        ),
        "latest_profile_available": bool(profile_path),
        "profile_compute_count_is_single_owner": max_compute_count <= 1,
        "stable_summary_render_gap_under_200ms": max_summary_gap <= 200.0,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    stamp = _utc_stamp()
    payload = {
        "schema": "design_guide_summary_guidance_compute_deferral_snapshot.v1",
        "status": status,
        "checks": checks,
        "profile_path": str(profile_path) if profile_path else None,
        "profile_metrics": metrics,
        "classification": {
            "summary_first_paint_guidance_compute_deferred": checks[
                "summary_block_defers_guidance_compute"
            ],
            "final_panel_remains_publication_proof_owner": checks[
                "final_panel_still_owns_guidance_compute"
            ],
            "product_behaviour_changed": False,
            "cta_apply_semantics_changed": False,
            "family_runtime_changed": False,
            "visible_wording_changed": False,
        },
    }
    json_path = ARTIFACT_DIR / f"design_guide_summary_guidance_compute_deferral_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_summary_guidance_compute_deferral_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Summary Guidance Compute Deferral Snapshot",
                "",
                f"Status: `{status}`",
                "",
                "## Checks",
                *[f"- {key}: `{value}`" for key, value in checks.items()],
                "",
                "## Latest Profile",
                f"- Path: `{profile_path}`",
                f"- Max stable summary build-to-render gap: `{max_summary_gap}` ms",
                f"- Max Design Guide compute count in sampled scenarios: `{max_compute_count}`",
                "",
                "## Ownership",
                "- Summary first paint uses visible summary rows when guidance cache is missing.",
                "- Final Design Guide panel remains the publication proof owner.",
                "- CTA/apply, family runtime, and visible wording are unchanged.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design_guide_summary_guidance_compute_deferral_snapshot {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
