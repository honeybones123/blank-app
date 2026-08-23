from __future__ import annotations

from pathlib import Path

from engineering_page_sections import shear_torsion_dimensions_checks as checks_ui
from engineering_page_sections.shear_checks_context import ShearCheckFamilyInput


ROOT = Path(__file__).resolve().parents[1]


def _view() -> checks_ui.ShearTorsionDimensionsView:
    evidence = ShearCheckFamilyInput(
        live_state={"b": 250.0},
        actions={"Vu": 120.0, "Tu": 0.0},
        results={"V_eq": 120.0},
        published_results={"revision": "beam-7"},
        phi=0.75,
        duct_factor=0.0,
        use_general_kv=True,
        method="General epsilon-x method",
    )
    return checks_ui.ShearTorsionDimensionsView(
        evidence=evidence,
        A_cp=75_000.0,
        Ao=67_500.0,
        Asv=157.08,
        D=300.0,
        D_used=300.0,
        T_star=0.0,
        Tcr_kNm=10.7,
        V_eq=120.0,
        V_star=120.0,
        b=250.0,
        b_used=250.0,
        b_v=250.0,
        d=255.0,
        d_v=255.0,
        dv_1=216.0,
        dv_2=229.5,
        f_syv=500.0,
        fc=40.0,
        k_d=0.0,
        legs=2.0,
        lig_d=10.0,
        method="General epsilon-x method",
        phi=0.75,
        s=200.0,
        sigma_cp=0.0,
        step1_req="\\le",
        step1_text="not required (strength check only)",
        sum_duct=0.0,
        theta_deg=45.0,
        torsion_eq_kN=0.0,
        torsion_required=False,
        torsion_required_limit=2.0,
        u_c=1_100.0,
        uh=990.0,
    )


def test_torsion_dimensions_module_owns_exact_three_cards(monkeypatch) -> None:
    cards: list[dict[str, object]] = []
    monkeypatch.setattr(
        checks_ui,
        "render_expandable_step",
        lambda **kwargs: cards.append(kwargs),
    )

    checks_ui.render_shear_torsion_dimensions_checks(_view())

    assert [card["step_id"] for card in cards] == [
        "shear_check1",
        "shear_check2",
        "shear_check3",
    ]
    assert [card["title"] for card in cards] == [
        "Check 1 — Torsion cracking check",
        "Check 2 — Equivalent shear $V_{eq}^*$",
        "Check 3 — Shear-resisting section (b_v, d_v, ligs)",
    ]
    assert cards[0]["status_kind"] == "pass"
    assert cards[1]["diagram_render_fn"] is None
    assert callable(cards[2]["diagram_render_fn"])
    assert all(callable(card["info_render_fn"]) for card in cards)


def test_runtime_delegates_checks_one_to_three_to_the_module() -> None:
    runtime_source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")
    module_source = (
        ROOT
        / "engineering_page_sections"
        / "shear_torsion_dimensions_checks.py"
    ).read_text(encoding="utf-8")

    assert "render_shear_torsion_dimensions_checks(" in runtime_source
    assert "ShearTorsionDimensionsView(" in runtime_source
    assert 'step_id="shear_check1"' not in runtime_source
    assert 'step_id="shear_check2"' not in runtime_source
    assert 'step_id="shear_check3"' not in runtime_source
    assert 'step_id="shear_check1"' in module_source
    assert 'step_id="shear_check2"' in module_source
    assert 'step_id="shear_check3"' in module_source
    assert "build_shear_calc_bundle_from_state" not in module_source
    assert "build_live_canonical_shear_state" not in module_source
