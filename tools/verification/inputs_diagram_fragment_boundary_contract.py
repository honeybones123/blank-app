"""Focused structural/runtime contract for typed Inputs diagram fragments."""

from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.diagram_fragments import (
    INPUTS_DIAGRAM_FRAGMENT_NAMES,
    run_inputs_diagram_fragment,
)


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict = {}


def main() -> int:
    owner_source = (
        ROOT / "inputs_application" / "diagram_fragments.py"
    ).read_text(encoding="utf-8")
    widget_source = (
        ROOT
        / "inputs_application"
        / "page_runtime"
        / "widgets.py"
    ).read_text(encoding="utf-8")
    ast.parse(owner_source)
    ast.parse(widget_source)
    assert INPUTS_DIAGRAM_FRAGMENT_NAMES == {
        "diagram_2d",
        "diagram_3d",
    }
    assert "run_inputs_fragment(" not in widget_source
    assert widget_source.count("run_inputs_diagram_fragment(") == 2
    assert 'fragment_name="diagram_2d"' in widget_source
    assert 'fragment_name="diagram_3d"' in widget_source
    assert "def _authoritative_state_snapshot" in widget_source

    fake = _FakeStreamlit()
    events: list[str] = []
    run_inputs_diagram_fragment(
        st_module=fake,
        fragment_name="diagram_2d",
        render_fn=lambda **kwargs: events.append(kwargs["name"]),
        kwargs={"name": "2d"},
    )
    assert events == ["2d"]
    try:
        run_inputs_diagram_fragment(
            st_module=fake,
            fragment_name="diagram_unknown",  # type: ignore[arg-type]
            render_fn=lambda: None,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("unknown diagram fragment was not rejected")
    print("inputs diagram fragment boundary contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
