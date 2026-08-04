from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import report_helpers
import summary_table_ui


def test_report_status_contracts() -> None:
    assert report_helpers.format_report_status_label("PASS") == "PASS"
    assert report_helpers.format_report_status_label("FAIL") == "FAIL"
    assert report_helpers.format_report_status_label("INFO") == "INFO"
    assert (
        report_helpers.format_report_status_label(
            "WARN",
            strength_status="PASS",
            detailing_status="FAIL",
        )
        == "PASS WITH WARNINGS"
    )
    assert "PASS" in report_helpers.format_report_status_badge("PASS")
    assert "FAIL" in report_helpers.format_report_status_badge("FAIL")


def test_report_row_normalisation_contract() -> None:
    row = report_helpers._normalise_report_row(
        {
            "uid": "bend_strength",
            "title": "Bending strength",
            "calculated": "180 kNm",
            "requirement": "125 kNm",
            "util": "0.69",
            "status": "PASS",
            "ok": True,
            "is_primary": True,
        }
    )
    assert row["capacity"] == "180 kNm"
    assert row["value"] == "180 kNm"
    assert row["action"] == "125 kNm"
    assert row["limit"] == "125 kNm"
    assert row["is_primary"] is True

    fallback = report_helpers._pick_primary_check([], "Fallback check")
    assert fallback["title"] == "Fallback check"
    assert fallback["status"] == "NOT_RUN"


def test_report_formatting_contracts() -> None:
    assert report_helpers._display_value(None) == "-"
    assert report_helpers._display_value(12.3456, 2) == "12.35"
    assert report_helpers._safe_float("bad") is None
    assert report_helpers._safe_float("1.25") == 1.25
    assert report_helpers._serviceability_status("PASS", "PASS") == "PASS"
    assert report_helpers._serviceability_status("FAIL", "PASS") == "FAIL"
    assert report_helpers._worst_utilisation("0.5", "0.9", None) == 0.9
    assert report_helpers._rebar_layer_text(3, 20) == "3N20"
    assert report_helpers._ligature_text(10, 200, 2) == "N10 @ 200, 2 legs"
    assert report_helpers._cover_text(40, 40, 40) == "40 mm"
    assert report_helpers._mm_to_m_text(2500) == "2.500 m"


def test_legacy_summary_table_contract() -> None:
    captured_markdown: list[str] = []
    captured_components: list[str] = []
    original_markdown = summary_table_ui.st.markdown
    original_components_html = summary_table_ui.components.html
    original_query_params = summary_table_ui.st.query_params
    original_session_state = summary_table_ui.st.session_state
    try:
        summary_table_ui.st.markdown = lambda body, **_: captured_markdown.append(str(body))
        summary_table_ui.components.html = lambda body, **_: captured_components.append(str(body))
        summary_table_ui.st.query_params = {}
        summary_table_ui.st.session_state = {}
        clicked = summary_table_ui.render_clickable_summary_table(
            [
                {
                    "uid": "row_1",
                    "title": "Strength",
                    "value": "180 kNm",
                    "limit": "125 kNm",
                    "util": "0.69",
                    "status": "PASS",
                    "ok": True,
                    "tab": "ULS Checks",
                    "is_primary": True,
                }
            ],
            key="contract",
        )
    finally:
        summary_table_ui.st.markdown = original_markdown
        summary_table_ui.components.html = original_components_html
        summary_table_ui.st.query_params = original_query_params
        summary_table_ui.st.session_state = original_session_state

    rendered = "\n".join(captured_markdown)
    script = "\n".join(captured_components)
    assert clicked is None
    assert "summary-table" in rendered
    assert "Strength" in rendered
    assert 'data-uid="row_1"' in rendered
    assert "contract_clicked_uid" in script


def main() -> int:
    test_report_status_contracts()
    test_report_row_normalisation_contract()
    test_report_formatting_contracts()
    test_legacy_summary_table_contract()
    print("report_export_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
