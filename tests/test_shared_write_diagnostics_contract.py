from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_default_seeding_does_not_collect_production_write_diagnostics() -> None:
    source = (ROOT / "state_and_helpers.py").read_text(encoding="utf-8-sig")
    set_shared_body = source.split("def set_shared(", 1)[1].split(
        "\ndef set_ui(", 1
    )[0]

    assert "diagnostics_enabled = bool(" in set_shared_body
    assert '_set_shared_is_user_intent_source(source)' in set_shared_body
    assert 'st.session_state.get("_dev_mode", False)' in set_shared_body
    assert set_shared_body.index("if diagnostics_enabled:") < set_shared_body.index(
        "inspect.stack()[1]"
    )
