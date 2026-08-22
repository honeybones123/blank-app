from pathlib import Path

import pytest

from bending_diagrams import make_sls_transformed_section_figure
from engineering_page_sections.bending_sls_checks import (
    _equilibrium_assembly,
    _equilibrium_substitution,
    _layer_frame,
)


ROOT = Path(__file__).resolve().parents[1]


def test_active_sls_tab_delegates_to_the_authoritative_six_check_renderer() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")
    active = source[source.index("def render_sls_tab(") :]

    delegate = active.index("return render_authoritative_sls_checks(")
    legacy_local_solver = active.index("nb_bot = st.session_state.get")
    assert delegate < legacy_local_solver
    assert "top_results=top_results" in active[:legacy_local_solver]


def test_sls_teaching_sequence_is_n_dn_icr_curvature_strain_stress() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_sls_checks.py"
    ).read_text(encoding="utf-8")
    titles = (
        "Check 1 — Modular ratio",
        "Check 2 — Cracked neutral-axis depth",
        "Check 3 — Cracked second moment of area I_cr",
        "Check 4 — Curvature",
        "Check 5 — Strain distribution",
        "Check 6 — Concrete and reinforcement stresses",
    )

    positions = tuple(source.index(title) for title in titles)
    assert positions == tuple(sorted(positions))
    assert "Check 7" not in source


def test_sls_check_2_references_but_does_not_recalculate_modular_ratio() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_sls_checks.py"
    ).read_text(encoding="utf-8")
    check_1 = source[source.index("check1_details =") : source.index("layer_table =")]
    check_2 = source[source.index("check2_details =") : source.index("def check2_table")]

    assert r"n=\frac{{E_s}}{{E_c}}" in check_1
    assert "**From Check 1**" in check_2
    assert "$$n={n:.4f}$$" in check_2
    assert r"\frac{{E_s}}{{E_c}}" not in check_2


def test_sls_check_2_contains_no_uls_only_material_solution() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_sls_checks.py"
    ).read_text(encoding="utf-8")
    check_2 = source[source.index("check2_details =") : source.index("def check2_table")]

    for forbidden in ("alpha_2", "gamma", "f_{sy}", "epsilon_{cu}", "yield"):
        assert forbidden not in check_2
    assert "elastic transformed-section equilibrium" in check_2
    assert r"Q_{{s,t,i}}=nA_{{s,i}}(y_i-d_n)" in check_2
    assert r"Q_{{s,c,i}}=(n-1)A_{{s,i}}(d_n-y_i)" in check_2


def test_displayed_layer_table_uses_authoritative_classification_and_factors() -> None:
    layers = (
        {
            "layer_id": "top",
            "label": "Physical top layer",
            "area_mm2": 200.0,
            "depth_from_compression_mm": 40.0,
            "state": "compression",
            "included": True,
            "transformed_factor": 5.5,
        },
        {
            "layer_id": "bottom",
            "label": "Physical bottom layer",
            "area_mm2": 500.0,
            "depth_from_compression_mm": 260.0,
            "state": "tension",
            "included": True,
            "transformed_factor": 6.5,
        },
    )

    frame = _layer_frame(layers)

    assert tuple(frame["Layer"]) == ("Physical top layer", "Physical bottom layer")
    assert tuple(frame["Final state"]) == ("compression", "tension")
    assert tuple(frame["Factor"]) == pytest.approx((5.5, 6.5))
    assert tuple(frame["Transformed contribution"]) == (
        "(n - 1) A_s (d_n - y_i)",
        "n A_s (y_i - d_n)",
    )


def test_displayed_equilibrium_substitution_matches_published_terms() -> None:
    result = {
        "section_shape": "RECT",
        "width_mm": 250.0,
        "neutral_axis_depth_mm": 100.0,
        "concrete_first_moment_mm3": 1000.0,
        "layers": (
            {
                "state": "compression",
                "included": True,
                "transformed_factor": 5.5,
                "area_mm2": 200.0,
                "depth_from_compression_mm": 40.0,
                "first_moment_mm3": 125.0,
            },
            {
                "state": "tension",
                "included": True,
                "transformed_factor": 6.5,
                "area_mm2": 500.0,
                "depth_from_compression_mm": 260.0,
                "first_moment_mm3": 1125.0,
            },
            {
                "state": "compression",
                "included": False,
                "first_moment_mm3": 50.0,
            },
        ),
    }

    assert _equilibrium_substitution(result) == (
        r"1,000.000 + 125.000 = 1,125.000\ \text{mm}^3"
    )
    assert _equilibrium_assembly(result) == (
        r"\frac{250.000(100.000000)^2}{2} + "
        r"(5.5000)(200.000)(100.000000-40.000) = "
        r"(6.5000)(500.000)(260.000-100.000000)"
    )


def test_sls_ignore_option_is_state_based_not_top_bottom_named() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_sls_checks.py"
    ).read_text(encoding="utf-8")

    assert '"Ignore compression reinforcement"' in source
    assert "Reinforcement on the tension side remains included" in source
    assert "Ignore top compression" not in source
    assert "sls_include_comp" not in source


def test_sls_check_2_diagram_is_transformed_section_not_uls_stress_block() -> None:
    figure = make_sls_transformed_section_figure(
        {
            "section_shape": "RECT",
            "width_mm": 250.0,
            "depth_mm": 300.0,
            "neutral_axis_depth_from_top_mm": 50.5,
            "compression_face": "top",
            "layers": (
                {
                    "layer_id": "T1",
                    "label": "Physical top reinforcement",
                    "depth_from_top_mm": 45.0,
                    "state": "compression",
                    "included": True,
                    "transformed_factor": 5.7283,
                },
                {
                    "layer_id": "B1",
                    "label": "Physical bottom reinforcement",
                    "depth_from_top_mm": 255.0,
                    "state": "tension",
                    "included": True,
                    "transformed_factor": 6.7283,
                },
            ),
        }
    )

    annotations = " ".join(str(item.text) for item in figure.layout.annotations)
    assert "Trial d<sub>n</sub>" in annotations
    assert "Active concrete" in annotations
    assert "Cracked concrete tension" in annotations
    assert "T1 — compression" in annotations
    assert "B1 — tension" in annotations
    for uls_only in ("alpha", "gamma", "fsy", "yield", "epsilon"):
        assert uls_only not in annotations.lower()
