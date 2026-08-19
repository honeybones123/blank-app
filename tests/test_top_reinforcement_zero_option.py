from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_top_reinforcement_rows_allow_zero_bars_but_bottom_rows_do_not() -> None:
    source = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8")

    assert "allow_zero_bars: bool = False" in source
    assert "(allow_zero_bars and int(option) == 0) or int(option) >= 2" in source
    assert 'allow_zero_bars=section_norm == "top"' in source
