"""Runtime contract for RECT/T/I bending diagram composition."""

from __future__ import annotations

import copy
import math
from pathlib import Path
import sys

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui.diagrams.stress_strain_diagram import (  # noqa: E402
    inject_figure_into_subplot,
)


def verify_shared_subplot_composer_preserves_child_figure() -> None:
    parent = make_subplots(rows=1, cols=1)
    child = go.Figure()
    child.add_trace(go.Scatter(x=[0.0, 1.0], y=[1.0, 0.0]))
    child.add_shape(type="rect", x0=0.0, x1=1.0, y0=0.0, y1=1.0)
    child.add_annotation(x=0.5, y=0.5, text="section")
    child_before = copy.deepcopy(child.to_plotly_json())

    inject_figure_into_subplot(
        parent,
        child,
        row=1,
        col=1,
        xref="x1",
        yref="y1",
    )

    assert child.to_plotly_json() == child_before
    assert len(parent.data) == 1
    assert len(parent.layout.shapes) == 1
    assert len(parent.layout.annotations) == 1


def _capacity_signature(app: AppTest) -> tuple[float, float]:
    signature = (
        float(app.session_state["phi_Mu_pos_kNm"]),
        float(app.session_state["phi_Mu_neg_kNm"]),
    )
    assert all(math.isfinite(value) and value > 0.0 for value in signature)
    return signature


def _assert_rendered(app: AppTest) -> None:
    assert not app.exception, [item.message for item in app.exception]
    plotly_count = len(app.get("plotly_chart"))
    fullscreen_anchor_count = sum(
        "data-beam-plotly-fullscreen-anchor" in str(markdown.value)
        for markdown in app.markdown
    )
    assert plotly_count >= 1
    assert fullscreen_anchor_count == plotly_count


def verify_all_section_and_moment_branches() -> None:
    app = AppTest.from_file(str(REPO_ROOT / "app.py"), default_timeout=120)
    app.run(timeout=120)
    app.radio[0].set_value("Bending").run(timeout=120)

    for positive, negative in ((100.0, 0.0), (0.0, 100.0)):
        app.number_input(key="inputs_load_Mstar_pos_proxy").set_value(
            positive
        ).run(timeout=120)
        app.number_input(key="inputs_load_Mstar_neg_proxy").set_value(
            negative
        ).run(timeout=120)

        for shape in ("RECT", "T", "I"):
            app.selectbox(key="bending_sec_shape").set_value(shape).run(
                timeout=120
            )
            _assert_rendered(app)
            linear_signature = _capacity_signature(app)

            app.checkbox(key="bending_parabolic_toggle").set_value(True).run(
                timeout=120
            )
            _assert_rendered(app)
            assert _capacity_signature(app) == linear_signature

            app.checkbox(key="bending_parabolic_toggle").set_value(False).run(
                timeout=120
            )
            _assert_rendered(app)
            assert _capacity_signature(app) == linear_signature


def main() -> None:
    verify_shared_subplot_composer_preserves_child_figure()
    verify_all_section_and_moment_branches()
    print("bending diagram contract: PASS")


if __name__ == "__main__":
    main()
