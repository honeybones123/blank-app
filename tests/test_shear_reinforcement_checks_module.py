from __future__ import annotations

from pathlib import Path

from engineering_page_sections import shear_reinforcement_checks as checks_ui
from engineering_page_sections.shear_checks_context import ShearCheckFamilyInput


ROOT = Path(__file__).resolve().parents[1]


def _view() -> checks_ui.ShearReinforcementView:
    evidence = ShearCheckFamilyInput(
        live_state={"b": 250.0},
        actions={"Vu": 120.0},
        results={"Asv": 157.08},
        published_results={"revision": "beam-7"},
        phi=0.75,
        duct_factor=0.0,
        use_general_kv=True,
        method="General epsilon-x method",
    )
    return checks_ui.ShearReinforcementView(
        evidence=evidence,
        Asv_min_over_s_check11=0.08,
        Asv_over_s_check11=0.79,
        min_shear_ok=True,
        min_shear_status="pass",
    )


def test_reinforcement_module_owns_check_ten(monkeypatch) -> None:
    cards: list[dict[str, object]] = []
    monkeypatch.setattr(
        checks_ui,
        "get_param",
        lambda _key, default=None: default,
    )
    monkeypatch.setattr(
        checks_ui,
        "render_expandable_step",
        lambda **kwargs: cards.append(kwargs),
    )

    checks_ui.render_shear_reinforcement_checks(_view())

    assert len(cards) == 1
    assert cards[0]["step_id"] == "shear_check10"
    assert cards[0]["title"] == (
        "Check 10 — Shear reinforcement (spacing + minimum check)"
    )
    assert cards[0]["status_kind"] == "pass"
    assert callable(cards[0]["diagram_render_fn"])


def test_runtime_delegates_check_ten_to_the_module() -> None:
    runtime_source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")
    module_source = (
        ROOT / "engineering_page_sections" / "shear_reinforcement_checks.py"
    ).read_text(encoding="utf-8")

    assert "render_shear_reinforcement_checks(" in runtime_source
    assert "ShearReinforcementView(" in runtime_source
    assert 'step_id="shear_check10"' not in runtime_source
    assert 'step_id="shear_check10"' in module_source
    assert "build_shear_calc_bundle_from_state" not in module_source
    assert "build_live_canonical_shear_state" not in module_source
