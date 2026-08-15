from tools.verification.recipes.one_click_recipe_defs import (
    _manual_actions,
    _manual_actions_with_sls,
)


def test_manual_recipe_populates_current_shear_and_axial_owners() -> None:
    actions = _manual_actions(300.0, 400.0)

    assert actions["manual_uls_Vstar"] == 400.0
    assert actions["manual_uls_Nstar"] == 0.0
    assert actions["manual_sls_Vstar"] == 0.0
    assert actions["manual_sls_Nstar"] == 0.0


def test_serviceability_recipe_populates_current_sls_shear_owner() -> None:
    actions = _manual_actions_with_sls(80.0, 20.0, 50.0, 15.0)

    assert actions["sls_Vstar"] == 15.0
    assert actions["manual_sls_Vstar"] == 15.0
