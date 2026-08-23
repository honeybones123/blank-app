from __future__ import annotations

from pathlib import Path

from reporting.bending_report_projection import (
    BendingReportState,
    build_bending_report,
)


ROOT = Path(__file__).resolve().parents[1]


def _reference_results() -> dict:
    return {
        "phi_Mu_cap": 145.0,
        "Mu_util": 0.72,
        "fctf": 3.4,
        "Z_gross": 9_000_000.0,
        "Mcr": 30.6,
        "As_min": 420.0,
    }


def _reference_params() -> dict:
    return {
        "b": 300.0,
        "D": 600.0,
        "fc": 40.0,
        "fsy": 500.0,
        "Ast": 1600.0,
        "d": 550.0,
        "phi": 0.85,
        "Mu_star_uls": 104.4,
        "Mu_star_sls": 72.0,
        "Ec": 30_000.0,
        "Es": 200_000.0,
        "moment_sign": "positive",
    }


def _reference_state() -> BendingReportState:
    return BendingReportState.from_mapping(
        {
            "bending_sls_dn": 92.5,
            "bending_sls_kappa": 1.25e-7,
            "bending_sls_eps_top": -1.15625e-5,
            "bending_sls_fs_outer": 24.375,
            "nb_top": 2,
            "db_top": 12.0,
            "cover_top": 30.0,
        }
    )


def test_report_projection_preserves_the_complete_reference_tree() -> None:
    report = build_bending_report(
        _reference_results(),
        _reference_params(),
        state=_reference_state(),
    )

    assert report["module_title"] == "Bending (ULS)"
    assert report["summary"] == [
        ("Demand", "104.4 kNm"),
        ("Capacity", "145.0 kNm"),
        ("Utilisation", "0.72"),
        ("Outcome", "PASS"),
    ]
    assert [tab["tab_title"] for tab in report["tabs"]] == [
        "ULS Checks",
        "SLS Checks",
        "Minimum strength checks",
    ]
    assert [[box["id"] for box in tab["boxes"]] for tab in report["tabs"]] == [
        ["1.1", "1.2", "1.3", "1.4", "1.4A", "1.5", "1.6", "1.7"],
        ["3.1", "3.2", "3.3", "3.4", "3.5", "3.6"],
        ["2.1", "2.2", "2.3", "2.4", "2.5"],
    ]
    assert report["tabs"][0]["boxes"][0]["result"] == (
        "alpha2 = 0.790, gamma = 0.870"
    )
    assert report["tabs"][1]["boxes"][0]["result"] == "n = 6.67"
    assert report["tabs"][2]["boxes"][0]["result"] == "f_ct,f = 3.400 MPa"
    assert callable(report["tabs"][0]["boxes"][0]["diagram"])
    assert callable(report["tabs"][1]["boxes"][1]["diagram"])


def test_missing_sls_publication_projects_the_existing_warning_box() -> None:
    report = build_bending_report(
        _reference_results(),
        _reference_params(),
        state=BendingReportState.from_mapping({}),
    )

    sls_boxes = report["tabs"][1]["boxes"]
    assert len(sls_boxes) == 1
    assert sls_boxes[0]["id"] == "SLS"
    assert sls_boxes[0]["status"] == "warn"
    assert sls_boxes[0]["title"] == "SLS checks not available"


def test_report_projection_has_no_page_or_session_state_owner() -> None:
    projection = (
        ROOT / "reporting" / "bending_report_projection.py"
    ).read_text(encoding="utf-8")
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    calculations = (
        ROOT / "engineering_page_sections" / "bending_calculations.py"
    ).read_text(encoding="utf-8")

    assert "streamlit" not in projection
    assert "st.session_state" not in projection
    assert "def build_bending_report(" not in runtime
    assert "bind_runtime(" not in runtime
    assert "bind_runtime(" not in calculations
    assert "from reporting.bending_report_projection import" in calculations
    assert "BendingReportState.from_mapping(st.session_state)" in calculations
