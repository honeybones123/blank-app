import pandas as pd

from batch_design.ui import project_beam_manager_adapters as adapters


def test_schedule_preview_and_export_projection_use_cached_rows(monkeypatch):
    rows = [
        {
            "active": True,
            "beam_id": "beam_1",
            "beam_label": "Beam 1",
            "sec_shape": "RECT",
            "b": 300,
            "D": 600,
            "L": 7000,
            "bot1_count": 3,
            "db_bot_1": 20,
            "top1_count": 2,
            "db_top_1": 16,
            "lig_d": 10,
            "s_lig": 200,
            "overall_status": "PASS",
            "strength_status": "PASS",
            "detailing_status": "PASS",
            "bending_status": "PASS",
            "shear_status": "PASS",
            "crack_status": "PASS",
            "deflection_status": "PASS",
            "last_checked_at": "2026-07-06T10:00:00",
        }
    ]
    monkeypatch.setattr(adapters, "build_beam_schedule_export_rows", lambda: rows)

    preview = adapters.build_schedule_preview_df()
    export = adapters.build_schedule_export_df()

    assert preview.to_dict("records")[0]["Geometry"] == "RECT 300 x 600 / L 7000"
    assert export.to_dict("records")[0]["beam_id"] == "beam_1"


def test_schedule_editor_projection_and_coercion(monkeypatch):
    monkeypatch.setattr(
        adapters,
        "build_beam_schedule_rows",
        lambda: [
            {
                "active": True,
                "beam_id": "beam_1",
                "beam_label": "Beam 1",
                "sec_shape": "RECT",
                "b": 300,
                "D": 600,
                "overall_status": "PASS",
                "strength_status": "PASS",
                "detailing_status": "PASS",
            }
        ],
    )
    monkeypatch.setattr(adapters, "SHARED_DEFAULTS", {"b": 250, "D": 500, "sec_shape": "RECT"})

    frame = adapters.build_beam_schedule_df()

    assert frame.to_dict("records")[0]["beam_id"] == "beam_1"
    assert adapters.coerce_beam_schedule_value("b", "325.5") == 325.5
    assert adapters.coerce_beam_schedule_value("lig_d", "12") == 12
    assert adapters.coerce_beam_schedule_value("sec_shape", "bad") == "RECT"


def test_sync_beam_records_marks_summary_not_run_when_params_change(monkeypatch):
    monkeypatch.setitem(
        adapters.st.session_state,
        "beam_records",
        {
            "beam_1": {
                "beam_label": "Beam 1",
                "params": {"b": 300, "D": 600, "sec_shape": "RECT"},
                "summary": {"overall_status": "PASS"},
                "meta": {},
            }
        },
    )
    monkeypatch.setattr(adapters, "SHARED_DEFAULTS", {"b": 250, "D": 500, "sec_shape": "RECT"})
    monkeypatch.setattr(adapters, "make_not_run_beam_summary", lambda: {"overall_status": "NOT_RUN"})

    changed = adapters.sync_beam_records_from_schedule_df(
        pd.DataFrame([{"beam_id": "beam_1", "beam_label": "Beam A", "b": 350, "D": 600, "sec_shape": "RECT"}])
    )

    record = adapters.st.session_state["beam_records"]["beam_1"]
    assert changed == {"beam_1"}
    assert record["beam_label"] == "Beam A"
    assert record["params"]["b"] == 350.0
    assert record["summary"]["overall_status"] == "NOT_RUN"
