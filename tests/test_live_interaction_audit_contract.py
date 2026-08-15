from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_SOURCE = (
    ROOT / "tools" / "verification" / "helpers" / "full_live_interaction_audit.py"
).read_text(encoding="utf-8")


def test_live_switch_audit_clicks_the_semantic_input() -> None:
    """The verifier must dispatch Streamlit's widget event, not style its shell."""

    start = AUDIT_SOURCE.index("def _audit_switches(")
    end = AUDIT_SOURCE.index("\ndef _audit_radio_groups(", start)
    switch_audit = AUDIT_SOURCE[start:end]

    assert 'control.click(force=True, timeout=5_000)' in switch_audit
    assert 'restored_control.click(force=True, timeout=5_000)' in switch_audit
    assert 'locator("xpath=..").click' not in switch_audit


def test_navigation_summary_audit_clicks_the_semantic_action_source_input() -> None:
    source = (
        Path(__file__).parents[1]
        / "tools"
        / "verification"
        / "helpers"
        / "navigation_summary_continuity_audit.py"
    ).read_text(encoding="utf-8")

    assert "toggle.click(force=True)" in source
    assert "first.click(force=True)" in source
    assert 'locator("xpath=..").click' not in source
