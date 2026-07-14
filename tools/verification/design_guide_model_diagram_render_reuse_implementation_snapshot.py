"""Verify the model/diagram figure reuse implementation.

This is a narrow smoothness guard. It proves stable model geometry reuses the
cached Plotly figure object instead of deep-copying/rebuilding it, while the live
Plotly render call remains present so browser-visible diagrams are not blanked
on normal Streamlit reruns.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_block(source: str, name: str) -> str:
    match = re.search(rf"^def {re.escape(name)}\(", source, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", source[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


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


def _capture() -> dict[str, Any]:
    inputs = _read(ROOT / "inputs_page.py")
    section_2d = _function_block(inputs, "_render_section_2d_diagram_block")
    section_3d = _function_block(inputs, "_render_3d_diagram_block")
    trace_helper = _function_block(inputs, "_record_inputs_model_diagram_render_reuse_trace")
    return {
        "source_checks": {
            "two_d_uses_cached_figure_without_deepcopy": (
                "fig_sec = cached_fig" in section_2d
                and "fig_sec = copy.deepcopy(cached_fig)" not in section_2d
            ),
            "two_d_stores_canonical_cached_figure": (
                'st.session_state["_inputs_model_2d_fig"] = fig_sec' in section_2d
                and 'st.session_state["_inputs_model_2d_fig"] = copy.deepcopy(fig_sec)' not in section_2d
            ),
            "three_d_uses_cached_figure_without_deepcopy": (
                "fig3d = cached_fig" in section_3d
                and "fig3d = copy.deepcopy(cached_fig)" not in section_3d
            ),
            "three_d_stores_canonical_cached_figure": (
                '"fig": fig3d' in section_3d and '"fig": copy.deepcopy(fig3d)' not in section_3d
            ),
            "trace_records_cache_hits": all(
                token in trace_helper
                for token in (
                    "figure_cache_hit",
                    "figure_copy_skipped",
                    "implementation_guard_active",
                    "diagram_figure_reuse_without_render_skip",
                )
            ),
            "two_d_passes_cache_hit_to_trace": (
                "figure_cache_hit=figure_cache_hit" in section_2d
                and "figure_copy_skipped=figure_cache_hit" in section_2d
            ),
            "three_d_passes_cache_hit_to_trace": (
                section_3d.count("figure_cache_hit=figure_cache_hit") >= 2
                and section_3d.count("figure_copy_skipped=figure_cache_hit") >= 2
            ),
            "two_d_live_render_preserved": "render_plotly_diagram(" in section_2d,
            "three_d_live_render_preserved": "render_plotly_diagram(" in section_3d,
            "no_render_skip_branch_added": "if row.get(\"reuse_eligible\")" not in inputs
            and "if trace.get(\"reuse_eligible\")" not in inputs,
            "cta_apply_publication_not_moved": all(
                forbidden not in section_2d + section_3d + trace_helper
                for forbidden in (
                    "FinalDesignGuidePublication",
                    "build_final_design_guide_publication",
                    "apply_payload",
                    "apply_resolved_candidate",
                    "one_click",
                    "cta_intent",
                    "FinalDesignGuideCTA",
                    "publication_hash",
                )
            ),
        },
        "upstream_locks": {
            "readiness": _latest("design_guide_model_diagram_render_reuse_readiness"),
            "trace": _latest("design_guide_model_diagram_render_reuse_trace"),
        },
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    checks = dict(capture.get("source_checks") or {})
    required = [
        "two_d_uses_cached_figure_without_deepcopy",
        "two_d_stores_canonical_cached_figure",
        "three_d_uses_cached_figure_without_deepcopy",
        "three_d_stores_canonical_cached_figure",
        "trace_records_cache_hits",
        "two_d_passes_cache_hit_to_trace",
        "three_d_passes_cache_hit_to_trace",
        "two_d_live_render_preserved",
        "three_d_live_render_preserved",
        "no_render_skip_branch_added",
        "cta_apply_publication_not_moved",
    ]
    missing = [key for key in required if not checks.get(key)]
    return {
        "status": "PASS" if not missing else "FAIL",
        "missing_checks": missing,
        "implemented_scope": "diagram_figure_reuse_without_render_skip",
        "ready_for_live_impact_snapshot": not missing,
        "product_behaviour_changed": False,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Design Guide Model/Diagram Render Reuse Implementation Snapshot",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Implemented scope: `{cls.get('implemented_scope')}`",
            f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
            f"- Ready for live impact snapshot: `{cls.get('ready_for_live_impact_snapshot')}`",
            "",
            "## Source Checks",
            "",
            "```json",
            json.dumps(payload.get("source_checks") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Notes",
            "",
            "- Stable geometry now reuses cached Plotly figure objects instead of deep-copying them.",
            "- The live Plotly render call is intentionally preserved; this slice does not blank or skip diagrams.",
            "- CTA, apply routing, publication, family runtimes, and visible wording are outside this change.",
            "",
        ]
    )


def main() -> int:
    capture = _capture()
    classification = _classify(capture)
    stamp = _stamp()
    payload = {
        "schema": "design_guide_model_diagram_render_reuse_implementation.v1",
        "timestamp": stamp,
        "status": classification["status"],
        "product_behaviour_changed": False,
        **capture,
        "classification": classification,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_model_diagram_render_reuse_implementation_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_model_diagram_render_reuse_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_model_diagram_render_reuse_implementation {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
