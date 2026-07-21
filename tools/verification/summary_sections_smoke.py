from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ui.summary_sections as summary_sections
import ui.summary_rows as summary_rows
import ui_seamless_steps


MOJIBAKE_MARKERS = ("\u00c3", "\ufffd", "Ã", "�")


def _assert_no_mojibake(text: str) -> None:
    assert not any(marker in text for marker in MOJIBAKE_MARKERS), repr(text)


def _sample_rows(family: str) -> list[dict[str, object]]:
    if family == "deflection":
        return [
            {
                "uid": "defl_step_1",
                "title": "Immediate deflection",
                "calculated": "8.0 mm",
                "requirement": "Span/250",
                "util": "0.72",
                "status": "PASS",
                "ok": True,
                "is_primary": True,
            },
            {
                "uid": "defl_step_2",
                "title": "Long-term deflection",
                "calculated": "11.5 mm",
                "requirement": "Span/250",
                "util": "0.91",
                "status": "PASS",
                "ok": True,
            },
        ]
    return [
        {
            "uid": f"{family}_step_1",
            "title": f"{family.title()} governing check",
            "action": "125 kN",
            "capacity": "175 kN",
            "util": "0.71",
            "status": "PASS",
            "ok": True,
            "is_primary": True,
        },
        {
            "uid": f"{family}_step_2",
            "title": f"{family.title()} secondary check",
            "action": "90 kN",
            "capacity": "160 kN",
            "util": "0.56",
            "status": "PASS",
            "ok": True,
        },
    ]


def _capture_render(rows: list[dict[str, object]], key_prefix: str) -> list[str]:
    captured: list[str] = []
    original_markdown = summary_sections.st.markdown
    try:
        summary_sections.st.markdown = lambda body, **_: captured.append(str(body))
        summary_sections.render_clickable_summary_table(rows, key_prefix=key_prefix)
    finally:
        summary_sections.st.markdown = original_markdown
    return captured


def test_legacy_facade_uses_shared_summary_sections() -> None:
    assert ui_seamless_steps._summary_card_css is summary_sections.summary_card_css
    assert ui_seamless_steps.SUMMARY_DASH == summary_sections.SUMMARY_DASH
    assert ui_seamless_steps.build_summary_check_card_html is summary_sections.build_summary_check_card_html
    assert ui_seamless_steps.build_final_summary_check_card_html is summary_sections.build_final_summary_check_card_html
    assert ui_seamless_steps.render_clickable_summary_table is summary_sections.render_clickable_summary_table


def test_direct_card_builder_keeps_expected_structure() -> None:
    html = summary_sections.build_summary_check_card_html(
        title="Bending &mdash; ULS",
        description="",
        family="bending",
        capacity="175 kNm",
        action="125 kNm",
        utilisation="0.71",
        status="PASS",
        rows=_sample_rows("bending"),
    )
    assert 'class="summary-check-card status-pass"' in html
    assert "Bending &mdash; ULS" in html
    assert "Detailed checks" in html
    assert "summary-detail-table" in html


def test_final_summary_card_adapter_normalises_inputs_card_values() -> None:
    bad_dash = "\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u20ac\u009d"
    assert summary_sections.normalise_summary_display_value(bad_dash) == summary_sections.SUMMARY_DASH

    model = summary_sections.build_final_summary_check_card_model(
        title="Deflection &mdash; SLS",
        family="deflection",
        capacity=bad_dash,
        action="&delta;total = 0.00 mm",
        utilisation=bad_dash,
        status="NOT RUN",
        rows=[
            {
                "uid": "defl_total",
                "title": "Total deflection",
                "calculated": "&delta;total = 0.00 mm",
                "requirement": "&delta;lim = 8.00 mm (L/250)",
                "util": bad_dash,
                "status": "NOT RUN",
                "ok": None,
                "is_primary": True,
            }
        ],
        threshold_text="SLS load not supplied",
    )
    assert model["action"] == "&delta;total = 0.00 mm"
    assert model["capacity"] == "&delta;lim = 8.00 mm (L/250)"
    assert model["utilisation"] == summary_sections.SUMMARY_DASH
    assert model["status"] == "NOT RUN"
    assert model["threshold_text"] == "SLS load not supplied"

    html = summary_sections.build_final_summary_check_card_html(
        title="Deflection &mdash; SLS",
        family="deflection",
        capacity=bad_dash,
        action="&delta;total = 0.00 mm",
        utilisation=bad_dash,
        status="NOT RUN",
        rows=model["rows"],
        threshold_text="SLS load not supplied",
    )
    assert "SLS load not supplied" in html
    _assert_no_mojibake(html)


def test_inputs_final_summary_cards_use_shared_adapter() -> None:
    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8")
    extracted_builder = (ROOT / "inputs_page_modules" / "summaries" / "builders.py").read_text(encoding="utf-8")
    assert "def _build_summary_cards_html_for_current_state" not in shell_source
    final_cards = source.split("def _build_summary_cards_html_for_current_state", 1)[1].split(
        '_summary_html_cache_key = "_final_publication_summary_card_html_cache"',
        1,
    )[0]
    assert final_cards.count("build_final_summary_check_card_html(") == 0
    assert "return build_inputs_summary_html(" in final_cards
    assert "def build_inputs_summary_html(" in extracted_builder
    extracted_html_builder = extracted_builder.split("def build_inputs_summary_html(", 1)[1]
    assert "build_final_summary_check_card_html(**card_source_to_summary_kwargs(card))" in extracted_html_builder
    assert "build_summary_check_card_html(" not in final_cards
    assert "build_deflection_summary_rows(" in (ROOT / "deflection.py").read_text(encoding="utf-8")
    assert "threshold_text=\"SLS load not supplied\"" not in final_cards
    assert '"threshold_text": ""' in extracted_builder
    _assert_no_mojibake(final_cards)


def test_representative_summary_families_render_card_stack() -> None:
    cases = {
        "bending": "Bending &mdash; ULS",
        "shear": "Shear &mdash; ULS",
        "deflection": "Deflection &mdash; SLS",
    }
    for family, title in cases.items():
        rendered = "\n".join(_capture_render(_sample_rows(family), key_prefix=family))
        assert ".summary-card-stack" in rendered
        assert 'class="summary-card-stack"' in rendered
        assert "summary-check-card" in rendered
        assert title in rendered


def test_shared_summary_row_builders_preserve_representative_rows() -> None:
    check_rows = [
        {
            "uid": "bend_strength_pos",
            "title": "Positive bending",
            "calculated": "phiM_u = 175 kNm",
            "requirement": "M_u* = 125 kNm",
            "util": "0.71",
            "status": "PASS",
            "is_primary": True,
            "moment_sign": "positive",
        },
        {
            "uid": "bend_duct",
            "title": "Ductility limit",
            "calculated": "k_u = 0.22",
            "requirement": "k_u <= 0.36",
            "util": "0.61",
            "status": "PASS",
        },
    ]
    legacy = summary_rows.build_bending_legacy_summary_rows(check_rows)
    assert legacy[0]["Check"] == "Positive bending"
    assert legacy[0]["Calculated capacity"] == "phiM_u = 175 kNm"
    assert legacy[0]["Applied design action"] == "M_u* = 125 kNm"
    assert legacy[0]["moment_sign"] == "positive"

    clickable = summary_rows.build_bending_clickable_summary_rows(check_rows)
    assert clickable[0]["uid"] == "bend_strength_pos"
    assert clickable[0]["capacity"] == "phiM_u = 175 kNm"
    assert clickable[0]["action"] == "M_u* = 125 kNm"
    assert clickable[0]["ok"] is True
    assert clickable[0]["tab"] == "ULS Checks"
    assert clickable[0]["jump_target_id"] == "bending_uls_1_7"

    shear_legacy = summary_rows.build_shear_legacy_summary_rows(
        [
            {
                "uid": "shear_check7",
                "title": "Sectional shear capacity",
                "capacity": "phiVu = 200 kN",
                "action": "Vu* = 120 kN",
                "util": "0.60",
                "status": "PASS",
            }
        ]
    )
    shear_clickable = summary_rows.build_shear_clickable_summary_rows(shear_legacy)
    assert shear_clickable[0]["uid"] == "shear_check7"
    assert shear_clickable[0]["is_primary"] is True
    assert shear_clickable[0]["value"] == "phiVu = 200 kN"
    assert shear_clickable[0]["limit"] == "Vu* = 120 kN"

    deflection = summary_rows.build_deflection_summary_rows(
        [
            {
                "uid": "defl_total",
                "title": "Total deflection (short + long-term)",
                "calculated": "\u00ce\u00b4total = 8.00 mm",
                "requirement": "\u00ce\u00b4lim = 10.00 mm (L/250)",
                "util": "\u00e2\u20ac\u201d",
                "status": "NOT RUN",
                "is_primary": True,
            }
        ]
    )
    assert deflection[0]["calculated"] == "&delta;total = 8.00 mm"
    assert deflection[0]["requirement"] == "&delta;lim = 10.00 mm (L/250)"
    assert deflection[0]["util"] == "&mdash;"
    assert deflection[0]["jump_target_id"] == "defl_long"

    creep = summary_rows.build_creep_summary_rows(
        phi_cc_t=1.25,
        phi_cc_star_table=2.0,
        eps_cc_micro=123.4,
    )
    assert creep[0]["title"] == "Design creep coefficient \u03d5_cc(t)"
    assert creep[0]["capacity"] == "\u03d5_cc(t) = 1.25"
    assert creep[2]["capacity"] == "\u03b5_cc = 123.4 \u00b5\u03b5"

    shrinkage = summary_rows.build_shrinkage_summary_rows(
        eps_cse=0.0001,
        eps_csd_t=0.0002,
        eps_cs_total=0.0003,
    )
    assert shrinkage[0]["capacity"] == "100.0 \u00b5\u03b5"
    assert shrinkage[2]["title"] == "Total shrinkage \u03b5_cs"


def test_specialized_pages_use_shared_summary_row_builders() -> None:
    root = ROOT
    sources = {
        "bending": (root / "bending_page.py").read_text(encoding="utf-8"),
        "shear": (root / "shear_page.py").read_text(encoding="utf-8"),
        "crack": (root / "crack_page.py").read_text(encoding="utf-8"),
        "deflection": (root / "deflection.py").read_text(encoding="utf-8"),
        "creep": (root / "creep.py").read_text(encoding="utf-8"),
        "shrinkage": (root / "shrinkage.py").read_text(encoding="utf-8"),
    }
    assert "build_bending_legacy_summary_rows(" in sources["bending"]
    assert "build_bending_clickable_summary_rows(" in sources["bending"]
    assert "finalize_bending_check_row(" not in sources["bending"]
    assert "BENDING_ROW_UID_TO_TAB" not in sources["bending"]

    assert "build_shear_legacy_summary_rows(" in sources["shear"]
    assert "build_shear_clickable_summary_rows(" in sources["shear"]
    assert "filter_shear_summary_rows(" in sources["shear"]
    assert "def _clickable_rows_from_shear_summary" not in sources["shear"]

    assert "build_crack_summary_rows(" in sources["crack"]
    assert "mark_primary_summary_row(" in sources["crack"]
    assert "rows.append({" not in sources["crack"].split("crack_pack = build_crack_check_rows_from_state", 1)[1].split("clicked_uid = render_clickable_summary_table", 1)[0]

    assert "build_deflection_summary_rows(" in sources["deflection"]
    assert "ROWS = defl_pack.get(\"rows\", [])" not in sources["deflection"]
    assert "build_creep_summary_rows(" in sources["creep"]
    assert "sync_legacy_value_limit({" not in sources["creep"]
    assert "build_shrinkage_summary_rows(" in sources["shrinkage"]
    assert "sync_legacy_value_limit({" not in sources["shrinkage"]


def main() -> int:
    test_legacy_facade_uses_shared_summary_sections()
    test_direct_card_builder_keeps_expected_structure()
    test_final_summary_card_adapter_normalises_inputs_card_values()
    test_inputs_final_summary_cards_use_shared_adapter()
    test_representative_summary_families_render_card_stack()
    test_shared_summary_row_builders_preserve_representative_rows()
    test_specialized_pages_use_shared_summary_row_builders()
    print("summary_sections_smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
