from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_side_view_reuses_reported_deflection_before_recomputing() -> None:
    source = (ROOT / "ui" / "diagrams" / "crack_side_view_diagram.py").read_text(encoding="utf-8")
    start = source.index("def compute_crack_diagram_deflection_mesh(")
    end = source.index("\ndef _defl_w_at_x", start)
    fn = source[start:end]

    first_pick = fn.index("reported = _pick_reported_delta_total_mm()")
    guard = fn.index("if reported is None or not math.isfinite(reported):")
    ensure = fn.index("_ensure_deflection_results_for_diagram()", guard)
    second_pick = fn.index("reported = _pick_reported_delta_total_mm()", first_pick + 1)

    assert first_pick < guard < ensure < second_pick
