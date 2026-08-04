from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
RENDER_COORDINATORS = ROOT / "inputs_page_modules" / "diagrams" / "render_coordinators.py"
DIAGRAM_INIT = ROOT / "inputs_page_modules" / "diagrams" / "__init__.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class FakeFigure:
    def __init__(self, events: list[dict[str, Any]], label: str) -> None:
        self.events = events
        self.label = label

    def update_layout(self, **kwargs) -> None:
        self.events.append({"event": "update_layout", "label": self.label, "kwargs": dict(kwargs)})


class FakeStreamlit:
    def __init__(self, session_state: dict[str, Any], events: list[dict[str, Any]]) -> None:
        self.session_state = session_state
        self.events = events

    def markdown(self, body: str, **kwargs) -> None:
        self.events.append({"event": "markdown", "body": body, "kwargs": dict(kwargs)})


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> tuple[str, int]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno]), node.end_lineno - node.lineno + 1
    return "", 0


def _exercise_rectangle() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from inputs_page_modules.diagrams import render_inputs_3d_diagram_block

    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {}

    def make_beam():
        events.append({"event": "make_beam"})
        return FakeFigure(events, "rect")

    def render_plotly(*args, **kwargs):
        events.append({"event": "plotly", "kwargs": dict(kwargs)})

    render_inputs_3d_diagram_block(
        st_module=FakeStreamlit(session_state, events),
        compact=True,
        model_state={"lig_d": 12, "lig_legs": 4, "s_lig": 180},
        time_perf_counter_fn=lambda: 1.0,
        inputs_geometry_fingerprint_fn=lambda model_state: ("fp", "rect"),
        copy_deepcopy_fn=lambda value: value,
        compute_section_layout_fn=lambda: {"shape_name": "Rectangle (b x D)", "dims": {}, "reo": {}, "reo_layout": {}},
        shared_state_snapshot_fn=lambda: {},
        cache_json_fn=lambda value: json.dumps(value, sort_keys=True),
        cached_make_section_3d_figure_fn=lambda **kwargs: FakeFigure(events, "ti"),
        make_beam_3d_figure_fn=make_beam,
        render_plotly_diagram_fn=render_plotly,
    )
    return events, session_state


def _exercise_t_section() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from inputs_page_modules.diagrams import render_inputs_3d_diagram_block

    events: list[dict[str, Any]] = []
    session_state: dict[str, Any] = {}

    def cached_section(**kwargs):
        events.append({"event": "cached_section", "kwargs": dict(kwargs)})
        return FakeFigure(events, "t")

    def render_plotly(*args, **kwargs):
        events.append({"event": "plotly", "kwargs": dict(kwargs)})

    render_inputs_3d_diagram_block(
        st_module=FakeStreamlit(session_state, events),
        compact=True,
        model_state={"lig_d": 10, "lig_legs": 2, "s_lig": 200},
        time_perf_counter_fn=lambda: 1.0,
        inputs_geometry_fingerprint_fn=lambda model_state: ("fp", "t"),
        copy_deepcopy_fn=lambda value: value,
        compute_section_layout_fn=lambda: {
            "shape_name": "T-Section",
            "dims": {"bf": 600, "tf": 120, "bw": 300, "D": 600},
            "reo": {},
            "reo_layout": [],
        },
        shared_state_snapshot_fn=lambda: {},
        cache_json_fn=lambda value: json.dumps(value, sort_keys=True),
        cached_make_section_3d_figure_fn=cached_section,
        make_beam_3d_figure_fn=lambda: FakeFigure(events, "rect"),
        render_plotly_diagram_fn=render_plotly,
    )
    return events, session_state


def _exercise_cache_hit() -> list[dict[str, Any]]:
    from inputs_page_modules.diagrams import render_inputs_3d_diagram_block

    events: list[dict[str, Any]] = []
    cached_fig = FakeFigure(events, "cached")
    session_state: dict[str, Any] = {
        "_inputs_model_3d_cache": {
            "geo_fp": ("fp", "cached"),
            "shape_name": "Rectangle (b x D)",
            "fig": cached_fig,
        }
    }

    render_inputs_3d_diagram_block(
        st_module=FakeStreamlit(session_state, events),
        compact=False,
        model_state=None,
        time_perf_counter_fn=lambda: 1.0,
        inputs_geometry_fingerprint_fn=lambda model_state: ("fp", "cached"),
        copy_deepcopy_fn=lambda value: value,
        compute_section_layout_fn=lambda: events.append({"event": "unexpected_layout"}) or {},
        shared_state_snapshot_fn=lambda: {},
        cache_json_fn=lambda value: json.dumps(value, sort_keys=True),
        cached_make_section_3d_figure_fn=lambda **kwargs: events.append({"event": "unexpected_section"}),
        make_beam_3d_figure_fn=lambda: events.append({"event": "unexpected_beam"}),
        render_plotly_diagram_fn=lambda *args, **kwargs: events.append({"event": "plotly", "kwargs": dict(kwargs)}),
    )
    return events


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    inputs_source = _source(INPUTS_PAGE)
    render_source = _source(RENDER_COORDINATORS)
    init_source = _source(DIAGRAM_INIT)
    wrapper_source, wrapper_size = _function_source(inputs_source, "_render_3d_diagram_block")
    extracted_source, extracted_size = _function_source(render_source, "render_inputs_3d_diagram_block")
    rect_events, rect_session = _exercise_rectangle()
    t_events, t_session = _exercise_t_section()
    cache_events = _exercise_cache_hit()

    checks = {
        "page_local_wrapper_removed": not bool(wrapper_source),
        "page_calls_extracted_directly": "render_inputs_3d_diagram_block(" in inputs_source,
        "page_injects_plotly_renderer": "render_plotly_diagram_fn=render_plotly_diagram" in inputs_source,
        "extracted_exists": bool(extracted_source),
        "extracted_is_render_only_size": 0 < extracted_size <= 125,
        "extracted_has_no_streamlit_import": "import streamlit" not in render_source.lower()
        and "from streamlit" not in render_source.lower(),
        "diagram_init_exports_extracted": "render_inputs_3d_diagram_block" in init_source,
        "rectangle_branch_uses_beam_figure": any(event["event"] == "make_beam" for event in rect_events),
        "rectangle_branch_plotly_contract": any(
            event["event"] == "plotly"
            and event["kwargs"].get("width") == "stretch"
            and event["kwargs"].get("config") == {"displayModeBar": True}
            for event in rect_events
        ),
        "rectangle_branch_writes_cache": "_inputs_model_3d_cache" in rect_session,
        "t_branch_uses_cached_section_figure": any(event["event"] == "cached_section" for event in t_events),
        "t_branch_normalises_reo_layout": any(
            event["event"] == "cached_section"
            and json.loads(event["kwargs"].get("reo_layout_json", "{}")) == {"top": [], "bottom": []}
            for event in t_events
        ),
        "t_branch_plotly_contract": any(
            event["event"] == "plotly"
            and event["kwargs"].get("use_container_width") is True
            and event["kwargs"].get("config") == {"displayModeBar": False}
            for event in t_events
        ),
        "cache_hit_skips_figure_builders": not any(
            event["event"].startswith("unexpected") for event in cache_events
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_diagram_3d_render_extraction",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "wrapper_size": wrapper_size,
        "extracted_size": extracted_size,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_diagram_3d_render_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_diagram_3d_render_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Diagram 3D Render Extraction",
                "",
                f"Status: `{payload['status']}`",
                f"Wrapper size: `{wrapper_size}`",
                f"Extracted size: `{extracted_size}`",
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
