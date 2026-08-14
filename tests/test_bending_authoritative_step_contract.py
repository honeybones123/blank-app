import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_authoritative_bending_uls_uses_the_eight_step_explanatory_sequence() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")

    expected_titles = (
        "1.1 Stress-block parameters",
        "1.2 Strain compatibility and steel stresses",
        "1.3 Neutral-axis and block-depth solution",
        "1.4 Internal force resultants",
        "1.5 Force-equilibrium verification",
        "1.6 Neutral-axis ratio, ductility and strength factor",
        "1.7 Nominal and design moment capacity",
        "1.8 Final flexural capacity check",
    )

    positions = [source.index(title) for title in expected_titles]
    assert positions == sorted(positions)


def test_authoritative_bending_diagrams_follow_the_equations_they_explain() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")

    assert 'uid="bending_uls_authoritative_2"' in source
    assert "diagram_fn=strain_diagram" in source
    assert '"bending_uls_authoritative_3_diagram", "Neutral axis and block depth"' in source
    assert '"bending_uls_authoritative_4_diagram", "Internal force resultants"' in source
    assert '"bending_uls_authoritative_7_diagram", "ULS force model and capacity"' in source


def test_authoritative_bending_info_preserves_detailed_heading_and_references() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")

    assert 'st.markdown(f"### {heading}\\n\\n{body}")' in source
    assert "#### Why this check matters" in source
    assert "#### References" in source
    assert "[1] AS 3600:2018" in source
    assert "[2] AS 3600:2018" in source


def test_authoritative_bending_info_cites_each_numbered_reference_inline() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8")
    authoritative = source[source.index("def _render_authoritative_uls_steps("):]
    info_bodies = authoritative.split("content_before=info_control(")[1:9]

    assert len(info_bodies) == 8
    for index, body in enumerate(info_bodies, start=1):
        prose, references = body.split("#### References", 1)
        references = references.split('""",', 1)[0]
        numbers = re.findall(
            r"^\[([0-9]+)\] AS 3600:2018", references, re.MULTILINE
        )
        assert numbers, f"Check 1.{index} has no numbered reference list"
        for number in numbers:
            assert f"[{number}]" in prose, (
                f"Check 1.{index} does not cite reference [{number}] inline"
            )


def test_shared_info_button_hides_current_streamlit_material_caret() -> None:
    source = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8")

    assert '[data-testid="stIconMaterial"]' in source
    assert ".material-symbols-rounded" in source
    assert 'div[data-testid="stPopoverBody"] h3' in source
