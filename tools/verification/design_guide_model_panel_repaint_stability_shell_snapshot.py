"""Verify the model-panel repaint stability shell.

This is a narrow visual-stability guard for the Inputs model diagram area. The
post-Apply root-cause lock proves changed-fingerprint model redraws are real and
must not be skipped. This verifier proves the app reserves/contains the model
diagram paint area while preserving the live Plotly render path.

It does not validate engineering results and must not move Design Brain,
publication, CTA/apply routing, family runtimes, visible wording, or widget
ownership.
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


def _function_block(source: str, name: str) -> str:
    match = re.search(rf"^def {re.escape(name)}\(", source, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", source[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _css_block(source: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\n\s*\}}", source, re.DOTALL)
    return match.group("body") if match else ""


def _capture() -> dict[str, Any]:
    style_source = (ROOT / "ui" / "inputs_page_style.py").read_text(encoding="utf-8", errors="replace")
    diagram_source = (ROOT / "inputs_page_modules" / "diagrams" / "render_coordinators.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    wrapper_css = _css_block(style_source, ".inputs-page-main-diagram-wrap")
    chart_css = _css_block(style_source, '.inputs-page-main-diagram-wrap div[data-testid="stPlotlyChart"]')
    section_2d = _function_block(diagram_source, "render_inputs_section_2d_diagram_block")
    section_3d = _function_block(diagram_source, "render_inputs_3d_diagram_block")
    root_lock = _latest("app_stability_post_apply_smoothness_root_cause_lock")
    post_apply = _latest("design_guide_post_apply_settle_source_profile")
    reuse_impl = _latest("design_guide_model_diagram_render_reuse_implementation")
    return {
        "source_checks": {
            "wrapper_css_exists": bool(wrapper_css),
            "wrapper_min_height_present": "min-height: min(52vh, 560px)" in wrapper_css,
            "wrapper_containment_present": "contain: layout paint" in wrapper_css,
            "wrapper_content_visibility_present": "content-visibility: auto" in wrapper_css,
            "wrapper_intrinsic_size_present": "contain-intrinsic-size: 560px" in wrapper_css,
            "chart_min_height_present": "min-height: min(52vh, 560px)" in chart_css,
            "chart_max_height_preserved": "max-height: min(52vh, 560px)" in chart_css,
            "two_d_live_plotly_render_preserved": "render_plotly_diagram_fn(" in section_2d,
            "three_d_live_plotly_render_preserved": "render_plotly_diagram_fn(" in section_3d,
            "two_d_wrapper_still_scopes_chart": 'class="inputs-page-main-diagram-wrap"' in section_2d,
            "three_d_wrapper_still_scopes_chart": section_3d.count('class="inputs-page-main-diagram-wrap"') >= 2,
            "no_design_brain_or_apply_logic_in_style": all(
                token not in style_source
                for token in (
                    "FinalDesignGuidePublication",
                    "apply_payload",
                    "run_bending",
                    "family",
                    "candidate",
                    "publication_hash",
                    "session_state",
                )
            ),
        },
        "upstream_evidence": {
            "post_apply_root_cause_lock": {
                "path": root_lock.get("path"),
                "status": root_lock.get("status"),
                "decision": ((root_lock.get("payload") or {}).get("classification") or {}).get("decision"),
            },
            "post_apply_source_profile": {
                "path": post_apply.get("path"),
                "status": post_apply.get("status"),
                "decision": ((post_apply.get("payload") or {}).get("summary") or {}).get("decision"),
                "top_owner": ((post_apply.get("payload") or {}).get("summary") or {}).get(
                    "focused_post_click_top_owner"
                ),
            },
            "model_diagram_reuse_implementation": {
                "path": reuse_impl.get("path"),
                "status": reuse_impl.get("status"),
                "classification": (reuse_impl.get("payload") or {}).get("classification"),
            },
        },
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    checks = dict(capture.get("source_checks") or {})
    evidence = dict(capture.get("upstream_evidence") or {})
    root = dict(evidence.get("post_apply_root_cause_lock") or {})
    post = dict(evidence.get("post_apply_source_profile") or {})
    reuse = dict(evidence.get("model_diagram_reuse_implementation") or {})
    required = [
        "wrapper_css_exists",
        "wrapper_min_height_present",
        "wrapper_containment_present",
        "wrapper_content_visibility_present",
        "wrapper_intrinsic_size_present",
        "chart_min_height_present",
        "chart_max_height_preserved",
        "two_d_live_plotly_render_preserved",
        "three_d_live_plotly_render_preserved",
        "two_d_wrapper_still_scopes_chart",
        "three_d_wrapper_still_scopes_chart",
        "no_design_brain_or_apply_logic_in_style",
    ]
    missing = [key for key in required if not checks.get(key)]
    if root.get("decision") != "POST_APPLY_MODEL_REPAINT_ROOT_CAUSE_LOCKED":
        missing.append("post_apply_root_cause_not_locked")
    if post.get("decision") != "POST_APPLY_MODEL_OR_CHART_MUTATION_HOTSPOT":
        missing.append("post_apply_profile_not_model_or_chart_hotspot")
    if post.get("top_owner") != "plotly_or_chart":
        missing.append("post_apply_top_owner_not_plotly_or_chart")
    if reuse.get("status") != "PASS":
        missing.append("model_diagram_reuse_implementation_not_passed")
    status = "PASS" if not missing else "FAIL"
    return {
        "status": status,
        "missing_checks": missing,
        "implemented_scope": "model_panel_visual_repaint_stability_shell",
        "product_behaviour_changed": False,
        "render_skipped": False,
        "engineering_logic_changed": False,
        "publication_or_cta_changed": False,
        "ready_for_live_impact_profile": not missing,
        "recommended_next_slice": (
            "Run post-Apply source profile and broad smoothness profile to measure whether the shell reduces visible "
            "layout/jump while preserving changed-fingerprint model redraw."
            if not missing
            else "Fix missing stability-shell checks before impact profiling."
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["timestamp"])
    json_path = ARTIFACT_DIR / f"design_guide_model_panel_repaint_stability_shell_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_model_panel_repaint_stability_shell_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Model Panel Repaint Stability Shell",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Implemented scope: `{cls.get('implemented_scope')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Render skipped: `{cls.get('render_skipped')}`",
        f"- Engineering logic changed: `{cls.get('engineering_logic_changed')}`",
        f"- Publication/CTA changed: `{cls.get('publication_or_cta_changed')}`",
        "",
        "## Source Checks",
        "",
        "```json",
        json.dumps(payload.get("source_checks") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Upstream Evidence",
        "",
        "```json",
        json.dumps(payload.get("upstream_evidence") or {}, indent=2, sort_keys=True, default=str)[:12000],
        "```",
        "",
        "## Recommended Next Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    capture = _capture()
    classification = _classify(capture)
    payload = {
        "schema": "design_guide_model_panel_repaint_stability_shell.v1",
        "timestamp": _stamp(),
        "status": classification["status"],
        "product_behaviour_changed": False,
        **capture,
        "classification": classification,
    }
    json_path, md_path = _write(payload)
    print(f"design_guide_model_panel_repaint_stability_shell {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
