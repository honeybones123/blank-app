from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_calcbox_owns_light_and_heavy_render_policy() -> None:
    source = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8-sig")
    start = source.index("def step_expander_calcbox(")
    end = source.index("\ndef apply_step_summary_card_css", start)
    renderer = source[start:end]

    assert 'render_policy: str = "mounted"' in renderer
    assert 'mount_closed_body = policy in {"mounted", "eager", "client_mounted"}' in renderer
    assert 'on_change="ignore" if mount_closed_body else "rerun"' in renderer
    assert 'if not expander.open and not mount_closed_body:' in renderer
    assert 'if str(uid).startswith("bending_"):' in renderer
    assert '"_bending_diagram_bundle_ready_fingerprint"' not in renderer
    assert '"_bending_diagram_render_stage"' not in renderer


def test_bending_opts_light_cards_into_canonical_mounted_policy() -> None:
    source = (ROOT / "bending_tabs.py").read_text(encoding="utf-8-sig")
    page = (ROOT / "bending_page.py").read_text(encoding="utf-8-sig")

    assert 'render_policy="mounted"' in source
    assert "calcbox_performance" not in page
    assert "install_bending_hybrid_calcbox_runtime" not in page
    assert not (ROOT / "engineering_page_sections" / "calcbox_performance.py").exists()


def test_open_calc_body_keeps_semantic_colour_connection() -> None:
    source = (ROOT / "widgets_helpers.py").read_text(encoding="utf-8-sig")

    assert "details[open]:has(span.step-neutral) > div" in source
    assert "details[open]:has(span.step-pass) > div" in source
    assert "details[open]:has(span.step-fail) > div" in source
    assert "box-shadow: inset 4px 0 0 #1f77b4" in source
    assert "box-shadow: inset 4px 0 0 #28a745" in source
    assert "box-shadow: inset 4px 0 0 #dc3545" in source
