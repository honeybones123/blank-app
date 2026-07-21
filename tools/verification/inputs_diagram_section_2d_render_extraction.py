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


class FakeContext:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events

    def __enter__(self):
        self.events.append({"event": "expander_enter"})
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.events.append({"event": "expander_exit"})
        return False


class FakeFigure:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events

    def update_layout(self, **kwargs) -> None:
        self.events.append({"event": "update_layout", "kwargs": dict(kwargs)})


class FakeStreamlit:
    def __init__(self, session_state: dict[str, Any], events: list[dict[str, Any]]) -> None:
        self.session_state = session_state
        self.events = events

    def info(self, body: str) -> None:
        self.events.append({"event": "info", "body": body})

    def warning(self, body: str) -> None:
        self.events.append({"event": "warning", "body": body})

    def expander(self, label: str):
        self.events.append({"event": "expander", "label": label})
        return FakeContext(self.events)

    def exception(self, exc: Exception) -> None:
        self.events.append({"event": "exception", "type": type(exc).__name__})

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


def _exercise_missing() -> list[dict[str, Any]]:
    from inputs_page_modules.diagrams import render_inputs_section_2d_diagram_block

    events: list[dict[str, Any]] = []
    render_inputs_section_2d_diagram_block(
        st_module=FakeStreamlit({"sec_shape": "RECT", "b": 400, "D": 0}, events),
        compact=False,
        model_state=None,
        time_perf_counter_fn=lambda: 1.0,
        inputs_geometry_fingerprint_fn=lambda model_state: "fp",
        make_summary_cross_section_figure_fn=lambda: FakeFigure(events),
        copy_deepcopy_fn=lambda value: value,
        render_plotly_diagram_fn=lambda *args, **kwargs: events.append({"event": "plotly"}),
    )
    return events


def _exercise_render(compact: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from inputs_page_modules.diagrams import render_inputs_section_2d_diagram_block

    events: list[dict[str, Any]] = []
    session_state = {"sec_shape": "RECT", "b": 400, "D": 600}

    def make_figure():
        events.append({"event": "make_figure"})
        return FakeFigure(events)

    def render_plotly_diagram(*args, **kwargs):
        events.append({"event": "plotly", "kwargs": dict(kwargs)})

    render_inputs_section_2d_diagram_block(
        st_module=FakeStreamlit(session_state, events),
        compact=compact,
        model_state={"b": 400},
        time_perf_counter_fn=lambda: 1.0,
        inputs_geometry_fingerprint_fn=lambda model_state: ("fp", tuple(sorted((model_state or {}).items()))),
        make_summary_cross_section_figure_fn=make_figure,
        copy_deepcopy_fn=lambda value: value,
        render_plotly_diagram_fn=render_plotly_diagram,
    )
    return events, session_state


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    inputs_source = _source(INPUTS_PAGE)
    render_source = _source(RENDER_COORDINATORS)
    init_source = _source(DIAGRAM_INIT)
    wrapper_source, wrapper_size = _function_source(inputs_source, "_render_section_2d_diagram_block")
    extracted_source, extracted_size = _function_source(render_source, "render_inputs_section_2d_diagram_block")
    missing_events = _exercise_missing()
    render_events, render_session = _exercise_render(compact=True)

    checks = {
        "page_local_wrapper_removed": not bool(wrapper_source),
        "page_calls_extracted_directly": "render_inputs_section_2d_diagram_block(" in inputs_source,
        "page_injects_plotly_renderer": "render_plotly_diagram_fn=render_plotly_diagram" in inputs_source,
        "extracted_exists": bool(extracted_source),
        "extracted_is_render_only_size": 0 < extracted_size <= 85,
        "extracted_has_no_streamlit_import": "import streamlit" not in render_source.lower()
        and "from streamlit" not in render_source.lower(),
        "diagram_init_exports_extracted": "render_inputs_section_2d_diagram_block" in init_source,
        "missing_branch_preserved": any(event["event"] == "info" for event in missing_events)
        and not any(event["event"] == "plotly" for event in missing_events),
        "render_branch_builds_figure": any(event["event"] == "make_figure" for event in render_events),
        "render_branch_updates_compact_height": any(
            event["event"] == "update_layout" and event["kwargs"].get("height") == 475
            for event in render_events
        ),
        "render_branch_writes_cache": "_inputs_model_2d_fig" in render_session
        and "_inputs_model_2d_geo_fp" in render_session,
        "render_branch_calls_plotly_without_modebar": any(
            event["event"] == "plotly"
            and event["kwargs"].get("config") == {"displayModeBar": False}
            for event in render_events
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_diagram_section_2d_render_extraction",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "wrapper_size": wrapper_size,
        "extracted_size": extracted_size,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_diagram_section_2d_render_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_diagram_section_2d_render_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Diagram Section 2D Render Extraction",
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
