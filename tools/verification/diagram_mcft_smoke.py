"""Smoke checks for extracted MCFT diagram builders."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shear_diagrams import (  # noqa: E402
    make_mcft_longitudinal_strain_profile_fig as legacy_make_mcft_longitudinal_strain_profile_fig,
    make_step4_longitudinal_strain_diagram as legacy_make_step4_longitudinal_strain_diagram,
    plot_shear_step4_middepth_strain_diagram as legacy_plot_shear_step4_middepth_strain_diagram,
    plot_step4_mcft_strain_diagram as legacy_plot_step4_mcft_strain_diagram,
)
from ui.diagrams.mcft_diagram import (  # noqa: E402
    make_mcft_longitudinal_strain_profile_fig,
    make_step4_longitudinal_strain_diagram,
    plot_shear_step4_middepth_strain_diagram,
    plot_step4_mcft_strain_diagram,
)


def _signature(fig) -> tuple[int, int, int]:
    return (
        len(fig.data),
        len(fig.layout.shapes or []),
        len(fig.layout.annotations or []),
    )


def _annotation_text(fig) -> list[str]:
    return [str(getattr(annotation, "text", "") or "") for annotation in fig.layout.annotations or []]


def _check_shared_profile() -> list[str]:
    kwargs = dict(eps_top_uls=-0.0008, eps_x_mcft=0.00055, eps_bot_uls=0.0013, height=360)
    module_fig = make_mcft_longitudinal_strain_profile_fig(**kwargs)
    legacy_fig = legacy_make_mcft_longitudinal_strain_profile_fig(**kwargs)
    failures: list[str] = []
    annotations = _annotation_text(module_fig)
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("profile_legacy_signature_changed")
    for expected in ("mid-depth", "Indicative strain trend"):
        if not any(expected in text for text in annotations):
            failures.append(f"profile_annotation_missing_{expected.replace(' ', '_')}")
    if int(module_fig.layout.height or 0) != 360:
        failures.append("profile_height_not_preserved")
    if module_fig.layout.xaxis.visible is not False:
        failures.append("profile_x_axis_visible")
    if module_fig.layout.yaxis.visible is not False:
        failures.append("profile_y_axis_visible")
    return failures


def _check_force_resolution() -> list[str]:
    kwargs = dict(
        eps_top_uls=-0.001,
        eps_x_mcft=0.0007,
        eps_bot_uls=0.0014,
        height=360,
        force_resolution=True,
        force_section_D_mm=750.0,
        force_section_c_mm=180.0,
        force_section_gamma=0.85,
        force_tension_steel_y_from_top_mm=690.0,
        force_moment_sign="positive",
        force_theta_deg=32.0,
    )
    module_fig = make_mcft_longitudinal_strain_profile_fig(**kwargs)
    legacy_fig = legacy_make_mcft_longitudinal_strain_profile_fig(**kwargs)
    failures: list[str] = []
    annotations = _annotation_text(module_fig)
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("force_legacy_signature_changed")
    for expected in ("Section actions", "Internal force resolution"):
        if not any(expected in text for text in annotations):
            failures.append(f"force_annotation_missing_{expected.replace(' ', '_')}")
    if int(module_fig.layout.height or 0) != 360:
        failures.append("force_height_not_preserved")
    return failures


def _check_middepth_diagram() -> list[str]:
    kwargs = dict(b_mm=450.0, D_mm=750.0, eps_x=0.0006)
    module_fig = plot_shear_step4_middepth_strain_diagram(**kwargs)
    legacy_fig = legacy_plot_shear_step4_middepth_strain_diagram(**kwargs)
    failures: list[str] = []
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("middepth_legacy_signature_changed")
    if not any("MCFT" in text or "varepsilon" in text for text in _annotation_text(module_fig)):
        failures.append("middepth_annotation_missing")
    if int(module_fig.layout.height or 0) != 420:
        failures.append("middepth_height_not_preserved")
    return failures


def _check_step4_profiles() -> list[str]:
    common = dict(D_mm=750.0, eps_mid=0.0007, eps_top=-0.0003, eps_bot=0.0016)
    module_fig = plot_step4_mcft_strain_diagram(**common)
    legacy_fig = legacy_plot_step4_mcft_strain_diagram(**common)
    detailed_kwargs = dict(D_mm=750.0, eps_x=0.0007, eps_top=-0.0003, eps_bot=0.0016, height_px=500)
    module_detailed = make_step4_longitudinal_strain_diagram(**detailed_kwargs)
    legacy_detailed = legacy_make_step4_longitudinal_strain_diagram(**detailed_kwargs)
    failures: list[str] = []
    if _signature(module_fig) != _signature(legacy_fig):
        failures.append("step4_legacy_signature_changed")
    if _signature(module_detailed) != _signature(legacy_detailed):
        failures.append("step4_detailed_legacy_signature_changed")
    if int(module_fig.layout.height or 0) != 420:
        failures.append("step4_height_not_preserved")
    if int(module_detailed.layout.height or 0) != 500:
        failures.append("step4_detailed_height_not_preserved")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_shared_profile())
    failures.extend(_check_force_resolution())
    failures.extend(_check_middepth_diagram())
    failures.extend(_check_step4_profiles())

    if failures:
        print("DIAGRAM_MCFT_SMOKE FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("DIAGRAM_MCFT_SMOKE PASS")
    print("- MCFT profile and force-resolution builders verified")
    print("- Step 4 mid-depth and longitudinal strain wrappers verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
