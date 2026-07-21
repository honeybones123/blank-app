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
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
RENDER_COORDINATORS = ROOT / "inputs_page_modules" / "diagrams" / "render_coordinators.py"
DIAGRAM_INIT = ROOT / "inputs_page_modules" / "diagrams" / "__init__.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class FakeContext:
    def __init__(self, label: str, events: list[dict[str, Any]]) -> None:
        self.label = label
        self.events = events

    def __enter__(self):
        self.events.append({"event": "enter", "label": self.label})
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.events.append({"event": "exit", "label": self.label})
        return False


class FakeStreamlit:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events

    def columns(self, spec, gap=None):
        self.events.append({"event": "columns", "spec": list(spec), "gap": gap})
        return FakeContext("title_col", self.events), FakeContext("toggle_col", self.events)

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


def _exercise(show_3d: bool) -> list[dict[str, Any]]:
    from inputs_page_modules.diagrams import render_inputs_fast_model_block

    events: list[dict[str, Any]] = []

    def shared_toggle(*args, **kwargs) -> bool:
        events.append({"event": "shared_toggle", "args": list(args), "kwargs": dict(kwargs)})
        return bool(show_3d)

    def render_with_temporary_model_state(model_state, render_fn):
        events.append({"event": "temporary_state", "model_state": dict(model_state or {})})
        return render_fn()

    def render_3d_diagram_block(**kwargs):
        events.append({"event": "render_3d", "kwargs": dict(kwargs)})

    def render_section_2d_diagram_block(**kwargs):
        events.append({"event": "render_2d", "kwargs": dict(kwargs)})

    render_inputs_fast_model_block(
        st_module=FakeStreamlit(events),
        sync_callbacks={"sync": "callback"},
        model_state={"b": 400, "D": 600},
        shared_toggle_fn=shared_toggle,
        render_with_temporary_model_state_fn=render_with_temporary_model_state,
        render_3d_diagram_block_fn=render_3d_diagram_block,
        render_section_2d_diagram_block_fn=render_section_2d_diagram_block,
    )
    return events


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    inputs_source = _source(INPUTS_PAGE)
    route_source = _source(ROUTE_COORDINATORS)
    render_source = _source(RENDER_COORDINATORS)
    init_source = _source(DIAGRAM_INIT)
    wrapper_source, wrapper_size = _function_source(inputs_source, "_render_fast_model_block")
    extracted_source, extracted_size = _function_source(render_source, "render_inputs_fast_model_block")
    events_2d = _exercise(False)
    events_3d = _exercise(True)

    checks = {
        "page_local_wrapper_removed": not bool(wrapper_source),
        "diagram_boundary_wired_through_shell_or_route": (
            "render_inputs_fast_model_block(" in inputs_source
            or "render_inputs_fast_model_block(" in route_source
        ),
        "diagram_callbacks_injected_outside_live_shell": (
            (
                "render_3d_diagram_block_fn=lambda" in inputs_source
                and "render_section_2d_diagram_block_fn=lambda" in inputs_source
            )
            or (
                "render_3d_diagram_block_fn=" in route_source
                and "render_section_2d_diagram_block_fn=" in route_source
            )
        ),
        "extracted_exists": bool(extracted_source),
        "extracted_is_render_only_size": 0 < extracted_size <= 60,
        "extracted_has_no_streamlit_import": "import streamlit" not in render_source.lower()
        and "from streamlit" not in render_source.lower(),
        "diagram_init_exports_extracted": "render_inputs_fast_model_block" in init_source,
        "two_d_branch_renders_2d_only": any(event["event"] == "render_2d" for event in events_2d)
        and not any(event["event"] == "render_3d" for event in events_2d),
        "three_d_branch_renders_3d_only": any(event["event"] == "render_3d" for event in events_3d)
        and not any(event["event"] == "render_2d" for event in events_3d),
        "toggle_contract_preserved": any(
            event["event"] == "shared_toggle"
            and event["args"][:4]
            == [
                "3D model",
                "inputs_fast_mode_show_3d_toggle",
                "fast_mode_show_3d",
                False,
            ]
            for event in events_2d + events_3d
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_diagram_fast_model_block_extraction",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "wrapper_size": wrapper_size,
        "extracted_size": extracted_size,
        "events_2d": events_2d,
        "events_3d": events_3d,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_diagram_fast_model_block_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_diagram_fast_model_block_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Diagram Fast Model Block Extraction",
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
