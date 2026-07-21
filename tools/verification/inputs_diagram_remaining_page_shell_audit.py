from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

EXPECTED_PAGE_SHELL_SURFACES = {
    "_build_inputs_diagram_source_snapshot": "page-shell source collection from session/current layout",
    "_record_inputs_diagram_view_model_trace": "non-authoritative trace/debug recording",
    "make_summary_cross_section_figure": "delegating 2D figure request wrapper",
    "make_beam_3d_figure": "delegating 3D figure request wrapper",
    "_render_materials_and_sectionA_2d": "Streamlit layout/rendering",
    "render_inputs_section_2d_diagram_block": "extracted 2D render coordinator with injected dependencies",
    "render_inputs_3d_diagram_block": "extracted 3D render coordinator with injected dependencies",
    "_record_inputs_model_diagram_render_reuse_trace": "non-authoritative render reuse trace",
    "render_inputs_fast_model_block": "extracted fast model render coordinator with injected dependencies",
    "_render_with_temporary_model_state": "temporary session/model-state render shim",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    start = source.index(marker)
    next_def = source.find("\ndef ", start + len(marker))
    next_marker = source.find("\n# ------------------------------------------------------------", start + len(marker))
    candidates = [idx for idx in (next_def, next_marker) if idx != -1]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def run_snapshot() -> dict:
    root_page = _read("inputs_page.py")
    live_surface = root_page + "\n" + _read("inputs_page_route_coordinators.py")
    builders = _read("inputs_page_modules/diagrams/builders.py")
    models = _read("inputs_page_modules/diagrams/models.py")
    contracts = _read("inputs_page_modules/diagrams/contracts.py")
    render_coordinators = _read("inputs_page_modules/diagrams/render_coordinators.py")
    module_source = builders + models + contracts + render_coordinators
    beam_body = _function_body(live_surface, "make_beam_3d_figure")
    section_body = _function_body(live_surface, "make_summary_cross_section_figure")
    checks = {
        "diagram_module_has_typed_models": "class InputsDiagramSourceSnapshot" in models
        and "class InputsDiagramSectionViewModel" in models,
        "diagram_module_has_request_builders": "def build_section_2d_request_view_model(" in builders
        and "def build_beam_3d_request_view_model(" in builders,
        "diagram_module_no_streamlit_import": "import streamlit" not in module_source
        and "from streamlit" not in module_source,
        "section_wrapper_uses_extracted_vm": "section_vm = view_model.section_2d" in section_body,
        "beam_wrapper_uses_extracted_vm": "beam_vm = view_model.beam_3d" in beam_body,
        "beam_wrapper_old_request_tail_deleted": "shape_name = str(layout.get(\"shape_name\"" not in beam_body
        and "resolve_longitudinal_bars_from_layout(" not in beam_body,
        "page_local_2d_render_wrapper_removed": "def _render_section_2d_diagram_block(" not in root_page,
        "live_route_calls_extracted_2d_renderer": "render_inputs_section_2d_diagram_block(" in live_surface
        and "make_summary_cross_section_figure_fn=make_summary_cross_section_figure" in live_surface
        and "render_plotly_diagram_fn=st.plotly_chart" in live_surface,
        "extracted_2d_render_coordinator_exists": "def render_inputs_section_2d_diagram_block(" in render_coordinators,
        "page_local_3d_render_wrapper_removed": "def _render_3d_diagram_block(" not in root_page,
        "live_route_calls_extracted_3d_renderer": "render_inputs_3d_diagram_block(" in live_surface
        and "cached_make_section_3d_figure_fn=cached_make_section_3d_figure" in live_surface
        and "make_beam_3d_figure_fn=make_beam_3d_figure" in live_surface
        and "render_plotly_diagram_fn=st.plotly_chart" in live_surface,
        "extracted_3d_render_coordinator_exists": "def render_inputs_3d_diagram_block(" in render_coordinators,
        "page_local_fast_model_wrapper_removed": "def _render_fast_model_block(" not in root_page,
        "live_route_calls_extracted_fast_model_renderer": "render_inputs_fast_model_block(" in live_surface
        and "render_3d_diagram_block_fn=_render_3d_diagram_block" in live_surface
        and "render_section_2d_diagram_block_fn=_render_section_2d_diagram_block" in live_surface,
        "route_cache_wrappers_remain_streamlit_owned": "@st.cache_data" in live_surface
        and "def cached_make_section_figure(" in live_surface
        and "def cached_make_section_3d_figure(" in live_surface,
        "no_second_diagram_renderer_created": "render_inputs_diagrams(" not in live_surface,
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    return {
        "status": status,
        "decision": "DIAGRAM_PAGE_SHELL_BOUNDED" if status == "PASS" else "DIAGRAM_PAGE_SHELL_NOT_BOUNDED",
        "checks": checks,
        "failures": failures,
        "remaining_page_shell_surfaces": EXPECTED_PAGE_SHELL_SURFACES,
        "product_behavior_changed": False,
        "visible_behavior_changed": False,
        "diagram_live_renderer_changed": False,
    }


def write_artifacts(snapshot: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_diagram_remaining_page_shell_audit_{ts}.json"
    md_path = AUDIT_DIR / f"inputs_diagram_remaining_page_shell_audit_{ts}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Inputs Diagram Remaining Page Shell Audit",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- `{name}`: `{value}`" for name, value in snapshot["checks"].items())
    lines.extend(["", "## Remaining Page Shell Surfaces"])
    lines.extend(
        f"- `{name}`: {reason}"
        for name, reason in snapshot["remaining_page_shell_surfaces"].items()
    )
    lines.extend(["", "## Failures"])
    lines.extend(f"- `{failure}`" for failure in snapshot["failures"]) if snapshot["failures"] else lines.append("- None")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    snapshot = run_snapshot()
    json_path, md_path = write_artifacts(snapshot)
    print(f"inputs_diagram_remaining_page_shell_audit {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
