from inputs_application.shear_state_normalization import (
    SUPPORTED_SHEAR_LEG_COUNTS,
    normalize_invalid_shear_state_updates,
    normalize_shear_link_pair,
)
from inputs_page_modules.widgets.builders import (
    build_shear_reinforcement_basic_widget_payloads,
)
from inputs_page_modules.session.shear_normalization import (
    build_invalid_shear_state_updates,
)
from inputs_v2.domain.beam_inputs import (
    SUPPORTED_SHEAR_LEG_COUNTS as V2_SUPPORTED_SHEAR_LEG_COUNTS,
)


def test_supported_odd_leg_counts_are_preserved() -> None:
    assert normalize_shear_link_pair({"lig_d": 10, "lig_legs": 3}) == {
        "lig_d": 10,
        "lig_legs": 3,
    }
    assert normalize_invalid_shear_state_updates(
        {"lig_d": 10, "lig_legs": 5, "s_lig": 200}, {}
    ).get("lig_legs", 5) == 5


def test_widget_only_offers_domain_supported_leg_counts() -> None:
    payloads = build_shear_reinforcement_basic_widget_payloads(
        link_diameter_widget_key="inputs_lig_d",
        link_legs_widget_key="inputs_lig_legs",
        link_spacing_widget_key="inputs_s_lig",
        link_diameter_label="Link dia (mm)",
        reo_bar_diameters=(10, 12, 16),
        link_diameter_value=10,
        link_legs_value=2,
        link_spacing_value=200,
    )
    assert payloads[1]["options"] == [0, *SUPPORTED_SHEAR_LEG_COUNTS]


def test_runtime_and_v2_supported_leg_contracts_match() -> None:
    assert SUPPORTED_SHEAR_LEG_COUNTS == V2_SUPPORTED_SHEAR_LEG_COUNTS


def test_router_hydration_uses_the_same_supported_leg_contract() -> None:
    assert build_invalid_shear_state_updates(
        {"lig_d": 12, "lig_legs": 3, "s_lig": 175}
    ).get("lig_legs", 3) == 3
