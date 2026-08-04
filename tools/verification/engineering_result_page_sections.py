"""Structural lock for extracted engineering-page section ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SECTION_ROOT = ROOT / "engineering_page_sections"

PAGES = {
    "design_page_runtime.py": {
        "main": "render_sfd_bmd_page",
        "modules": ("design_inputs.py",),
        "moved": ("_agent_debug_log", "_span_from_inputs"),
    },
    "bending_page_runtime.py": {
        "main": "render_bending",
        "modules": ("bending_diagrams.py", "bending_calculations.py"),
        "moved": ("_build_beam_3d_figure", "compute_bending_results"),
    },
    "shear_page_runtime.py": {
        "main": "render_shear",
        "modules": ("shear_visualisation.py",),
        "moved": ("_support_pair_from_resolved_support_type",),
    },
    "crack_page_runtime.py": {
        "main": "render_crack",
        "modules": ("crack_inputs.py",),
        "moved": ("_seed_from_param", "_inject_calcbox_css"),
    },
    "deflection_page_runtime.py": {
        "main": "render_deflection",
        "modules": (
            "deflection_diagrams.py",
            "deflection_support.py",
            "deflection_inputs.py",
        ),
        "moved": (
            "_deflection_diagram_reo_layers",
            "get_deflection_diagram_support_condition",
        ),
    },
}


def _top_level_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def main() -> int:
    for runtime_name, spec in PAGES.items():
        runtime_source = (ROOT / runtime_name).read_text(encoding="utf-8-sig")
        runtime_names = _top_level_names(runtime_source)
        assert spec["main"] in runtime_names, (runtime_name, "missing_coordinator")
        assert "render_timing_mark(" in runtime_source

        section_source = ""
        for module_name in spec["modules"]:
            source = (SECTION_ROOT / module_name).read_text(encoding="utf-8")
            ast.parse(source, filename=module_name)
            assert "def bind_runtime(" in source, (module_name, "missing_binding")
            assert module_name[:-3] in runtime_source, (
                runtime_name,
                "section_not_composed",
                module_name,
            )
            section_source += "\n" + source

        for moved_name in spec["moved"]:
            assert moved_name not in runtime_names, (
                runtime_name,
                "helper_still_owned_by_coordinator",
                moved_name,
            )
            assert moved_name in section_source, (
                runtime_name,
                "helper_missing_from_sections",
                moved_name,
            )

    print("engineering_result_page_sections: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
