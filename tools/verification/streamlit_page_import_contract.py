from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPECTED_PAGE_APIS = {
    "bending_page": ("render_bending", "compute_bending_results", "build_bending_report"),
    "shear_page": ("render_shear", "compute_shear_results"),
    "crack_page": ("render_crack_page", "render_crack_control", "render_crack"),
    "creep": ("render_creep", "compute_creep_results"),
    "deflection": ("render_deflection", "calc_deflection_as3600", "calc_span_depth_limit"),
    "design_guide_page": ("render_final_panel", "render_debug_sidebar"),
    "inputs_page": ("render_inputs_landing_card", "inputs_has_design_actions_or_loads"),
    "sfd_bmd_page": ("render_sfd_bmd_page", "diagram_cache_fingerprint"),
    "shrinkage": ("render_shrinkage", "compute_shrinkage_results"),
}


def test_page_modules_import_and_expose_expected_apis() -> None:
    for module_name, api_names in EXPECTED_PAGE_APIS.items():
        module = importlib.import_module(module_name)
        for api_name in api_names:
            assert callable(getattr(module, api_name, None)), f"{module_name}.{api_name}"


def test_representative_pure_page_helpers() -> None:
    deflection = importlib.import_module("deflection")
    assert deflection._normalize_deflection_support_type("Fixed-Fixed") == "Fixed-ended"
    assert deflection._normalize_deflection_support_type("fixed_fixed") == "Simply supported"
    assert str(deflection.format_L_over_delta(0, 6000)).strip()

    sfd_bmd_page = importlib.import_module("sfd_bmd_page")
    assert sfd_bmd_page._support_type_from_load_case("Cantilever") == "Cantilever"
    assert sfd_bmd_page._clamp_x_to_span(12.0, 6.0) == 6.0


def main() -> int:
    test_page_modules_import_and_expose_expected_apis()
    test_representative_pure_page_helpers()
    print("streamlit_page_import_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
