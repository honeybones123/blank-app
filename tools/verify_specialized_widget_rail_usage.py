from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_MARKERS = ("\u00c3", "\ufffd", "Ã", "�")


EXPECTED_USAGES = {
    "bending_page.py": [
        'render_specialized_widget_rail("bending_input_scroll", 4',
    ],
    "shear_page.py": [
        'render_specialized_widget_rail("shear_input_scroll", 4',
    ],
    "deflection.py": [
        'specialized_widget_rail_columns(\n        "deflection_primary_inputs"',
    ],
    "crack_page.py": [
        'specialized_widget_rail_columns(\n        "crack_primary_inputs"',
    ],
    "inputs_page.py": [
        'specialized_widget_rail_columns(\n        "inputs_reinforcement_inputs"',
        'specialized_widget_rail_columns(\n            "inputs_lower_serviceability_inputs"',
    ],
}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    helper_source = _read("widgets_helpers.py")
    helper_requirements = [
        "def render_specialized_widget_rail(",
        "def specialized_widget_rail_columns(",
        'visible_columns: int = 3',
        "REO_DIAMETER_LABEL",
        'SHEAR_LINK_DIAMETER_LABEL = f"Link {REO_DIAMETER_LABEL}"',
        "overflow-x: auto !important;",
        "overflow-y: hidden;",
        "width_pct = max(100.0, (count / visible) * 100.0)",
        "REO_DIAMETER_LABEL,\n        dia_key,",
    ]
    missing_helper = [item for item in helper_requirements if item not in helper_source]
    if missing_helper:
        print("SPECIALIZED_WIDGET_RAIL usage FAIL")
        print("Missing helper requirements:")
        for item in missing_helper:
            print(f"- {item}")
        return 1

    missing_usages: list[str] = []
    for rel_path, expected_items in EXPECTED_USAGES.items():
        source = _read(rel_path)
        for item in expected_items:
            if item not in source:
                missing_usages.append(f"{rel_path}: {item}")

    inputs_source = _read("inputs_page.py")
    reinforcement_start = inputs_source.find("# 2. REINFORCEMENT SECTIONS")
    reinforcement_end = inputs_source.find("# 3.", reinforcement_start)
    reinforcement_block = (
        inputs_source[reinforcement_start:reinforcement_end]
        if reinforcement_start >= 0 and reinforcement_end > reinforcement_start
        else ""
    )
    contract_checks = {
        "inputs_reinforcement_uses_shared_rail": 'specialized_widget_rail_columns(\n        "inputs_reinforcement_inputs"' in reinforcement_block,
        "inputs_bottom_reo_uses_shared_renderer": 'render_longitudinal_reo_rows(\n            page_prefix="inputs",\n            section="bot"' in reinforcement_block,
        "inputs_top_reo_uses_shared_renderer": 'render_longitudinal_reo_rows(\n            page_prefix="inputs",\n            section="top"' in reinforcement_block,
        "inputs_shear_uses_shared_link_label": "SHEAR_LINK_DIAMETER_LABEL" in reinforcement_block,
        "inputs_shear_widget_keys_unchanged": all(
            item in reinforcement_block
            for item in (
                'w_lig_d = get_widget_key_for_shared("lig_d", prefix="inputs_") or "inputs_lig_d"',
                'w_lig_legs = get_widget_key_for_shared("lig_legs", prefix="inputs_") or "inputs_lig_legs"',
                'w_s_lig = get_widget_key_for_shared("s_lig", prefix="inputs_") or "inputs_s_lig"',
            )
        ),
        "inputs_reinforcement_block_has_no_mojibake": not any(
            marker in reinforcement_block for marker in MOJIBAKE_MARKERS
        ),
        "shared_rail_css_has_no_font_override": "font-family" not in helper_source[
            helper_source.find("def _specialized_widget_rail_container(") : helper_source.find("with st.container(key=outer_key)")
        ],
    }
    failed_contract_checks = [name for name, passed in contract_checks.items() if not passed]

    if missing_usages or failed_contract_checks:
        print("SPECIALIZED_WIDGET_RAIL usage FAIL")
        if missing_usages:
            print("Missing page usages:")
        for item in missing_usages:
            print(f"- {item}")
        if failed_contract_checks:
            print("Failed contract checks:")
        for item in failed_contract_checks:
            print(f"- {item}")
        return 1

    print("SPECIALIZED_WIDGET_RAIL usage PASS")
    print("Shared three-visible-column rail is used by bending, shear, deflection, crack, and Inputs widget groups.")
    print("Inputs reinforcement widgets use shared reo renderers, shared shear diameter label, and unchanged widget keys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
