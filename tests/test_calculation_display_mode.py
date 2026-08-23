from pathlib import Path

from widgets_helpers import _visible_progressive_steps


ROOT = Path(__file__).resolve().parents[1]


def test_progressive_steps_keep_authored_blocks_intact() -> None:
    steps = ("First explanation and equation", "Second explanation and equation", "Result")

    assert _visible_progressive_steps(steps, 1) == steps[0]
    assert _visible_progressive_steps(steps, 2) == "\n\n".join(steps[:2])
    assert _visible_progressive_steps(steps, 99) == "\n\n".join(steps)


def test_shared_display_mode_defaults_to_standard_and_keeps_progress_per_card() -> None:
    source = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8")

    assert '_CALC_DISPLAY_STANDARD = "standard"' in source
    assert 'return f"calc_display_mode__{section_uid}"' in source
    assert 'return f"calc_step_progress__{uid}"' in source
    assert 'options=("Standard", "Step-by-step")' in source
    assert "on_click=set_progress" in source


def test_bending_uls_has_one_section_control_and_check_2_has_six_authored_steps() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_uls_checks.py"
    ).read_text(encoding="utf-8")

    assert 'render_calculation_display_control("bending_uls")' in source
    assert 'display_section="bending_uls"' in source
    assert "progressive_steps=neutral_axis_progressive_steps" in source
    progressive = source[
        source.index("neutral_axis_progressive_steps = ("):
        source.index("neutral_axis_equilibrium_md = rf\"\"\"")
    ]
    assert progressive.count("**Step ") >= 6
    assert "**Step 1 â€” Concrete compression**" in progressive
    assert "**Step 6 â€” Accept the neutral axis**" in progressive


def test_every_authoritative_bending_uls_check_uses_the_shared_display_section() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_uls_checks.py"
    ).read_text(encoding="utf-8")
    authoritative = source[
        source.index("def _render_authoritative_uls_steps("):
        source.index("# ============================================================\n#  TAB 1")
    ]

    assert 'kwargs.setdefault("display_section", "bending_uls")' in authoritative
    assert authoritative.count("render_uls_calcbox(") == 9  # helper definition plus Checks 1–8
    assert "_progressive_steps_from_headings(details_md)" in (
        ROOT / "widgets_helpers.py"
    ).read_text(encoding="utf-8")
