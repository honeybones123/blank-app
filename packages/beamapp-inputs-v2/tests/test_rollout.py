from inputs_v2.application.rollout import calculation_mode, shadow_results_enabled


def test_rollout_defaults_to_fixture(monkeypatch) -> None:
    monkeypatch.delenv("INPUTS_V2_CALCULATION_MODE", raising=False)
    assert calculation_mode() == "fixture"
    assert shadow_results_enabled() is False


def test_rollout_accepts_shadow_mode(monkeypatch) -> None:
    monkeypatch.setenv("INPUTS_V2_CALCULATION_MODE", "shadow")
    assert calculation_mode() == "shadow"
    assert shadow_results_enabled() is True

