from __future__ import annotations

from pathlib import Path

from reporting.shear_report_projection import build_shear_report
from shear_calculation_runtime import ShearResults


ROOT = Path(__file__).resolve().parents[1]


def _results() -> ShearResults:
    return ShearResults(
        b_used=250.0,
        D_used=300.0,
        A_cp=75_000.0,
        u_c=1_100.0,
        Ao=67_500.0,
        uh=990.0,
        A_oh=60_750.0,
        Tcr_kNm=10.7,
        torsion_required=False,
        torsion_required_limit=2.0,
        Vt_eq_kN=0.0,
        V_eq=120.0,
        b_v=250.0,
        d_v=255.0,
        Asv=157.1,
        f_syv=500.0,
        eps_x=0.0004,
        term_M=10.0,
        sqrt_inner=20.0,
        numerator=30.0,
        k_v=0.2,
        theta_v_deg=31.0,
        theta_v_rad=0.541052,
        sqrt_fc_limited=6.3249,
        Vuc_kN=80.0,
        Vus_kN=160.0,
        Vu_total_kN=240.0,
        phi_Vu=180.0,
        shear_ok=True,
        Vu_max_kN=400.0,
        LHS=0.3,
        RHS=0.8,
        web_ok=True,
    )


def test_report_projection_preserves_complete_reference_tree() -> None:
    report = build_shear_report(
        results=_results(),
        phi=0.75,
        phi_Vu_cap=180.0,
        util=2.0 / 3.0,
        Vu_star=120.0,
        Tu_star=0.0,
        s_lig=200.0,
        Asv_over_s=0.7855,
        Asv_min_over_s=0.2530,
        max_spacing=225.0,
        min_shear_ok=True,
        spacing_ok=True,
    )

    assert report["module_title"] == "Shear (ULS)"
    assert report["summary"] == [
        ("Demand", "120.0 kN"),
        ("Capacity", "180.0 kN"),
        ("Utilisation", "0.67"),
        ("Outcome", "PASS"),
    ]
    assert [tab["tab_title"] for tab in report["tabs"]] == ["ULS Checks"]
    boxes = report["tabs"][0]["boxes"]
    assert [box["id"] for box in boxes] == [str(i) for i in range(1, 9)]
    assert boxes[0]["title"] == "Actions"
    assert boxes[2]["derivation"] == "εx = 0.00040<br/>k_v = 0.200<br/>θ_v = 31.0°"
    assert boxes[5]["result"] == "PASS"
    assert boxes[5]["status"] == "pass"
    assert boxes[6]["result"] == "PASS"
    assert boxes[7]["result"] == "PASS"


def test_report_projection_has_no_page_or_session_owner() -> None:
    projection_source = (
        ROOT / "reporting" / "shear_report_projection.py"
    ).read_text(encoding="utf-8")
    runtime_source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    assert "streamlit" not in projection_source
    assert "st.session_state" not in projection_source
    assert "update_results" not in projection_source
    assert "def build_shear_report(" not in runtime_source
    assert "shear_report = build_shear_report(" in runtime_source
