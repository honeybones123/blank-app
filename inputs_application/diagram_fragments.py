"""Typed fragment registry for Inputs diagram surfaces."""

from __future__ import annotations

from typing import Any, Callable, Literal

from inputs_page_modules.fragments import run_inputs_fragment


InputsDiagramFragmentName = Literal["diagram_2d", "diagram_3d"]
INPUTS_DIAGRAM_FRAGMENT_NAMES = frozenset({"diagram_2d", "diagram_3d"})


def run_inputs_diagram_fragment(
    *,
    st_module: Any,
    fragment_name: InputsDiagramFragmentName,
    render_fn: Callable[..., Any],
    kwargs: dict[str, Any] | None = None,
) -> Any:
    """Render one diagram at its existing layout position under typed ownership."""

    name = str(fragment_name)
    if name not in INPUTS_DIAGRAM_FRAGMENT_NAMES:
        raise ValueError(f"unsupported Inputs diagram fragment: {name}")
    return run_inputs_fragment(
        st_module=st_module,
        fragment_name=name,
        render_fn=render_fn,
        kwargs=kwargs,
    )


__all__ = [
    "INPUTS_DIAGRAM_FRAGMENT_NAMES",
    "InputsDiagramFragmentName",
    "run_inputs_diagram_fragment",
]
