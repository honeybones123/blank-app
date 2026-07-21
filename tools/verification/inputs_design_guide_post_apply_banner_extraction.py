from __future__ import annotations

import ast
import html
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
RENDER_COORDINATORS = ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py"
DESIGN_GUIDE_INIT = ROOT / "inputs_page_modules" / "design_guide" / "__init__.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _render(session_state: dict[str, Any], focus: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from inputs_page_modules.design_guide import render_design_guide_post_apply_banner

    events: list[dict[str, Any]] = []
    render_design_guide_post_apply_banner(
        st_module=FakeStreamlit(session_state, events),
        html_escape_fn=html.escape,
        fast_focus_section=focus,
        apply_banner_key="_banner",
    )
    return events, session_state


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    inputs_source = _source(INPUTS_PAGE)
    render_source = _source(RENDER_COORDINATORS)
    init_source = _source(DESIGN_GUIDE_INIT)
    wrapper_source, wrapper_size = _function_source(inputs_source, "_render_design_guide_post_apply_banner")
    extracted_source, extracted_size = _function_source(render_source, "render_design_guide_post_apply_banner")

    non_model_events, non_model_session = _render({"_banner": {"recommendation_title": "Keep"}}, "loads")
    missing_events, missing_session = _render({}, "model")
    rendered_events, rendered_session = _render(
        {
            "_banner": {
                "recommendation_title": "<Title>",
                "display_truth": {"family": "bending"},
                "change_lines": ["  Width < 400  ", "", "Depth > 600"],
            }
        },
        "model",
    )
    fallback_events, fallback_session = _render(
        {"_banner": {"recommendation_title": "Fallback", "display_truth": {"ok": True}, "change_lines": []}},
        "model",
    )

    rendered_body = rendered_events[0]["body"] if rendered_events else ""
    fallback_body = fallback_events[0]["body"] if fallback_events else ""
    checks = {
        "wrapper_exists": bool(wrapper_source),
        "wrapper_is_small": 0 < wrapper_size <= 8,
        "wrapper_delegates_to_extracted": "return render_design_guide_post_apply_banner(" in wrapper_source,
        "extracted_exists": bool(extracted_source),
        "extracted_is_render_only_size": 0 < extracted_size <= 45,
        "extracted_has_no_streamlit_import": "import streamlit" not in render_source.lower()
        and "from streamlit" not in render_source.lower(),
        "design_guide_init_exports_extracted": "render_design_guide_post_apply_banner" in init_source,
        "non_model_is_noop": not non_model_events and "_banner" in non_model_session,
        "missing_payload_is_noop": not missing_events,
        "payload_is_popped_after_render": "_banner" not in rendered_session,
        "display_truth_written": rendered_session.get("design_guide_post_apply_display_truth") == {"family": "bending"},
        "change_lines_rendered_and_escaped": "Width &lt; 400" in rendered_body
        and "Depth &gt; 600" in rendered_body
        and "&lt;Title&gt;" in rendered_body,
        "fallback_rendered_when_no_lines": "Model updated below. Review the live section before continuing." in fallback_body
        and fallback_session.get("design_guide_post_apply_display_truth") == {"ok": True},
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_design_guide_post_apply_banner_extraction",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "wrapper_size": wrapper_size,
        "extracted_size": extracted_size,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_design_guide_post_apply_banner_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_design_guide_post_apply_banner_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Design Guide Post Apply Banner Extraction",
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
