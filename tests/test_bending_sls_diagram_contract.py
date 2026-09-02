from pathlib import Path

from engineering_page_sections.bending_sls_transformed_diagram import (
    _CALLOUT_COLOURS,
    _CARD_BG,
)
from engineering_page_sections.bending_sls_diagram import (
    make_sls_compression_first_moment_figure,
)


ROOT = Path(__file__).resolve().parents[1]


def test_sls_check2_step3_has_no_reinforcement_classification_diagram() -> None:
    source = (ROOT / "engineering_page_sections/bending_sls_checks_view.py").read_text(
        encoding="utf-8"
    )
    step3_start = source.index('uid="bending_sls_check2_step_3"')
    step4_start = source.index('uid="bending_sls_check2_step_4"')
    step3_call = source[step3_start:step4_start]

    assert "diagram_fn" not in step3_call
    assert "**Step 3 — Classify every physical reinforcement layer**" in source


def test_sls_canonical_diagram_has_no_compression_region_annotation() -> None:
    source = (ROOT / "engineering_page_sections/bending_sls_diagram.py").read_text(
        encoding="utf-8"
    )

    assert 'text="Active concrete<br>compression region"' not in source


def test_sls_transformed_diagram_has_no_compression_region_annotation() -> None:
    source = (
        ROOT / "engineering_page_sections/bending_sls_transformed_diagram.py"
    ).read_text(encoding="utf-8")

    assert 'text="<b>Active concrete</b><br>compression region"' not in source


def test_sls_transformed_diagram_has_no_redundant_outer_layer_envelopes() -> None:
    source = (
        ROOT / "engineering_page_sections/bending_sls_transformed_diagram.py"
    ).read_text(encoding="utf-8")

    assert "_BAND_FILL" not in source
    assert "x0=0.12 * width" not in source
    assert "x1=0.88 * width" not in source


def test_sls_transformed_diagram_swaps_callout_colours() -> None:
    assert _CALLOUT_COLOURS["tension"] == "#2563eb"
    assert _CALLOUT_COLOURS["compression"] == "#dc2626"
    assert _CARD_BG["tension"].startswith("rgba(219,234,254")
    assert _CARD_BG["compression"].startswith("rgba(254,226,226")


def test_sls_check2_step2_teaches_the_compression_concrete_first_moment() -> None:
    source = (ROOT / "engineering_page_sections/bending_sls_checks_view.py").read_text(
        encoding="utf-8"
    )

    assert "**Step 2 — Determine the compression concrete first moment**" in source
    assert "**Step 2 — Ignore tensile concrete**" not in source
    assert r"A_c=b\,d_n" in source
    assert r"\bar y_c=\frac{{d_n}}{{2}}" in source
    assert r"Q_c=A_c\bar y_c" in source
    assert "not a concrete stress or force" in source
    assert "concrete_q = float(result.get(\"concrete_first_moment_mm3\"" in source


def test_compression_first_moment_diagram_shows_geometric_terms() -> None:
    figure = make_sls_compression_first_moment_figure(
        width_mm=250.0,
        depth_mm=300.0,
        neutral_axis_depth_mm=50.530773,
        neutral_axis_depth_from_top_mm=50.530773,
        compression_face="top",
    )
    annotations = "\n".join(str(item.text) for item in figure.layout.annotations)

    assert "A<sub>c</sub> = b d<sub>n</sub>" in annotations
    assert "Tensile concrete ignored" in annotations
    assert "ȳ<sub>c</sub> = d<sub>n</sub>/2" in annotations
    assert "Q<sub>c</sub> = A<sub>c</sub> × ȳ<sub>c</sub>" in annotations
    assert "25.265 mm" in annotations
