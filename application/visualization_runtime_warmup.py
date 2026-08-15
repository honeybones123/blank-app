"""One-shot import warm-up for the shared plotting runtime.

Calculation pages share Matplotlib for explanatory and engineering diagrams.
Importing it inside the first visited page made that route pay a process-wide
initialisation cost.  Warm the neutral plotting dependency while the shared
application shell is composed; no page module, figure, calculation, session
state, or publication is created here.
"""

from __future__ import annotations

from threading import Event, Lock, Thread


_started = False
_started_lock = Lock()
_ready = Event()
_failure: BaseException | None = None


def _warm() -> None:
    global _failure
    try:
        import matplotlib.pyplot  # noqa: F401, PLC0415
        import plotly.graph_objects as go  # noqa: PLC0415
        from plotly.subplots import make_subplots  # noqa: PLC0415

        # Initialise Plotly's shared validator/subplot machinery without
        # constructing or caching any application figure.  Plotly imports
        # validators lazily, so exercise the neutral layout/trace features
        # shared by the engineering diagrams while the common shell starts.
        # This deliberately contains no page data, page module, or UI output.
        figure = make_subplots(
            rows=1,
            cols=3,
            shared_yaxes=True,
            horizontal_spacing=0.08,
            subplot_titles=("", "", ""),
        )
        # Exercise the three-panel trace/shape/annotation validators used by
        # the Bending page. This remains dependency-only warm-up: the values
        # are neutral, no application figure is cached, and no page module or
        # engineering state is imported.
        for col in range(1, 4):
            for trace_index in range(6):
                offset = trace_index * 0.01
                figure.add_trace(
                    go.Scatter(
                        x=(0.0 + offset, 1.0 + offset),
                        y=(0.0, 1.0),
                        mode="lines+markers",
                        fill="toself" if trace_index == 0 else None,
                        line={"color": "#000000", "width": 1.0, "dash": "dash"},
                        marker={"size": 4, "line": {"width": 1}},
                        customdata=((0.0,), (1.0,)),
                        hovertemplate="%{x}<extra></extra>",
                        legendgroup="warmup",
                        showlegend=False,
                    ),
                    row=1,
                    col=col,
                )
            figure.add_shape(
                type="line", x0=0.0, x1=1.0, y0=0.0, y1=1.0, row=1, col=col
            )
            figure.add_shape(
                type="circle", x0=0.4, x1=0.6, y0=0.4, y1=0.6, row=1, col=col
            )
            figure.add_annotation(
                x=0.5,
                y=0.5,
                text="",
                showarrow=True,
                arrowhead=2,
                bgcolor="#ffffff",
                bordercolor="#000000",
                row=1,
                col=col,
            )
        figure.update_layout(
            template="simple_white",
            title={"text": "", "x": 0.5, "xanchor": "center"},
            xaxis={
                "visible": False,
                "showgrid": False,
                "showticklabels": False,
                "showline": False,
                "ticks": "",
                "zeroline": False,
                "fixedrange": True,
                "range": (-0.1, 1.1),
            },
            yaxis={
                "visible": False,
                "showgrid": False,
                "showticklabels": False,
                "showline": False,
                "ticks": "",
                "zeroline": False,
                "fixedrange": True,
                "range": (-0.1, 1.1),
                "scaleanchor": "x",
                "scaleratio": 1,
            },
            legend={"orientation": "h", "traceorder": "normal"},
            margin={"l": 1, "r": 1, "t": 1, "b": 1},
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            hovermode="closest",
            showlegend=False,
            width=10,
            height=10,
        )
        figure.to_plotly_json()
    except BaseException as exc:  # pragma: no cover - surfaced by normal use
        _failure = exc
    finally:
        _ready.set()


def start_visualization_runtime_warmup() -> bool:
    """Start the process-owned dependency import once."""

    global _started
    with _started_lock:
        if _started:
            return False
        _started = True
        Thread(target=_warm, name="visualization-runtime-warmup", daemon=True).start()
        return True


def wait_for_visualization_runtime_warmup(timeout: float | None = None) -> bool:
    """Wait for warm-up and surface an import failure, if one occurred."""

    completed = _ready.wait(timeout)
    if completed and _failure is not None:
        raise RuntimeError("Visualization Runtime warm-up failed") from _failure
    return completed


__all__ = ["start_visualization_runtime_warmup", "wait_for_visualization_runtime_warmup"]
