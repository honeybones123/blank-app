import math
import os
import pandas as pd
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,
    get_widget_key_for_shared,
)
from shear_diagrams import (
    plot_shear_torsion_section_2d,
    plot_shear_step1_theta_cracks_3d,
    plot_shear_step3_section_params_plotly,
    make_mcft_longitudinal_strain_profile_fig,
)
from shear_core import derive_eps_top_bot_for_step4_diagram
from torsion_diagrams import plot_torsion_prism_3d

# Shared helpers (same contract as Inputs/Bending)
from widgets_helpers import apply_global_widget_css, apply_calcbox_css, number_row, select_row, calcbox, clickable_calcbox, render_step, apply_step_summary_expander_css, info_i_button, page_divider
from step_ui import init_step_ui_state, render_expandable_step
from ui_seamless_steps import render_clickable_summary_table, bind_summary_clicks


def _coalesce_num(v, default: float) -> float:
    """Return default only if v is None (preserves 0)."""
    return default if v is None else float(v)


# ------------------------------------------------------------
#  Helper functions for diagrams
# ------------------------------------------------------------

def _safe_float(x, fallback):
    try:
        v = float(x)
        if v != v:  # NaN
            return float(fallback)
        return v
    except Exception:
        return float(fallback)


def build_reo_circles_from_state(b_mm: float, D_mm: float):
    """
    Returns list of circles for reo overlay:
      [{"x":..,"y":..,"r":..}, ...]
    If your key names differ, just map them here.
    """
    b = float(b_mm)
    D = float(D_mm)

    # --- CHANGE THESE KEY NAMES to match yours ---
    n_bot  = int(_safe_float(get_param("nb_bot"), 4))
    db_bot = _safe_float(get_param("db_bot"), 20.0)  # mm

    n_top  = int(_safe_float(get_param("nb_top"), 2))
    db_top = _safe_float(get_param("db_top"), 16.0)  # mm

    cover_bot = _safe_float(get_param("cover_bot"), 40.0)   # mm
    cover_top = _safe_float(get_param("cover_top"), 40.0)   # mm
    stirrup_db = _safe_float(get_param("lig_d"), 10.0)  # mm

    # Simple inside-face bar layout (teaching overlay)
    # centres at cover + stirrup + bar/2
    r_bot = db_bot / 2.0
    r_top = db_top / 2.0

    x_min_bot = cover_bot + stirrup_db + r_bot
    x_max_bot = b - (cover_bot + stirrup_db + r_bot)
    y_bot = cover_bot + stirrup_db + r_bot

    x_min_top = cover_top + stirrup_db + r_top
    x_max_top = b - (cover_top + stirrup_db + r_top)
    y_top = D - (cover_top + stirrup_db + r_top)

    circles = []

    # bottom row
    if n_bot <= 1:
        circles.append({"x": b/2, "y": y_bot, "r": r_bot})
    else:
        xs = [x_min_bot + i*(x_max_bot - x_min_bot)/(n_bot - 1) for i in range(n_bot)]
        circles += [{"x": x, "y": y_bot, "r": r_bot} for x in xs]

    # top row
    if n_top <= 1:
        circles.append({"x": b/2, "y": y_top, "r": r_top})
    else:
        xs = [x_min_top + i*(x_max_top - x_min_top)/(n_top - 1) for i in range(n_top)]
        circles += [{"x": x, "y": y_top, "r": r_top} for x in xs]

    return circles


# ------------------------------------------------------------
#  Shear diagrams – always-on right-hand side per step
# ------------------------------------------------------------

STEP_DIAGRAMS = {
    1: ("shear_step1_torsion_crack.png", "Step 1 – shear + torsion cracking region"),
    2: ("shear_step2_dv_critical_section.png", "Step 2 – critical section at $d_v$"),
    3: ("shear_step3_Veq_shear_demand.png", "Step 3 – equivalent shear $V_{eq}^*$"),
    4: ("shear_step4_epsx.png", "Step 4 – longitudinal strain $\\varepsilon_x$"),
    5: ("shear_step5_kv_theta.png", "Step 5 – $k_v$ and $\\theta_v$"),
    6: ("shear_step6_Vuc_Vus.png", "Step 6 – $V_{uc}$ and $V_s$"),
    7: ("shear_step7_Vumax.png", "Step 9 – web-crushing limit $V_{u,\\max}$"),
    8: ("shear_step8_lig_spacing.png", "Step 8 – ligature spacing and detailing"),
}


def _safe_step_diagram(step_no: int):
    """Always show the diagram for a step on the right; fail gracefully if missing."""
    fname, caption = STEP_DIAGRAMS.get(step_no, (None, None))
    if not fname:
        return
    path = os.path.join("assets", fname)
    
    # Special handling for Step 5: two-column layout with theta.png on the right
    if step_no == 5:
        col_left, col_right = st.columns([1, 1])
        with col_left:
            if os.path.exists(path):
                st.image(path, caption=caption, use_container_width=True)
            else:
                st.info(f"💡 Add diagram for Step {step_no} at `{path}`.")
        with col_right:
            theta_path = os.path.join("assets", "theta.png")
            if os.path.exists(theta_path):
                st.image(theta_path, caption="Strut angle $\\theta_v$", use_container_width=True)
            else:
                st.info(f"💡 Add theta diagram at `{theta_path}`.")
        return
    
    # Special handling for Step 9 (step_no == 7 in dict): stack two images vertically
    if step_no == 7:  # This is Step 9 in the display
        if os.path.exists(path):
            st.image(path, caption=caption, use_container_width=True)
        else:
            st.info(f"💡 Add diagram for Step 9 at `{path}`.")
        # Add second image below
        vumax2_path = os.path.join("assets", "shear_step7_Vumax2.png")
        if os.path.exists(vumax2_path):
            st.image(vumax2_path, caption="Strut-and-tie / concrete compression strut behaviour in deep beams", use_container_width=True)
        else:
            st.info(f"💡 Add Step 9 second diagram at `{vumax2_path}`.")
        return
    
    # Default: single image
    if os.path.exists(path):
        st.image(path, caption=caption, use_container_width=True)
    else:
        st.info(f"💡 Add diagram for Step {step_no} at `{path}`.")


# ------------------------------------------------------------
#  Shear theory insights – one toggle per step
# ------------------------------------------------------------

def render_shear_step_insight(step_no: int):
    """Render the theory/insight text for a given shear step inside an expander."""
    if step_no == 1:
        st.markdown("### Check 1 – Shear + torsion cracking region")
        st.markdown(
            r"""
**Why we convert torsion into equivalent shear**



- Torsion produces **diagonal tension** in the beam web, similar to shear-induced diagonal cracking.  

- Treating torsion as an **equivalent shear demand** is conservative and avoids separate iterative torsion-shear coupling.  

- Using an equivalent shear $V_{eq}^*$ means:

  - We track a **single internal force state** through all MCFT steps.  

  - Longitudinal strain $\varepsilon_x$ reflects the combined effect of **shear + torsion + axial**.  

  - We don't under-predict crack width or concrete shear strength.



This step sets up a **consistent load model** that will be used for all subsequent MCFT-based checks.

"""
        )

    elif step_no == 2:
        st.markdown("### Check 2 – Critical section at $d_v$")
        st.markdown(
            r"""
**Why shear is checked at $d_v$**



- Tests show that **peak diagonal cracking** and shear demand occur at about **one effective depth $d_v$** from the support.  

- Around this section:

  - Flexural cracks rotate into steeper **diagonal shear cracks**.  

  - **Aggregate interlock** begins to reduce.  

  - **Concrete compression struts** form between the load and support.  

- AS 3600 takes the design shear at a distance **$d_v$ from the face of the support** and ignores distributed loads between the support and that section.  

- If significant point loads fall within this zone, behaviour is closer to a **deep beam / strut-and-tie** region.



This step identifies **where** to apply the MCFT shear model in the member.

"""
        )

    elif step_no == 3:
        st.markdown("### Check 3 – Equivalent shear $V_{eq}^*$")
        st.markdown(
            r"""
**Why we use $V_{eq}^*$ instead of $V^*$**



- MCFT relies on a **single set of internal forces** to define the strain state.  

- Shear, torsion and axial load all influence the **longitudinal strain $\varepsilon_x$**.  

- Converting to an equivalent shear $V_{eq}^*$ helps to:

  - Keep the strain-based model **simple and conservative**.  

  - Avoid under-estimating crack width and over-estimating concrete shear strength.  

  - Line up with the **CSA 2004 approach** which AS 3600 follows for shear.



This step ensures that all later calculations (εₓ, $k_v$, $\theta_v$, $V_{uc}$, $V_s$) are based on a **consistent combined shear demand**.

"""
        )

    elif step_no == 4:
        st.markdown("### Check 4 – Longitudinal strain $\varepsilon_x$")
        st.markdown(
            r"""
**Why $\varepsilon_x$ controls concrete shear strength**



- In MCFT, **crack width** is tied directly to longitudinal strain and crack spacing:  



  $$w \approx 0.2\ \text{mm} + 1000\,\varepsilon_x$$  



- As $\varepsilon_x$ increases:

  - Crack widths **grow**,  

  - **Aggregate interlock** reduces,  

  - Diagonal **compression struts flatten**,  

  - More shear is forced into **stirrups**.  



- AS 3600 uses two closed-form strain equations:

  - **Equation (1)** – mid-depth in **tension** ($\varepsilon_x \ge 0$)  

  - **Equation (2)** – mid-depth in **slight compression** ($\varepsilon_x < 0$)  



- The selected strain is then **bounded**:  



  $$-2.0\times 10^{-4} \le \varepsilon_x \le 3.0\times 10^{-3}$$  



This step is the **core of the MCFT approach**:  

$\varepsilon_x \rightarrow$ crack width $\rightarrow k_v \rightarrow V_{uc} \rightarrow \theta_v \rightarrow V_s$.

"""
        )

    elif step_no == 5:
        st.markdown("### Check 5 – $k_v$ and $\theta_v$")
        st.markdown(
            r"""
**What $k_v$ represents**



- $k_v$ is a **concrete shear-transfer efficiency factor** in MCFT.  

- It collects the effects of:

  - Residual concrete shear across cracks,  

  - **Aggregate interlock**,  

  - **Dowel action** from longitudinal bars,  

  - Friction along the crack faces.  



- For members with at least minimum shear reinforcement:  



  $$k_v = \frac{0.4}{1 + 1500\varepsilon_x}$$  



- For members with **less than minimum shear reinforcement**, extra modifiers account for **member depth and crack spacing**.



As $\varepsilon_x$ increases, cracks widen and **$k_v$ drops**, reducing the concrete contribution $V_{uc}$.



**What $\theta_v$ represents**



- $\theta_v$ is the **angle of the diagonal compression strut** in the web.  

- AS 3600 uses:



  $$\theta_v = 29^\circ + 7000\varepsilon_x$$  



  with limits of **15° to 50°**.  



- Higher $\varepsilon_x$ → flatter stress field → **larger $\theta_v$**.  

- $\theta_v$ affects both:

  - Concrete contribution $V_{uc}$, and  

  - Steel contribution $V_s$ (via $\cot\theta_v$).



This step converts the strain state into the **geometry and efficiency** of the shear-resisting stress field.

"""
        )

    elif step_no == 6:
        st.markdown("### Check 6 – Concrete shear $V_{uc}$ and steel shear $V_s$")
        st.markdown(
            r"""
**Concrete contribution $V_{uc}$**



- MCFT gives the concrete shear contribution at the critical section as:



  $$V_{uc} = k_v\, b_v\, d_v\, \sqrt{f'_c}$$  



- $V_{uc}$ reduces when:

  - Longitudinal strain $\varepsilon_x$ increases (cracks widen),  

  - Effective shear depth $d_v$ increases,  

  - Effective crack spacing increases,  

  - Aggregate interlock and dowel action become less effective.



**Steel contribution $V_s$**



- Stirrups cross the **inclined crack length**:



  $$\ell_{cr} \approx d_v \cot\theta_v$$  



- Number of stirrup legs crossing the crack within spacing $s$:



  $$n = \frac{d_v \cot\theta_v}{s}$$  



- The shear resisted by stirrups is:



  $$V_s = V_{us} = \frac{A_{sv} f_{sy,v} d_v}{s}\cot\theta_v$$  



- Shear reinforcement:

  - Increases **ultimate shear capacity**,  

  - Provides **ductility and warning**,  

  - Helps **control crack widths**.



This step combines $V_{uc}$ and $V_s$ to give the **total shear resistance** at the critical section.

"""
        )

    elif step_no == 7:
        st.markdown("### Check 9 – Web-crushing limit $V_{u,\\max}$")
        st.markdown(
            r"""
**Why $V_{u,\\max}$ is needed**



- Even with a lot of shear reinforcement, the **concrete web** can only carry a finite **compression strut force**.  

- Once the diagonal concrete strut reaches its **crushing limit**, the failure is **sudden and brittle**.  



- AS 3600 caps the design shear by a web-crushing limit of the form:



  $$V_{u,\\max} = 0.55\, b_v\, d_v\, \sqrt{f'_c}\,(\cot\theta_v + \cot\alpha_v)$$  



  with **$\alpha_v = 90^\circ$** for vertical stirrups.



- If the applied shear demand $V_u^*$ approaches or exceeds $V_{u,\\max}$:

  - Increasing stirrup area **no longer increases capacity**,  

  - Modifying the **geometry** (web thickness, depth, load position) becomes necessary.



This step ensures the design remains within the **concrete web strength** envelope, not just the stirrup capacity.

"""
        )

    elif step_no == 8:
        st.markdown("### Check 8 – Ligature spacing and detailing")
        st.markdown(
            r"""
**Why ligature spacing rules exist**



- Shear demand **varies along the beam**, but cracks localise around the **peak shear region**.  

- If shear reinforcement is not distributed carefully, there can be a **local "weak zone"** where $A_{sv}/s$ is not enough.  



- AS 3600 Cl. 8.2.5.1 assumes:

  - The **required** shear reinforcement ratio $A_{sv}/s$ varies **linearly** over a segment.  

  - The **provided** reinforcement must stay **on or above** that required line.  



- Figure C8.2.5.1 shows recommended detailing arrangements to avoid under-reinforced pockets.



This step checks that the **physical layout of the ligatures** matches the required shear resistance along the span.

"""
        )


# ------------------------------------------------------------
#  Small helpers
# ------------------------------------------------------------
def cot(rad: float) -> float:
    """Cotangent with protection against tan(pi/2) etc."""
    return 1.0 / math.tan(rad)


def _fmt(val, decimals=1):
    """Safe number formatter for text in calc boxes."""
    try:
        if val is None:
            return "—"
        return f"{float(val):.{decimals}f}"
    except Exception:
        return "—"


# _inject_calcbox_css() removed - use apply_calcbox_css() from widgets_helpers instead




# ------------------------------------------------------------
#  SHEAR – DRAWINGS + INSIGHT BLOCKS
# ------------------------------------------------------------

def _safe_image(path: str, caption: str | None = None, width: int | None = None, use_container_width: bool | None = None):
    """Tiny helper so missing images don't break the app."""
    if os.path.exists(path):
        if width is not None:
            st.image(path, caption=caption, width=width)
        elif use_container_width is not None:
            st.image(path, caption=caption, use_container_width=use_container_width)
        else:
            st.image(path, caption=caption, use_container_width=True)
    else:
        st.info(f"💡 Add image file at `{path}` for: {caption or 'shear illustration'}")


def render_shear_intro_block():
    """
    Concept of shear + dv location.
    Diagram on the right, theory in an ℹ️ popover attached to the diagram.
    """
    st.markdown("### Shear action and the critical dv section")

    # Centered diagram taking up most of the width
    col_left, col_center, col_right = st.columns([1, 6, 1])

    with col_center:
        img_col, info_col = st.columns([10, 1])

        # Diagram
        with img_col:
            _safe_image(
                "assets/shear_flexural_cracks_dv.png",
                caption="Shear cracks forming around the dv section.",
            )

        # Info button attached to the diagram
        with info_col:
            with info_i_button(use_container_width=True):
                calcbox(
                    r"""
**What is shear in a beam?**



- Shear forces act **perpendicular to the beam axis**.  

- You can picture shear as a stack of playing cards where layers **try to slide** past each other.  

- In a beam, one part of the cross-section wants to slide relative to the next, creating **internal shear stresses**.



**Critical section for shear – dv**



- The design shear check is taken at a distance **dv from the face of the support**.  

- At this section we take the **design shear $V^*$**, ignoring any distributed load between the support and dv.  

- If significant concentrated loads fall inside this region, the behaviour is closer to a **strut-and-tie / deep beam** and a STM model is required.  

- AS 3600 defines **effective shear depth**



  $$d_v = \max\left(0.72D,\; 0.9d_0\right)$$



  where $d_0$ is the depth to the centroid of the **tension reinforcement** in the tensile zone.

"""
                )


def render_shear_behaviour_block():
    """
    Flexural vs deep-beam behaviour and shear transfer before/after cracking.
    Diagram on the right, all theory in an ℹ️ popover attached to it.
    """
    st.markdown("### Flexural shear vs deep-beam behaviour")

    # Centered diagram taking up most of the width
    col_left, col_center, col_right = st.columns([1, 6, 1])

    with col_center:
        img_col, info_col = st.columns([10, 1])

        # Diagram
        with img_col:
            _safe_image(
                "assets/shear_deep_vs_flexural.png",
                caption="Deep-beam (load close to support) vs flexural shear region.",
            )

        # Info button with BOTH behaviour + transfer explanation
        with info_col:
            with info_i_button(use_container_width=True):
                st.markdown("#### Flexural vs deep-beam behaviour")
                calcbox(
                    r"""
**Deep-beam behaviour**



- Occurs when the **clear span-to-depth ratio is small** and loads act **within about dv of the support**.  

- Load is carried mainly by **direct compression struts** rather than classic flexural action.  

- Typical examples: **brackets, corbels, short-span webs**.  

- Shear resistance is dominated by **concrete compression struts**, with failure as **web crushing** of these struts.



**Flexural shear behaviour**



- Governs when loads act **further than dv** from the support.  

- Flexural cracks form first; with increasing load they **rotate into diagonal shear cracks** near the dv section.  

- As diagonal cracks widen, **aggregate interlock reduces**, so concrete carries less shear and failure is **brittle**, local to the critical section.

"""
                )

                st.markdown("#### How shear is transferred – before and after cracking")

                col1, col2 = st.columns(2)

                with col1:
                    calcbox(
                        r"""
**Before cracking**



- In the **uncracked** region, shear is carried by the **tensile and compressive strength of uncracked concrete**.  

- Shear stress is distributed across the depth; the concrete alone provides **shear stiffness**.

"""
                    )

                with col2:
                    calcbox(
                        r"""
**After cracking**



Once flexural and diagonal cracks form:



- Shear is transferred by:  

  - **Compression in the concrete compression zone** ($V_{cc}$)  

  - **Residual concrete shear stress** across cracks ($V_{cr}$)  

  - **Aggregate interlock and friction** along crack faces ($V_{ca}$)  

  - **Dowel action** of longitudinal reinforcement ($V_d$)  

- Transverse steel **stitches the cracked section together**, improves aggregate interlock and adds a direct **steel shear component**.

"""
                    )


def render_shear_mcft_block():
    """
    High-level MCFT / Vuc / kv insight, linked to eps_x.
    Diagram on the right, theory in an ℹ️ popover attached to it.
    """
    st.markdown("### MCFT concrete shear strength – role of εₓ and k_v")

    # Centered diagram taking up most of the width
    col_left, col_center, col_right = st.columns([1, 6, 1])

    with col_center:
        img_col, info_col = st.columns([10, 1])

        # Diagram
        with img_col:
            _safe_image(
                "assets/shear_mcft_principal_struts.png",
                caption="Principal compression struts and diagonal cracking in MCFT.",
            )

        # Info button
        with info_col:
            with info_i_button(use_container_width=True):
                calcbox(
                    r"""
**Concrete contribution $V_{uc}$ in AS 3600**



- In the **Simplified Modified Compression Field Theory (SMCFT)** used by AS 3600,  

  concrete shear strength at the critical section is written as  



  $$V_{uc} = k_v\, b_v\, d_v\, \sqrt{f'_c}$$



- The factor **$k_v$** captures how shear is transferred across **cracked concrete**, combining:  

  - direct concrete shear,  

  - **aggregate interlock**, and  

  - **dowel action** from longitudinal bars.



**Influence of longitudinal strain εₓ**



- The mid-depth longitudinal strain **εₓ** is derived from internal forces (moment, shear, torsion, axial, prestress).  

- As **εₓ increases**, cracks widen and aggregate interlock reduces → **$k_v$ decreases** and the concrete contribution **$V_{uc}$ drops**.  

- Higher εₓ flattens the compression struts (smaller $\theta_v$), increases longitudinal tension forces and raises concrete web compression.

"""
                )

                calcbox(
                    r"""
**Deriving $k_v$ from crack width**



- SMCFT relates **crack width w** to strain and spacing as  



  $$w \approx 0.2\ \text{mm} + 1000\,\varepsilon_x$$



- The constant 0.2 mm represents the **initial crack width** at very small strains.  

- The second term $1000\,\varepsilon_x$ captures **additional widening** as tensile strain grows.  

- This $w$–$\varepsilon_x$ relationship feeds directly into **$k_v$**:  

  - With **minimum or greater shear reinforcement**, a simple form  



    $$k_v = \frac{0.4}{1 + 1500\,\varepsilon_x}$$  



    is used.  

  - With **less than minimum shear reinforcement**, an extra size and spacing factor  



    $$\frac{1300}{1000 + k_{dg} d_v}$$  



    adjusts $k_v$ for effective crack spacing and member depth.

"""
                )


def render_shear_steel_and_spacing_block():
    """
    Ligature spacing / detailing only.
    Steel contribution V_s is now covered in the main Step 7 calc box.
    """
    st.markdown("### Ligature spacing and detailing along the span")

    # Centered diagram taking up most of the width
    col_left, col_center, col_right = st.columns([1, 6, 1])

    with col_center:
        _safe_image(
            "assets/shear_lig_spacing_code_diagram.png",
            caption="Example of varying Asv/s along the span (AS 3600 Fig. C8.2.5.1).",
        )

    # Spacing theory in toggle below
    with st.expander(
        "Show ligature spacing and detailing explanation", expanded=False
    ):
        calcbox(
                r"""
**Ligature spacing (AS 3600 Cl. 8.2.5.1)**





- Where the required shear reinforcement **$A_{sv}/s$ varies** along the member, the code assumes a **linear variation** over each segment.  



- Detailing should follow the **recommended patterns** (e.g. Figure C8.2.5.1), so that provided $A_{sv}/s$ ≥ required $A_{sv}/s$ in the **critical region**.  



- Proper spacing is essential because shear failure due to **yielding of ligatures** tends to occur in a **localized zone** near peak shear.  



- The goal is to avoid "gaps" in shear resistance where the **provided envelope drops below the required line**.



"""
            )


# ------------------------------------------------------------
#  COMPUTE FUNCTION (no UI rendering)
# ------------------------------------------------------------
def compute_shear_results(publish: bool = True) -> dict:
    """
    Compute shear results without UI rendering.
    
    Args:
        publish: If True, publish to results dict for report export.
    
    Returns:
        dict with computed results
    """
    from state_and_helpers import recalc_derived_values
    from shear_core import ShearInputs, run_shear_calc
    
    recalc_derived_values()
    
    # --- Read inputs (shared state) ---
    b = get_param("b", 300.0)
    D = get_param("D", 600.0)
    d = get_param("d", 560.0)
    fc = get_param("fc", 32.0)
    fsy = get_param("fsy", 500.0)
    Ec = get_param("Ec", 30000.0)
    Es = get_param("Es", 200000.0)
    
    M_star = get_param("Mu_star", get_param("Mu_star_manual", 0.0))
    Vu_star = get_param("Vu_star", get_param("Vu_star_manual", 0.0))
    Tu_star = get_param("Tu_star", get_param("Tu_star_manual", 0.0))
    N_star = get_param("N_star", 0.0)
    P_v = get_param("P_star", 0.0)
    
    lig_d = get_param("lig_d", 10.0)
    legs = get_param("lig_legs", 2)
    s_lig = get_param("s_lig", 200.0)
    
    A_st = get_param("Ast_bot", 0.0)
    A_pt = get_param("A_pt", 0.0)
    f_po = get_param("f_po", 0.0)
    A_ct = b * D / 2.0 if b and D else 0.0
    
    d_g = get_param("shear_d_g", get_param("d_g", 20.0))
    phi = get_param("phi_shear", 0.75)
    sigma_cp = get_param("sigma_cp", 0.0) or 0.0
    
    n_ducts = get_param("n_ducts", 0.0) or 0.0
    duct_dia = get_param("duct_dia", 0.0) or 0.0
    sum_duct = n_ducts * (duct_dia ** 2) * math.pi / 4.0
    
    kd_option = get_param("k_d_option", "None (no ducts in web)")
    kd_map = {
        "None (no ducts in web)": 0.0,
        "0.5 – steel ducts, grouted": 0.5,
        "0.8 – plastic ducts, grouted": 0.8,
        "1.2 – ungrouted ducts": 1.2,
    }
    k_d = kd_map.get(kd_option, 0.0)
    
    kv_method = get_param("k_v_method", "General εₓ-based (Cl. 8.2.4.2)")
    use_general_kv = str(kv_method).startswith("General")
    
    inp = ShearInputs(
        b=b,
        D=D,
        d=d,
        fc=fc,
        fsy=fsy,
        Ec=Ec,
        Es=Es,
        M_star=M_star,
        V_star=Vu_star,
        T_star=Tu_star,
        N_star=N_star,
        P_v=P_v,
        phi=phi,
        sigma_cp=sigma_cp,
        A_st=A_st,
        A_pt=A_pt,
        f_po=f_po,
        A_ct=A_ct,
        d_g=d_g,
        lig_d=lig_d,
        legs=legs,
        s_lig=s_lig,
        use_general_kv=use_general_kv,
        sum_duct=sum_duct,
        k_d=k_d,
    )
    
    results = run_shear_calc(inp)
    
    # Derived metrics
    phi_Vu_cap = results.phi_Vu
    util = results.V_eq / phi_Vu_cap if phi_Vu_cap > 0 else float("nan")
    phi_Vu_max = phi * results.Vu_max_kN
    Vuc_util = results.V_eq / phi_Vu_max if phi_Vu_max > 0 else float("nan")
    
    # Minimum shear reinforcement + spacing checks
    Asv_over_s = results.Asv / s_lig if s_lig else 0.0
    Asv_min_over_s = 0.08 * math.sqrt(fc) * results.b_v / (results.f_syv or 1.0)
    min_shear_ok = Asv_over_s >= Asv_min_over_s
    max_spacing = min(0.75 * D, 500.0) if D else 500.0
    spacing_ok = s_lig <= max_spacing if s_lig else False
    
    # Summary for report
    summary = [
        ("Demand", f"{results.V_eq:.1f} kN"),
        ("Capacity", f"{phi_Vu_cap:.1f} kN"),
        ("Utilisation", f"{util:.2f}" if not math.isnan(util) else "—"),
        ("Outcome", "PASS" if util <= 1.0 else "FAIL"),
    ]
    
    boxes = []
    
    boxes.append({
        "id": "1",
        "title": "Actions",
        "clause": "AS 3600:2018 Cl. 2.3",
        "derivation": "<br/>".join([
            f"V* = {Vu_star:.1f} kN",
            f"T* = {Tu_star:.1f} kNm",
            f"V_eq* = {results.V_eq:.1f} kN",
        ]),
        "result": "",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "2",
        "title": "Effective section + reinforcement",
        "clause": "AS 3600:2018 Cl. 8.2.2",
        "derivation": "<br/>".join([
            f"b_v = {results.b_v:.0f} mm",
            f"d_v = {results.d_v:.0f} mm",
            f"A_sv = {results.Asv:.0f} mm²",
            f"s = {s_lig:.0f} mm",
        ]),
        "result": "",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "3",
        "title": "MCFT parameters",
        "clause": "AS 3600:2018 Cl. 8.2.4",
        "derivation": "<br/>".join([
            f"εx = {results.eps_x:.5f}",
            f"k_v = {results.k_v:.3f}",
            f"θ_v = {results.theta_v_deg:.1f}°",
        ]),
        "result": "",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "4",
        "title": "Concrete shear capacity",
        "clause": "AS 3600:2018 Cl. 8.2.4.1",
        "derivation": "<br/>".join([
            f"b_v = {results.b_v:.0f} mm",
            f"d_v = {results.d_v:.0f} mm",
            f"V_uc = {results.Vuc_kN:.1f} kN",
        ]),
        "result": f"φV_uc = {(phi * results.Vuc_kN):.1f} kN",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "5",
        "title": "Shear reinforcement contribution",
        "clause": "AS 3600:2018 Cl. 8.2.5",
        "derivation": "<br/>".join([
            f"A_sv = {results.Asv:.0f} mm²",
            f"s = {s_lig:.0f} mm",
            f"V_us = {results.Vus_kN:.1f} kN",
        ]),
        "result": f"φV_us = {(phi * results.Vus_kN):.1f} kN",
        "status": None,
        "diagram": None,
    })
    
    boxes.append({
        "id": "6",
        "title": "Total shear capacity and utilisation",
        "clause": "AS 3600:2018",
        "derivation": "<br/>".join([
            f"φV_u = {phi_Vu_cap:.1f} kN",
            f"Util = V_eq*/(φV_u) = {util:.2f}" if not math.isnan(util) else "Util = —",
        ]),
        "result": "PASS" if util <= 1.0 else "FAIL",
        "status": "pass" if util <= 1.0 else "fail",
        "diagram": None,
    })
    
    boxes.append({
        "id": "7",
        "title": "Web-crushing limit",
        "clause": "AS 3600:2018 Cl. 8.2.6",
        "derivation": "<br/>".join([
            f"V_u,max = {results.Vu_max_kN:.1f} kN",
            f"Demand = {results.LHS:.1f}",
            f"Capacity = {results.RHS:.1f}",
        ]),
        "result": "PASS" if results.web_ok else "FAIL",
        "status": "pass" if results.web_ok else "fail",
        "diagram": None,
    })
    
    boxes.append({
        "id": "8",
        "title": "Minimum shear reinforcement + spacing",
        "clause": "AS 3600:2018 Cl. 8.2.5",
        "derivation": "<br/>".join([
            f"A_sv/s = {Asv_over_s:.3f} mm²/mm",
            f"(A_sv/s)_min = {Asv_min_over_s:.3f} mm²/mm",
            f"s_max = {max_spacing:.0f} mm",
        ]),
        "result": "PASS" if (min_shear_ok and spacing_ok) else "FAIL",
        "status": "pass" if (min_shear_ok and spacing_ok) else "fail",
        "diagram": None,
    })
    
    shear_report = {
        "module_title": "Shear (ULS)",
        "summary": summary,
        "tabs": [{"tab_title": "ULS Checks", "boxes": boxes}],
    }
    
    if publish:
        update_results(
            phi_Vu_cap=phi_Vu_cap,
            Vu_utilisation=util if not math.isnan(util) else 0.0,
            Vu_max_kN=results.Vu_max_kN,
            phi_Vu_max_kN=phi_Vu_max,
            V_eq_kN=results.V_eq,
            Vuc_utilisation=Vuc_util if not math.isnan(Vuc_util) else None,
        )
        
        st.session_state.setdefault("results", {})
        st.session_state["results"]["shear_report"] = shear_report
    
    return {
        "phi_Vu_cap": phi_Vu_cap,
        "Vu_utilisation": util,
        "V_eq": results.V_eq,
        "Vuc_kN": results.Vuc_kN,
        "Vus_kN": results.Vus_kN,
        "shear_report": shear_report,
    }


# ------------------------------------------------------------
#  MAIN PAGE RENDER FUNCTION
# ------------------------------------------------------------
def render_shear():
    # Handle cross-page navigation from Inputs page
    from jump_nav import get_jump_uid
    get_jump_uid()
    
    apply_global_widget_css()
    apply_calcbox_css()
    apply_step_summary_expander_css()
    
    # Initialize step UI state (always-summary mode - no checkbox)
    init_step_ui_state("shear")

    st.title("Shear & Torsion")

    sync_callbacks = get_sync_callbacks()

    # --- Layout row: intro text (left) + dv diagram (right) ---
    col_left, col_right = st.columns([1, 1])  # 50/50 split

    with col_left:
        st.markdown(
            r"""
This page computes **ultimate shear and torsion capacity** outputs in accordance with **AS 3600:2018** using the MCFT-based shear method, and reports the governing utilisation checks.

- **Design shear capacity**  
  $ \phi V_{uc} = \phi(V_c + V_s) $, used for the governing shear strength check.

- **Concrete shear contribution (MCFT)**  
  $ V_c = k_v \cdot b_v \cdot d_v \cdot \sqrt{f'_c} $, depends on $\varepsilon_x$ and $\theta_v$.

- **Torsion and interaction (when applicable)**  
  $ V_{eq}^* = \sqrt{(V^*)^2 + V_{t,eq}^2} $, used for combined shear–torsion checks.
        """
        )

    with col_right:
        # Add a small left spacer, then image, then info button
        spacer_col, img_col, info_col = st.columns([1, 5, 1])

        with img_col:
            # Slightly right-shifted and ~10% bigger (360 → 396)
            st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
            _safe_image(
                "assets/shear_flexural_cracks_dv.png",
                caption=None,
                width=396,  # ~10% larger than original 360
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with info_col:
            # ℹ️ popover attached to the drawing
            with info_i_button(use_container_width=True):
                calcbox(
                    r"""
**What is shear in a beam?**







- Shear forces act **perpendicular to the beam axis**.  

- You can picture shear as a stack of playing cards where layers **try to slide** past each other.  

- In a beam, one part of the cross-section wants to slide relative to the next, creating **internal shear stresses**.







**Critical section for shear – $d_v$**







- The design shear check is taken at a distance **$d_v$ from the face of the support**.  

- At this section we take the **design shear $V^{\ast}$**, ignoring any distributed load between the support and $d_v$.  

- If significant concentrated loads fall inside this region, the behaviour is closer to a **strut-and-tie / deep beam** and a STM model is required.  

- AS 3600 defines effective shear depth  



  $$d_v = \max\left(0.72D,\;0.9d_0\right)$$  



  where $d_0$ is the depth to the centroid of the **tension reinforcement** in the tensile zone.

"""
                )

    # Top summary table placeholder (for clickable summary table)
    top_summary_placeholder = st.empty()

    # =====================================================
    # 1. DESIGN INPUTS (shared + local)  — SAME WIDGET CONTRACT
    # =====================================================
    st.subheader("Design Inputs")
    st.caption("Only user-controlled inputs are shown. All derived strain terms are handled internally.")

    col_geom, col_mat, col_actions = st.columns(3, gap="large")

    # ---------- 1.1 Geometry (left column) ----------
    with col_geom:
        st.header("Geometry")

        number_row(
            "Width b (mm)",
            "shear_b",
            get_param("b", 300.0),
            sync_callbacks,
            help_text="Shared with Inputs tab.",
        )
        number_row(
            "Depth D (mm)",
            "shear_D",
            get_param("D", 600.0),
            sync_callbacks,
            help_text="Overall section depth, shared with Inputs.",
        )
        number_row(
            "Span L (mm)",
            "shear_L",
            get_param("L", 3000.0),
            sync_callbacks,
            help_text="Clear span or design span for this section.",
        )

    # ---------- 1.2 Materials (middle column) ----------
    with col_mat:
        st.header("Materials")

        number_row(
            "Concrete strength f'c (MPa)",
            "shear_fc",
            get_param("fc", 40.0),
            sync_callbacks,
            help_text="Concrete compressive strength (AS 3600).",
        )
        number_row(
            "Steel yield f_sy (MPa)",
            "shear_fsy",
            get_param("fsy", 500.0),
            sync_callbacks,
            help_text="Yield stress of longitudinal & shear reinforcement.",
        )
        number_row(
            "Concrete modulus Ec (MPa)",
            "shear_Ec",
            get_param("Ec", 30000.0),
            sync_callbacks,
            help_text="Used in εₓ calc when compression develops.",
        )
        number_row(
            "Steel modulus Es (MPa)",
            "shear_Es",
            get_param("Es", 200000.0),
            sync_callbacks,
            help_text="Modulus of non-prestressed reinforcement.",
        )

    # ---------- 1.3 Design action (right column) ----------
    with col_actions:
        st.header("Design action")

        number_row(
            "Design shear V* (kN)",
            "shear_Vu_star",
            get_param("Vu_star_manual", 300.0),
            sync_callbacks,
            help_text="Factored shear at the section.",
        )
        number_row(
            "Axial force N* (kN, +tension)",
            "shear_N_star",
            get_param("N_star", 0.0),
            sync_callbacks,
            help_text="Axial force at the section (+tension, −compression).",
        )
        number_row(
            "Torsion T* (kNm)",
            "shear_Tu_star",
            get_param("Tu_star", 0.0),
            sync_callbacks,
            help_text="Factored torsion at the section.",
        )
        number_row(
            "φ – strength reduction for shear",
            "shear_phi_shear",
            get_param("phi_shear", 0.75),
            sync_callbacks,
            help_text="Strength reduction factor for shear (AS 3600).",
        )

    # ---------- Shear reinforcement section (below top row) ----------
    # Create three equal-width columns: reo (left), ducts (middle), params (right)
    reo_col, ducts_col, shear_params_col = st.columns(3, gap="large")
    
    with reo_col:
        st.subheader("Shear reinforcement")
        
        # Widget keys (resolved via TAB_KEYS)
        w_lig_d = get_widget_key_for_shared("lig_d", prefix="shear_") or "shear_lig_d"
        w_lig_legs = get_widget_key_for_shared("lig_legs", prefix="shear_") or "shear_lig_legs"
        w_s_lig = get_widget_key_for_shared("s_lig", prefix="shear_") or "shear_s_lig"
        
        # Read shared values (do NOT write shared keys)
        lig_d_val = float(st.session_state.get("lig_d", 10.0))
        lig_legs_val = float(st.session_state.get("lig_legs", 2))
        s_lig_val = float(st.session_state.get("s_lig", 200.0))
        
        # Option lists for dropdowns
        REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
        REO_COUNTS_0_12 = list(range(0, 13))  # 0..12 inclusive
        
        select_row(
            "Link Ø (mm)",
            w_lig_d,
            REO_BAR_DIAS,
            int(lig_d_val),
            sync_callbacks,
            help_text="Nominal diameter of shear links (mm).",
        )
        
        select_row(
            "No. of legs",
            w_lig_legs,
            REO_COUNTS_0_12,
            int(lig_legs_val),
            sync_callbacks,
            help_text="Number of legs per shear link.",
        )
        
        number_row(
            "Link spacing (mm)",
            w_s_lig,
            s_lig_val,
            sync_callbacks,
            help_text="Centre-to-centre spacing of shear links (mm).",
        )

    with ducts_col:
        st.subheader("Ducts & prestress voids")
        
        number_row(
            "Number of ducts crossing web",
            "shear_n_ducts",
            0.0,
            sync_callbacks,
            help_text="Number of prestressing ducts crossing the web.",
        )
        
        number_row(
            "Duct diameter (mm)",
            "shear_duct_dia",
            0.0,
            sync_callbacks,
            help_text="Diameter of each prestressing duct.",
        )
        
        # Compute sum_duct internally from the two inputs
        n_ducts = get_param("n_ducts", 0.0)
        duct_dia = get_param("duct_dia", 0.0)

        n_ducts = 0.0 if n_ducts is None else float(n_ducts)
        duct_dia = 0.0 if duct_dia is None else float(duct_dia)

        sum_duct = n_ducts * (duct_dia ** 2) * 3.14159 / 4.0
        # Store computed value in session state for use in calculations
        st.session_state["shear_sum_duct"] = sum_duct
        
        # k_d factor options (matching shared state format)
        KD_OPTIONS = [
            "None (no ducts in web)",
            "0.5 – steel ducts, grouted",
            "0.8 – plastic ducts, grouted",
            "1.2 – ungrouted ducts",
        ]
        # Mapping from option string to numeric k_d value
        KD_VALUE_MAP = {
            "None (no ducts in web)": 0.0,
            "0.5 – steel ducts, grouted": 0.5,
            "0.8 – plastic ducts, grouted": 0.8,
            "1.2 – ungrouted ducts": 1.2,
        }
        
        # Get widget key for k_d_option
        w_kd = get_widget_key_for_shared("k_d_option", prefix="shear_") or "shear_k_d_option"
        kd_option_val = get_param("k_d_option", "None (no ducts in web)")
        if kd_option_val not in KD_OPTIONS:
            kd_option_val = "None (no ducts in web)"
        
        select_row(
            "k_d factor for prestressing ducts",
            w_kd,
            KD_OPTIONS,
            kd_option_val,
            sync_callbacks,
            help_text="k_d factor for prestressing ducts (AS 3600).",
        )
        
        # Convert selected option to numeric k_d value for calculations
        kd_option_selected = st.session_state.get(w_kd, kd_option_val)
        k_d = KD_VALUE_MAP.get(kd_option_selected, 0.0)
    
    with shear_params_col:
        st.subheader("Shear section parameters")
        
        number_row(
            "Maximum aggregate size d_g (mm)",
            "shear_d_g",
            20.0,
            sync_callbacks,
            help_text="Maximum aggregate size for k_v calculation.",
        )
        
        # k_v method options
        KV_METHOD_OPTIONS = [
            "General εₓ-based (Cl. 8.2.4.2)",
            "Simplified non-prestressed (Cl. 8.2.4.3)",
        ]
        
        # Get widget key for k_v_method
        w_kv_method = get_widget_key_for_shared("k_v_method", prefix="shear_") or "shear_k_v_method"
        kv_method_val = get_param("k_v_method", "General εₓ-based (Cl. 8.2.4.2)")
        if kv_method_val not in KV_METHOD_OPTIONS:
            kv_method_val = "General εₓ-based (Cl. 8.2.4.2)"
        
        select_row(
            "k_v method",
            w_kv_method,
            KV_METHOD_OPTIONS,
            kv_method_val,
            sync_callbacks,
            help_text="Method for calculating k_v factor (AS 3600 Cl. 8.2.4.2 or 8.2.4.3).",
        )
        
        # Determine if general method is used
        method = st.session_state.get(w_kv_method, kv_method_val)
        use_general_kv = method.startswith("General")

    # --- Conceptual behaviour + shear transfer (flexural vs deep) ---
    page_divider()
    render_shear_behaviour_block()

    # -------------------------------------------------
    # Pull shared values for calculations
    # -------------------------------------------------
    b = get_param("b")
    D = get_param("D")
    d = get_param("d")

    fc = get_param("fc")
    fsy = get_param("fsy")
    Ec = get_param("Ec")
    Es = get_param("Es")

    M_star = get_param("Mu_star_manual") or 0.0
    V_star = get_param("Vu_star_manual") or 0.0
    T_star = get_param("Tu_star") or 0.0
    N_star = get_param("N_star") or 0.0
    P_v = get_param("P_star") or 0.0

    lig_d = get_param("lig_d")
    legs = get_param("lig_legs")
    s_lig = get_param("s_lig")
    
    # Get local widget values for epsilon_x calculation
    A_st = st.session_state.get("shear_A_st", float(4 * (math.pi * 20 ** 2 / 4)))
    A_pt = st.session_state.get("shear_A_pt", 0.0)
    f_po = st.session_state.get("shear_f_po", 0.0)
    A_ct = st.session_state.get("shear_A_ct", float(b * D / 2.0) if b and D else 0.0)
    d_g = get_param("shear_d_g", 20.0)
    phi = get_param("phi_shear", 0.75)  # Now synced via shared state
    sigma_cp = 0.0  # Prestress removed from UI, default to 0.0

    if not (b and D and d):
        st.error("Geometry (b, D, d) not fully defined – check Inputs / Bending tab.")
        return

    # =====================================================
    # 2. COMPUTE ALL VALUES (before tabs, so summary table can access them)
    # =====================================================
    # Read θ from shared state (read-only, no widget)
    theta_deg = float(get_param("crack_theta_deg", 45.0))

    # Calculate Step 1 values (torsion geometry)
    cover_t = 40.0  # assumed for closed stirrup centroid
    A_cp = b * D
    u_c = 2 * (b + D)
    Ao = 0.9 * A_cp

    # Closed stirrup path (reused in Step 2 & εx)
    uh = 2 * ((b - cover_t) + (D - cover_t))
    A_oh = (b - cover_t) * (D - cover_t)

    sqrt_fc = math.sqrt(fc)
    denom = 0.33 * sqrt_fc
    Tcr_Nmm = 0.33 * sqrt_fc * (A_cp ** 2) / u_c * math.sqrt(
        1 + (sigma_cp / denom if denom > 0 else 0.0)
    )
    Tcr_kNm = Tcr_Nmm / 1e6

    torsion_required_limit = 0.25 * phi * Tcr_kNm
    torsion_required = T_star > torsion_required_limit

    step1_req = ">" if torsion_required else "\\le"
    step1_text = (
        "required" if torsion_required else "not required (strength check only)"
    )
    torsion_status = "pass" if not torsion_required else "fail"
    
    # Check 2: Equivalent shear
    T_star_Nmm = T_star * 1e6
    sum_duct_step2 = st.session_state.get("shear_sum_duct", get_param("sum_duct", 0.0))
    
    if torsion_required:
        torsion_eq_N = 0.9 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
        torsion_eq_kN = torsion_eq_N / 1e3
        V_eq = math.sqrt(V_star ** 2 + torsion_eq_kN ** 2)
    else:
        torsion_eq_kN = 0.0
        V_eq = V_star
    
    # Check 3: Effective section parameters
    lig_d = lig_d or 10.0
    legs = legs or 2.0
    s = s_lig or 200.0
    
    sum_duct_widget = st.session_state.get("shear_sum_duct", None)
    if sum_duct_widget is not None:
        sum_duct = sum_duct_widget
    else:
        sum_duct = get_param("sum_duct", 0.0)
    
    Asv = legs * math.pi * lig_d ** 2 / 4.0
    f_syv = fsy
    
    b_v = b - k_d * sum_duct
    d_v = max(0.72 * D, 0.9 * d)
    
    dv_1 = 0.72 * D
    dv_2 = 0.9 * d
    
    # Check 4: Longitudinal strain εx
    M_star_Nmm = abs(M_star) * 1e6
    term_M = M_star_Nmm / (d_v or 1.0)
    
    Vprime_kN = abs(V_star) - P_v
    Vprime_N = Vprime_kN * 1e3
    
    torsion_N = 0.97 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
    sqrt_inner = math.sqrt(Vprime_N ** 2 + torsion_N ** 2)
    
    N_star_N = 0.5 * N_star * 1e3
    A_pt_fpo_N = A_pt * f_po
    
    numerator_1 = term_M + sqrt_inner + N_star_N - A_pt_fpo_N
    
    Ep = 195000.0  # tendon modulus, MPa
    denom1 = 2.0 * (Es * A_st + Ep * A_pt)
    eps_x_1 = numerator_1 / denom1 if denom1 > 0 else 0.0
    
    V_abs_N = abs(V_star) * 1e3
    numerator_2 = term_M + V_abs_N - P_v * 1e3 + N_star_N - A_pt_fpo_N
    denom2 = 2.0 * (Es * A_st + Ep * A_pt + Ec * A_ct)
    eps_x_2 = numerator_2 / denom2 if denom2 > 0 else 0.0
    
    if eps_x_1 >= 0:
        eps_x_raw = eps_x_1
        eq_used = "Equation (1) – mid-depth in tension"
    else:
        eps_x_raw = eps_x_2
        eq_used = "Equation (2) – mid-depth in slight compression"
    
    eps_x = max(-0.0002, min(eps_x_raw, 0.003))
    
    # Check 5: k_v and θ_v
    if use_general_kv:
        if fc <= 65:
            k_dg = 32.0 / (16.0 + d_g)
            k_dg = max(k_dg, 0.8)
            if d_g >= 16:
                k_dg = max(k_dg, 1.0)
        else:
            k_dg = 2.0
        
        Asv_over_s = Asv / s
        Asv_min_over_s = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)
        
        if Asv_over_s < Asv_min_over_s:
            k_v = (0.4 / (1 + 1500 * eps_x)) * (1300 / (1000 + k_dg * d_v))
            kv_case = "general MCFT with **low stirrup ratio** ($A_{sv}/s < (A_{sv}/s)_{min}$)"
        else:
            k_v = 0.4 / (1 + 1500 * eps_x)
            kv_case = "general MCFT with **adequate stirrup ratio**"
        
        theta_v_deg = 29.0 + 7000.0 * eps_x
    else:
        if Asv / s < 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0):
            k_v = min(200.0 / (1000.0 + 1.3 * d_v), 0.10)
            kv_case = "simplified non-prestressed – **low stirrup ratio**"
        else:
            k_v = 0.15
            kv_case = "simplified non-prestressed – **minimum stirrups provided**"
        theta_v_deg = 36.0
        k_dg = float("nan")
    
    theta_v_rad = math.radians(theta_v_deg)
    
    # Check 6: Concrete shear contribution
    sqrt_fc_limited = min(math.sqrt(fc), 8.0)
    Vuc_N = k_v * b_v * d_v * sqrt_fc_limited
    Vuc_kN = Vuc_N / 1e3
    
    # Check 7: Steel shear contribution
    Vus_N = (Asv * f_syv * d_v / s) * cot(theta_v_rad)
    Vus_kN = Vus_N / 1e3
    
    # Check 8: Combined shear strength
    Vu_total_kN = Vuc_kN + Vus_kN + P_v
    phi_Vu = phi * Vu_total_kN
    shear_ok = phi_Vu >= V_eq
    shear_status = "pass" if shear_ok else "fail"
    
    # Check 9: Web crushing
    theta_1_deg = 90.0
    theta_1_rad = math.radians(theta_1_deg)
    cot_theta_v = cot(theta_v_rad)
    cot_theta_1 = cot(theta_1_rad)
    
    Vu_max_N = (
        0.55
        * fc
        * b_v
        * d_v
        * (cot_theta_v + cot_theta_1)
        / (1 + cot_theta_v ** 2)
        + P_v * 1e3
    )
    Vu_max_kN = Vu_max_N / 1e3
    
    V_star_N = V_star * 1e3
    term_V = V_star_N / (b_v * d_v or 1.0)
    term_T = T_star_Nmm * uh / (1.7 * (A_oh ** 2 or 1.0))
    
    LHS = math.sqrt(term_V ** 2 + term_T ** 2)
    RHS = phi * Vu_max_N / (b_v * d_v or 1.0)
    
    web_ok = LHS <= RHS
    web_status = "pass" if web_ok else "fail"
    
    # Check 10: Minimum shear reinforcement
    Asv_over_s_check10 = Asv / s if s > 0 else 0.0
    Asv_min_over_s_check10 = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)
    min_shear_ok = Asv_over_s_check10 >= Asv_min_over_s_check10
    min_shear_status = "pass" if min_shear_ok else "fail"

    # =====================================================
    # 3. SHEAR DESIGN CHECKS UI (organized into tabs)
    # =====================================================
    page_divider()
    st.subheader("Shear design checks")
    
    apply_step_summary_expander_css()  # same pattern as bending
    
    tab1, tab2, tab3 = st.tabs([
        "Torsion + dimensions",
        "MCFT and strength checks",
        "Shear reinforcement checks",
    ])
    
    # =====================================================
    # TAB 1: Torsion + dimensions
    # =====================================================
    with tab1:
        st.caption("Torsion cracking check, equivalent shear, and effective section parameters (bv, dv).")
        
        # =====================================================
        # Check 1 — TORSION CRACKING CHECK (T_cr)
        # =====================================================
        # Check 1 converted to use render_expandable_step (always-summary mode)
        # Build calc markdown from the existing details
        check1_calc_md = f"""
*Purpose: Determine if torsion design is required by checking if $T^* > 0.25 \\phi T_{{cr}}$.*

**Inputs:**

- Section: $b = {b:.0f}$ mm, $D = {D:.0f}$ mm  
- Derived: $A_{{cp}} = bD = {A_cp:.0f}$ mm², $u_c = 2(b + D) = {u_c:.0f}$ mm  
- Concrete: $f'_c = {fc:.1f}$ MPa, $\\sigma_{{cp}} = {sigma_cp:.2f}$ MPa  
- Torsion geometry: $A_o = 0.9 A_{{cp}} = {Ao:.0f}$ mm², $u_h = {uh:.0f}$ mm  

---

**Formula (AS 3600 Cl. 8.3.4):**

$$\\large T_{{cr}} = 0.33\\sqrt{{f'_c}} \\cdot \\frac{{A_{{cp}}^2}}{{u_c}} \\cdot \\sqrt{{1 + \\frac{{\\sigma_{{cp}}}}{{0.33\\sqrt{{f'_c}}}}}}$$

**Substitution:**

$$\\large T_{{cr}} = 0.33\\sqrt{{{fc:.1f}}} \\cdot \\frac{{{A_cp:.0f}^2}}{{{u_c:.0f}}} \\cdot \\sqrt{{1 + \\frac{{{sigma_cp:.2f}}}{{0.33\\sqrt{{{fc:.1f}}}}}}} = {Tcr_kNm:,.1f}\\ \\text{{kNm}}$$

---

**Result:**

- Limit: $0.25 \\phi T_{{cr}} = 0.25 \\times {phi:.2f} \\times {Tcr_kNm:,.1f} = {torsion_required_limit:,.1f}$ kNm  
- Demand: $T^* = {T_star:.1f}$ kNm  
- Condition: $T^* {step1_req} 0.25 \\phi T_{{cr}}$  
- **Conclusion: torsion design is {step1_text}.**
"""
            
        # Diagram render function
        def check1_diagram_fn():
            L_mm = float(get_param("L", 3000.0))
            b_mm = float(get_param("b", 400.0))
            D_mm = float(get_param("D", 600.0))
            
            # Get cached or uncached version based on debug mode
            def _get_cached_step1_fig():
                """Get the cached or uncached version based on debug mode."""
                try:
                    from src.debug.cache_control import cache_enabled
                    if cache_enabled():
                        # Caching enabled: use cache
                        return st.cache_data(show_spinner=False)(_step1_fig_impl)
                    else:
                        # Cache bypass enabled: return unwrapped function
                        return _step1_fig_impl
                except ImportError:
                    # Debug module not available: use cache
                    return st.cache_data(show_spinner=False)(_step1_fig_impl)
            
            def _step1_fig_impl(L_mm, b_mm, D_mm, theta_deg):
                """Pure function for step1 figure (cached in production)."""
                return plot_shear_step1_theta_cracks_3d(
                    L_mm=L_mm, b_mm=b_mm, D_mm=D_mm, theta_deg=theta_deg,
                    n_cracks=3, start_t_min=0.10, start_t_span=0.06,
                crack_lw=4.0, show_cracks=True
                )
            
            _cached_fn = _get_cached_step1_fig()
            fig = _cached_fn(L_mm, b_mm, D_mm, theta_deg)
            st.pyplot(fig, use_container_width=True, clear_figure=True)
        
        # Info render function (popover)
        def check1_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Torsion cracking (what this check means)"):
                    st.markdown(r"""
### Torsion cracking behaviour

**What torsion cracking means**

Torsion cracking occurs when the applied torsional moment exceeds the concrete's cracking resistance, causing diagonal cracking around the section perimeter.  

Before cracking, torsion is resisted mainly by the concrete acting elastically. After cracking, resistance shifts to a **space-truss mechanism** (diagonal compression struts + transverse reinforcement).

**Why the 0.25·φ·Tcr threshold is used**

AS 3600 uses **0.25·φ·Tcr** to distinguish between:

- **uncracked torsion** (elastic concrete behaviour), and

- **cracked torsion** (truss action governs).

Below this limit, torsion does not significantly change member behaviour and detailed torsion design is not required.

**Key takeaway**

This step only decides whether torsion is **cracked** or **uncracked**.  

After this, torsion is treated as a known condition and is not re-explained.
                """)
        
        # Build summary line
        check1_summary = f"Check 1 — Torsion cracking check | Result: Torsion design is {'NOT REQUIRED' if not torsion_required else 'REQUIRED'}"
        
        # Convert status
        status_kind = "pass" if not torsion_required else "fail"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check1",
            title="Check 1 — Torsion cracking check",
            summary_md=check1_summary,
            status_kind=status_kind,
            calc_md=check1_calc_md,
            diagram_render_fn=check1_diagram_fn,
            info_render_fn=check1_info_fn,
            anchor_id="torsion_considered",
        )

        # =====================================================
        # Check 2 — CONVERT TORSION INTO AN EQUIVALENT SHEAR V_eq*
        # =====================================================
        if torsion_required:
            # --- Full equivalent shear including torsion ---
            check2_calc_md = f"""
*Purpose: Convert torsion into an equivalent shear force for combined shear + torsion design.*

**Inputs:**

- Shear demand: $V^* = {V_star:.1f}$ kN  
- Torsion: $T^* = {T_star:.1f}$ kNm  
- Torsion geometry: $u_h = {uh:.0f}$ mm, $A_o = {Ao:.0f}$ mm²  

---

**Formula (AS 3600 Cl. 8.2.3):**

$$\\large V_{{t,eq}} = 0.9 \\cdot \\frac{{T^* u_h}}{{2 A_o}}$$

$$\\large V_{{eq}}^* = \\sqrt{{(V^*)^2 + V_{{t,eq}}^2}}$$

**Substitution:**

$$\\large V_{{t,eq}} = 0.9 \\cdot \\frac{{{T_star:.1f} \\times 10^6 \\times {uh:.0f}}}{{2 \\times {Ao:.0f}}} = {torsion_eq_kN:.1f}\\ \\text{{kN}}$$

$$\\large V_{{eq}}^* = \\sqrt{{({V_star:.1f})^2 + ({torsion_eq_kN:.1f})^2}} = {V_eq:.1f}\\ \\text{{kN}}$$

---

**Result:**

- Torsion is included as an equivalent shear.  
- **$V_{{eq}}^* = {V_eq:.1f}$ kN**
"""
        else:
            # --- No torsion design: equivalent shear = shear only ---
            torsion_eq_kN = 0.0
            V_eq = V_star
            check2_calc_md = f"""
*Purpose: Convert torsion into an equivalent shear force (if required).*

**Inputs:**

- Shear demand: $V^* = {V_star:.1f}$ kN  
- Torsion: $T^* = {T_star:.1f}$ kNm (from Check 1, torsion design is not required)  

---

**Formula (AS 3600 Cl. 8.2.3):**

$$\\large V_{{eq}}^* = \\sqrt{{(V^*)^2 + V_{{t,eq}}^2}}$$

Since $V_{{t,eq}} = 0$:

$$\\large V_{{eq}}^* = V^*$$

**Substitution:**

$$\\large V_{{eq}}^* = V^* = {V_eq:.1f}\\ \\text{{kN}}$$

---

**Result:**

- Torsion is not treated as a design action.  
- **$V_{{eq}}^* = {V_eq:.1f}$ kN**
"""
            
        # Diagram render function
        def check2_diagram_fn():
            # Mode selector for diagram - now includes all three options
            diagram_mode = st.radio(
                "Stress flow mode:",
                ["V+T (Combined)", "V (Shear only)", "T (Torsion only)"],
                index=0,
                key="shear_check2_diagram_mode",
                horizontal=True,
            )
            
            # Map radio selection to mode string
            mode_map = {
                "V+T (Combined)": "V+T",
                "V (Shear only)": "V",
                "T (Torsion only)": "T"
            }
            mode_short = mode_map[diagram_mode]
            
            # Get geometry from session state
            b_mm = _safe_float(get_param("b"), 300.0)
            D_mm = _safe_float(get_param("D"), 600.0)
            
            # Build reo circles from state
            reo_circles = build_reo_circles_from_state(b_mm, D_mm)
            
            # Generate and display the shear+torsion section diagram
            fig = plot_shear_torsion_section_2d(
                b_mm=b_mm,
                D_mm=D_mm,
                mode=mode_short,
                show_labels=True,
                reo_circles=reo_circles,
                reo_alpha=0.50,
            )
            st.pyplot(fig, use_container_width=True, clear_figure=True)

        # Info render function (popover)
        def check2_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Equivalent shear (combined demand)"):
                    st.markdown(r"""
### Combined shear demand (Veq*)

**Why torsion is converted to an equivalent shear**

When the section is cracked, torsion introduces longitudinal force components that interact with shear behaviour.  

A practical way to capture this is to convert torsion into a **shear-equivalent demand**.

**Vector combination (one idea)**

The combined demand is taken as a vector sum of:

- the applied shear V*, and

- the torsion-equivalent shear component.

This reflects simultaneous actions acting through different internal force components.

**Why it is conservative**

Vector combination slightly overestimates the combined effect when one action dominates.  

This conservatism is intentional and consistent with simplified design assumptions.
                """)
        
        # Build summary line
        check2_summary = f"Check 2 — Equivalent shear $V_{{eq}}^*$ | Result: $V_{{eq}}^* = {V_eq:.1f}$ kN"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check2",
            title="Check 2 — Equivalent shear $V_{eq}^*$",
            summary_md=check2_summary,
            status_kind=None,
            calc_md=check2_calc_md,
            diagram_render_fn=check2_diagram_fn,
            info_render_fn=check2_info_fn,
            anchor_id="veq",
        )

        # =====================================================
        # Check 3 — EFFECTIVE SECTION & SHEAR REINFORCEMENT
        # =====================================================
        check3_calc_md = f"""
*Purpose: Calculate the shear-resisting section parameters $A_{{sv}}$, $b_v$ and $d_v$ for AS 3600 shear design.*

**Inputs:**

- Section geometry: $b = {_fmt(b)}$ mm, $D = {_fmt(D)}$ mm, $d = {_fmt(d)}$ mm  
- Transverse reinforcement: $d_{{lig}} = {_fmt(lig_d)}$ mm, $n_{{legs}} = {_fmt(legs, 0)}$, $s_{{lig}} = {_fmt(s)}$ mm, $f_{{sy,v}} = {_fmt(f_syv)}$ MPa  
- Ducts in web: $\\sum d_{{duct}} = {_fmt(sum_duct)}$ mm, $k_d = {_fmt(k_d)}$  
- Shear model: $k_v$ method = {method}  

---

**Formula (a) – Transverse steel area $A_{{sv}}$:**

$$\\large A_{{sv}} = n_{{legs}} \\cdot \\frac{{\\pi d_{{lig}}^2}}{{4}}$$

**Substitution:**

$$\\large A_{{sv}} = {_fmt(legs, 0)} \\cdot \\frac{{\\pi \\times {_fmt(lig_d)}^2}}{{4}} = {_fmt(Asv)}\\ \\text{{mm}}^2$$

Stirrups at spacing: $s_{{lig}} = {_fmt(s)}$ mm  

---

**Formula (b) – Effective web width $b_v$ (AS 3600 Cl. 8.2.2):**

$$\\large b_v = b - k_d \\sum d_{{duct}}$$

**Substitution:**

$$\\large b_v = {_fmt(b)} - {_fmt(k_d)} \\times {_fmt(sum_duct)} = {_fmt(b_v)}\\ \\text{{mm}}$$

---

**Formula (c) – Shear depth $d_v$ (AS 3600 Cl. 8.2.2):**

$$\\large d_v = \\max(0.72D,\\ 0.9d)$$

**Substitution:**

$0.72D = 0.72 \\times {_fmt(D)} = {_fmt(dv_1)}$ mm  

$0.9d = 0.9 \\times {_fmt(d)} = {_fmt(dv_2)}$ mm  

$$\\large d_v = {_fmt(d_v)}\\ \\text{{mm}}$$

---

**Result:**

- $A_{{sv}} = {_fmt(Asv)}$ mm² with stirrups at $s_{{lig}} = {_fmt(s)}$ mm  
- $b_v = {_fmt(b_v)}$ mm, $d_v = {_fmt(d_v)}$ mm  
"""
        
        # Diagram render function
        def check3_diagram_fn():
            # Get section geometry (from shared)
            b_mm = float(b)
            D_mm = float(D)

            # Get Check 3 computed shear parameters
            bv_mm = float(b_v)
            dv_mm = float(d_v)

            # Optional if available
            Asv_mm2 = float(Asv) if Asv else None
            s_lig_mm = float(s) if s else None

            # Get reo layout (same as bending page uses)
            from section_layout import compute_section_layout_cached
            cover_bot = _coalesce_num(get_param("cover_bot", 40.0), 40.0)
            cover_top = _coalesce_num(get_param("cover_top", 40.0), 40.0)
            cover_side = float(get_param("cover_side", min(cover_top, cover_bot)) or min(cover_top, cover_bot))
            
            nb_or_s_bot_1 = _coalesce_num(get_param("nb_or_s_bot_1", 4.0), 4.0)
            db_bot_1 = _coalesce_num(get_param("db_bot_1", 20.0), 20.0)
            nb_or_s_bot_2 = _coalesce_num(get_param("nb_or_s_bot_2", 0.0), 0.0)
            db_bot_2 = _coalesce_num(get_param("db_bot_2", 20.0), 20.0)
            nb_or_s_top_1 = _coalesce_num(get_param("nb_or_s_top_1", 2.0), 2.0)
            db_top_1 = _coalesce_num(get_param("db_top_1", 16.0), 16.0)
            nb_or_s_top_2 = _coalesce_num(get_param("nb_or_s_top_2", 0.0), 0.0)
            db_top_2 = _coalesce_num(get_param("db_top_2", 16.0), 16.0)
            rowgap_bot = _coalesce_num(get_param("rowgap_bot", 60.0), 60.0)
            rowgap_top = _coalesce_num(get_param("rowgap_top", 60.0), 60.0)
            
            layout = compute_section_layout_cached(
                b=b_mm, D=D_mm,
                cover_bot=cover_bot, cover_top=cover_top, cover_side=cover_side,
                nb_or_s_bot_1=nb_or_s_bot_1, db_bot_1=db_bot_1,
                nb_or_s_bot_2=nb_or_s_bot_2, db_bot_2=db_bot_2,
                nb_or_s_top_1=nb_or_s_top_1, db_top_1=db_top_1,
                nb_or_s_top_2=nb_or_s_top_2, db_top_2=db_top_2,
                rowgap_bot=rowgap_bot, rowgap_top=rowgap_top,
            )
            
            # Convert reo_layout to reo_shapes format (bottom=red, top=blue)
            reo_shapes = []
            reo_layout = layout.get("reo_layout", {})
            
            # Bottom bars (red)
            for layer_data in reo_layout.get("bottom", []):
                for x_pos in layer_data.get("x", []):
                    reo_shapes.append({
                        "x": float(x_pos),
                        "y": float(layer_data["y"]),
                        "r": float(layer_data["db"]) / 2.0,
                        "fill": "rgba(220, 60, 60, 0.95)",   # bottom = red
                        "line": "rgba(120, 20, 20, 1.0)",
                    })
            
            # Top bars (blue)
            for layer_data in reo_layout.get("top", []):
                for x_pos in layer_data.get("x", []):
                    reo_shapes.append({
                        "x": float(x_pos),
                        "y": float(layer_data["y"]),
                        "r": float(layer_data["db"]) / 2.0,
                        "fill": "rgba(60, 110, 220, 0.95)",  # top = blue
                        "line": "rgba(20, 50, 120, 1.0)",
                    })

            # Get ligature parameters for drawing stirrups
            lig_d_val = float(lig_d) if lig_d else None
            lig_legs_val = int(legs) if legs else None
            
            fig = plot_shear_step3_section_params_plotly(
                b_mm=b_mm,
                D_mm=D_mm,
                bv_mm=bv_mm,
                dv_mm=dv_mm,
                Asv_mm2=Asv_mm2,
                s_lig_mm=s_lig_mm,
                reo_shapes=reo_shapes,
                lig_d=lig_d_val,
                lig_legs=lig_legs_val,
                cover_bot=cover_bot,
                cover_top=cover_top,
                cover_side=cover_side,
                height=850,  # 2.5x bigger (340 * 2.5 = 850)
                label_pad=14,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Info render function (popover)
        def check3_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Effective shear geometry (bv, dv)"):
                    st.markdown(r"""
### Effective shear geometry

**bv (effective web width)**

bv is the web width available to resist shear.  

It excludes regions that do not participate effectively in shear transfer (e.g., ducts/voids).

**dv (effective shear depth)**

dv is the effective depth used for shear force transfer through the web.  

It reflects the shear force path, not just reinforcement location.

**Why dv ≠ flexural depth d**

d is defined by tension reinforcement location (flexure).  

dv is defined by shear transfer geometry (shear). They represent different mechanisms.
                """)
        
        # Build summary line
        check3_summary = f"Check 3 — Shear-resisting section ($b_v$, $d_v$, ligs) | Result: $A_{{sv}} = {_fmt(Asv)}$ mm², $b_v = {_fmt(b_v)}$ mm, $d_v = {_fmt(d_v)}$ mm"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check3",
            title="Check 3 — Shear-resisting section (b_v, d_v, ligs)",
            summary_md=check3_summary,
            status_kind=None,
            calc_md=check3_calc_md,
            diagram_render_fn=check3_diagram_fn,
            info_render_fn=check3_info_fn,
        )

    # =====================================================
    # TAB 2: MCFT and strength checks
    # =====================================================
    with tab2:
        st.caption("Longitudinal strain, MCFT parameters, concrete and steel contributions, combined capacity, and web crushing.")
        
        # High-level MCFT / Vuc / kv insight tied to εx
        render_shear_mcft_block()

        # =====================================================
        # Check 4 — LONGITUDINAL STRAIN εx
        # =====================================================
        # Build calc markdown
        eq2_note = ""
        if eps_x_1 < 0:
            eq2_note = f"""
**Since the strain from Equation (1) is negative**  
$\\varepsilon_{{x,1}} = {eps_x_1:.5f} < 0$, mid-depth is in slight compression.  
AS 3600 allows εₓ to be taken as 0 or recalculated with **Equation (2)** including the concrete stiffness term:

$$\\large \\varepsilon_{{x,2}} = \\frac{{|M^*|/d_v + |V^*| - P_v + 0.5N^* - A_{{pt}} f_{{po}}}}{{2(E_s A_{{st}} + E_p A_{{pt}} + E_c A_{{ct}})}}$$

Substituting the derived numerator and denominator:

$$\\large \\varepsilon_{{x,2}} = \\frac{{{numerator_2:,.0f}}}{{{denom2:,.0f}}} = {eps_x_2:.5f}$$
"""

        check4_calc_md = f"""
*Purpose: Calculate the longitudinal strain $\\varepsilon_x$ at mid-depth for use in the MCFT shear model.*

**Inputs:**

- Shear depth: $d_v = {_fmt(d_v)}$ mm  
- Actions: $M^* = {_fmt(M_star)}$ kNm, $V^* = {_fmt(V_star)}$ kN, $P_v = {_fmt(P_v)}$ kN, $N^* = {_fmt(N_star)}$ kN, $T^* = {_fmt(T_star)}$ kNm  
- Material stiffness: $E_s = {_fmt(Es,0)}$ MPa, $E_p = {_fmt(Ep,0)}$ MPa  
- Steel areas: $A_{{st}} = {_fmt(A_st,1)}$ mm², $A_{{pt}} = {_fmt(A_pt,1)}$ mm², $f_{{po}} = {_fmt(f_po)}$ MPa  
- Torsion geometry: $u_h = {_fmt(uh)}$ mm, $A_o = {_fmt(Ao)}$ mm²  

---

**Derivation of terms:**

*Moment term:*

$$\\large |M^*|/d_v = \\frac{{|{M_star:.1f}| \\times 10^6}}{{{d_v:.1f}}} = {term_M:,.0f}\\ \\text{{N}}$$

*Shear + torsion term:*

- $V' = |V^*| - P_v = |{V_star:.1f}| - {P_v:.1f} = {Vprime_kN:.1f}$ kN  $= {Vprime_N:,.0f}$ N  
- $0.97 T^* u_h / (2A_o) = {torsion_N:,.0f}$ N  

$$\\large \\sqrt{{V'^{{2}} + (0.97 T^* u_h / 2A_o)^2}} = \\sqrt{{{Vprime_N:,.0f}^2 + {torsion_N:,.0f}^2}} = {sqrt_inner:,.0f}\\ \\text{{N}}$$

*Axial / prestress:*

- $0.5N^* = 0.5 \\times {N_star:.1f} \\times 10^3 = {N_star_N:,.0f}$ N  
- $A_{{pt}} f_{{po}} = {A_pt:.1f} \\times {f_po:.1f} = {A_pt_fpo_N:,.0f}$ N  

---

**Formula (AS 3600 Cl. 8.2.4.2.2(1)) – mid-depth in tension (εₓ ≥ 0):**

$$\\large \\varepsilon_{{x,1}} = \\frac{{|M^*|/d_v + \\sqrt{{V'^{{2}} + (0.97 T^* u_h / 2A_o)^2}} + 0.5N^* - A_{{pt}} f_{{po}}}}{{2(E_s A_{{st}} + E_p A_{{pt}})}}$$

**Substitution:**

$$\\large \\varepsilon_{{x,1}} = \\frac{{{term_M:,.0f} + {sqrt_inner:,.0f} + {N_star_N:,.0f} - {A_pt_fpo_N:,.0f}}}{{2 \\times ({Es:,.0f} \\times {A_st:.1f} + {Ep:,.0f} \\times {A_pt:.1f})}}$$

$$\\large \\varepsilon_{{x,1}} = \\frac{{{numerator_1:,.0f}}}{{{denom1:,.0f}}} = {eps_x_1:.5f}$$

{eq2_note}

---

**Result:**

- Governing equation: **{eq_used}**  
- Raw strain: $\\varepsilon_x = {eps_x_raw:.5f}$  
- After applying AS 3600 limits $[-2.0 \\times 10^{{-4}},\\, 3.0 \\times 10^{{-3}}]$:

$$\\large \\varepsilon_x = {eps_x:.5f}$$

This value is **{"positive (tension at mid-depth)" if eps_x >= 0 else "negative (slight compression at mid-depth)"}**.
"""
            
        # Diagram render function
        def check4_diagram_fn():
            # Diagram with info popover (second info button)
            col_diag_title, col_diag_info = st.columns([1, 0.08])
            with col_diag_title:
                st.markdown("**Longitudinal strain profile**")
            with col_diag_info:
                with info_i_button(help_text="Derivation of εx (conceptual)"):
                    st.markdown(r"""
### Derivation of longitudinal strain εx

**Strain basis**

Hooke's Law links stress and strain:

\[
\varepsilon = \frac{\sigma}{E}
\]

The longitudinal strain corresponds to the average longitudinal force in the member divided by the effective longitudinal stiffness.

**Resolving internal forces**

At a cracked section under M*, V*, and N*, the tensile chord force can be expressed as:

\[
T = \frac{M^*}{d_v} + 0.5N + 0.5V\cot\theta
\]

- \(M^*/d_v\): tension force from flexure  

- \(0.5N\): axial force contribution  

- \(0.5V\cot\theta\): longitudinal component of the diagonal compression strut

**AS 3600 (CSA 2004) simplification**

CSA 2004 (adopted in AS 3600) simplifies by taking:

\[
0.5\cot\theta \approx 1.0
\]

This is conservative and removes θ-dependency so εx can be evaluated without iteration.

**Diagram placeholders**

- [Diagram A] Internal force resolution (M–V–N)  

- [Diagram B] Compression strut angle θ and longitudinal component  

- [Diagram C] Strain profile through depth (top / mid / bottom)
                    """)
            
            # Check 4 MCFT εx (AS3600 sign: +tension, -compression)
            eps_x_mcft = eps_x  # Final Check 4 result (after AS3600 limits)
            
            # Pull ULS top/bot strains from bending page session state
            eps_top_uls = None
            eps_bot_uls = None
            
            for key in ["eps_c"]:
                val = st.session_state.get(key, None)
                if val is not None:
                    try:
                        eps_top_uls = float(val)
                        break
                    except Exception:
                        pass
            
            for key in ["eps_s"]:
                val = st.session_state.get(key, None)
                if val is not None:
                    try:
                        eps_bot_uls = float(val)
                        break
                    except Exception:
                        pass
            
            if eps_top_uls is None or eps_bot_uls is None:
                try:
                    from bending_core import _stress_strain_state
                    state_dict = _stress_strain_state("ULS")
                    if eps_top_uls is None and "eps_c" in state_dict:
                        eps_top_uls = float(state_dict["eps_c"])
                    if eps_bot_uls is None and "eps_s" in state_dict:
                        eps_bot_uls = float(state_dict["eps_s"])
                except Exception:
                    pass
            
            if eps_top_uls is None or eps_bot_uls is None:
                eps_top_uls, eps_bot_uls = derive_eps_top_bot_for_step4_diagram(eps_x_mcft, delta=0.00035)
            
            eps_top_uls = float(eps_top_uls)
            eps_bot_uls = float(eps_bot_uls)
            
            fig_eps = make_mcft_longitudinal_strain_profile_fig(
                eps_top_uls=eps_top_uls,
                eps_x_mcft=eps_x_mcft,
                eps_bot_uls=eps_bot_uls,
                title="Longitudinal strain profile",
                height=840,
            )
            st.plotly_chart(fig_eps, use_container_width=True, config={"displayModeBar": False})

        # Info render function (popover)
        def check4_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Longitudinal strain εx (MCFT behaviour anchor)"):
                    st.markdown(r"""
### Longitudinal strain εx (MCFT behaviour)

**What MCFT is**

The Modified Compression Field Theory (MCFT) models shear transfer in cracked reinforced concrete using:

- diagonal compression struts,

- cracked concrete shear transfer mechanisms, and

- reinforcement interaction.

AS 3600 adopts a simplified MCFT form so key parameters can be obtained without iteration.

**Why strain governs shear behaviour**

As longitudinal strain increases, cracking and deformation increase, which changes:

- the diagonal crack angle, and

- the effectiveness of concrete in shear transfer.

**Why εx is evaluated at mid-depth**

Mid-depth is representative of the cracked web region where shear transfer is governed.  

εx here acts as a practical "behaviour indicator" for the shear model.

**Sign convention**

Compression strains are negative, tension strains are positive (consistent with bending strain convention).
                    """)

                    st.markdown(
                        r"""
### **How the app uses these equations**

1. Compute εₓ using **Equation (1)**.  
2. If εₓ is **negative**, recompute using **Equation (2)**.  
3. Apply AS 3600 limits:  
   $$-2.0\times10^{-4} \le \varepsilon_x \le 3.0\times10^{-3}$$
4. Use the resulting εₓ to compute $k_v$ in Check 5.
"""
                    )
        
        # Build summary line
        check4_summary = f"Check 4 — Longitudinal strain $\\varepsilon_x$ | Result: $\\varepsilon_x = {eps_x:.5f}$ ({eq_used.split('–')[0].strip()})"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check4",
            title="Check 4 — Longitudinal strain $\\varepsilon_x$",
            summary_md=check4_summary,
            status_kind=None,
            calc_md=check4_calc_md,
            diagram_render_fn=check4_diagram_fn,
            info_render_fn=check4_info_fn,
            anchor_id="mcft_state",
        )

        # =====================================================
        # Check 5 — k_v AND θ_v
        # =====================================================
        # For the summary text inside the calcbox
        Asv_over_s = Asv / s
        Asv_min_over_s = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)
        k_dg_display = k_dg if use_general_kv else float("nan")

        if use_general_kv:
            kv_formula_block = f"""
**General MCFT form (AS 3600 Cl. 8.2.4.2):**

For *low* stirrup ratio $A_{{sv}}/s < (A_{{sv}}/s)_{{min}}$:

$$k_v = \\frac{{0.4}}{{1 + 1500\\varepsilon_x}} \\cdot \\frac{{1300}}{{1000 + k_{{dg}} d_v}}$$

For *adequate* stirrups $A_{{sv}}/s \\ge (A_{{sv}}/s)_{{min}}$:

$$k_v = \\frac{{0.4}}{{1 + 1500\\varepsilon_x}}$$
"""
            kv_sub_block = f"""
**Current case:** {kv_case}  

- $\\varepsilon_x = {eps_x:.5f}$  
- $k_{{dg}} \\approx {k_dg_display:.3f}$  
- $d_v = {d_v:.1f}$ mm  

$$(A_{{sv}}/s)_{{min}} = 0.08\\sqrt{{f'_c}} \\cdot \\frac{{b_v}}{{f_{{sy,v}}}} = {Asv_min_over_s:.3f}\\text{{ mm}}^2/\\text{{mm}}$$

$$A_{{sv}}/s = {Asv_over_s:.3f}\\text{{ mm}}^2/\\text{{mm}}$$

Thus:

$$k_v = {k_v:.3f}$$

Strut angle (MCFT):

$$\\theta_v = 29 + 7000\\varepsilon_x = {theta_v_deg:.1f}°$$
"""
        else:
            kv_formula_block = f"""
**Simplified non-prestressed form (AS 3600 Cl. 8.2.4.3):**

If $A_{{sv}}/s < (A_{{sv}}/s)_{{min}}$:

$$k_v = \\min\\left(\\frac{{200}}{{1000 + 1.3 d_v}}, 0.10\\right)$$

Otherwise:

$$k_v = 0.15$$

Strut angle is taken as:

$$\\theta_v = 36°$$
"""
        kv_sub_block = f"""
**Current case:** {kv_case}  

- $d_v = {d_v:.1f}$ mm  

$$(A_{{sv}}/s)_{{min}} = 0.08\\sqrt{{f'_c}} \\cdot \\frac{{b_v}}{{f_{{sy,v}}}} = {Asv_min_over_s:.3f}\\text{{ mm}}^2/\\text{{mm}}$$

$$A_{{sv}}/s = {Asv_over_s:.3f}\\text{{ mm}}^2/\\text{{mm}}$$

Hence:

$$k_v = {k_v:.3f}, \\quad \\theta_v = {theta_v_deg:.1f}°$$
"""

        check5_calc_md = f"""
*Purpose: Determine the shear parameters $k_v$ and $\\theta_v$ for use in $V_{{uc}}$ and web-crushing checks.*

**Inputs:**

- Concrete: $f'_c = {fc:.1f}$ MPa  
- Geometry: $b_v = {b_v:.1f}$ mm, $d_v = {d_v:.1f}$ mm, $d_g = {d_g:.1f}$ mm  
- Transverse steel: $A_{{sv}} = {Asv:.1f}$ mm², spacing $s = {s:.1f}$ mm, $f_{{sy,v}} = {f_syv:.1f}$ MPa  
- Aggregate size factor: $k_{{dg}} \\approx {k_dg_display:.3f}$  
- Strain: $\\varepsilon_x = {eps_x:.5f}$  

---

{kv_formula_block}

---

{kv_sub_block}

**Result:**  

- $k_v = {k_v:.3f}$  
- $\\theta_v = {theta_v_deg:.1f}°$

"""
            
        # Diagram render function
        def check5_diagram_fn():
            # Theta diagram on the right
            theta_path = os.path.join("assets", "theta.png")
            if os.path.exists(theta_path):
                st.image(theta_path, caption="Strut angle $\\theta_v$", use_container_width=True)
            else:
                st.info(f"💡 Add theta diagram at `{theta_path}`.")

        # Info render function (popover)
        def check5_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="MCFT parameters (what kv and θv represent)"):
                    st.markdown(r"""
### MCFT parameters

**kv (concrete effectiveness factor)**

kv represents the effectiveness of cracked concrete in resisting shear.  

Lower kv generally means more cracking/deformation and less concrete shear contribution.

**θv (crack angle)**

θv is the average diagonal crack angle in the web.  

It influences how shear is resolved into diagonal compression and stirrup tension.

These are treated as model parameters obtained directly from AS 3600 relationships.
                    """)
        
        # Build summary line
        check5_summary = f"Check 5 — MCFT parameters ($k_v$ and $\\theta_v$) | Result: $k_v = {k_v:.3f}$, $\\theta_v = {theta_v_deg:.1f}°$"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check5",
            title="Check 5 — MCFT parameters (k_v and θ_v)",
            summary_md=check5_summary,
            status_kind=None,
            calc_md=check5_calc_md,
            diagram_render_fn=check5_diagram_fn,
            info_render_fn=check5_info_fn,
        )

        # =====================================================
        # Check 6 — CONCRETE SHEAR CONTRIBUTION V_uc ONLY
        # =====================================================
        check6_calc_md = f"""
*Purpose: Calculate the concrete shear strength $V_{{uc}}$ at the critical section.*  

**Inputs:**  

- $k_v = {k_v:.3f}$  

- $b_v = {b_v:.1f}$ mm, $d_v = {d_v:.1f}$ mm  

- $f'_c = {fc:.1f}$ MPa (limited $\\sqrt{{f'_c}} = {sqrt_fc_limited:.3f}$ MPa)  

---

**Formula (AS 3600 Cl. 8.2.4.1):**  

$$V_{{uc}} = k_v b_v d_v \\sqrt{{f'_c}}$$  

**Substitution:**  

$$V_{{uc}} = {k_v:.3f} \\times {b_v:.1f} \\times {d_v:.1f} \\times {sqrt_fc_limited:.3f} = {Vuc_kN:,.1f}\\,\\text{{kN}}$$  

---

**Result:**  

- **Concrete shear strength:** $V_{{uc}} = {Vuc_kN:,.1f}$ kN  

*(Steel contribution $V_s$ is added in the next step.)*

"""
        
        # Diagram render function
        def check6_diagram_fn():
            _safe_step_diagram(6)
        
        # Info render function (popover)
        def check6_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(use_container_width=True):
                    st.markdown("### Check 6 – Concrete contribution $V_{uc}$")
                    st.markdown(
                        r"""
- In the MCFT model used by AS 3600, concrete shear strength at the critical section is

  $$V_{uc} = k_v b_v d_v \sqrt{f'_c}$$  

- The factor $k_v$ depends mainly on **longitudinal strain** $\varepsilon_x$ and crack spacing:  

  higher tensile strain → wider cracks → **smaller $k_v$** → smaller $V_{uc}$.

- $V_{uc}$ represents the combined effect of:  

  - residual shear across cracks,  

  - **aggregate interlock**, and  

  - **dowel action** from longitudinal bars.

This step isolates the **concrete-only** contribution before we add the stirrup shear $V_s$.
"""
                    )
        
        # Build summary line
        check6_summary = f"Check 6 — Concrete shear strength $V_{{uc}}$ | Result: $V_{{uc}} = {Vuc_kN:,.1f}$ kN"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check6",
            title="Check 6 — Concrete shear strength V_uc",
            summary_md=check6_summary,
            status_kind=None,
            calc_md=check6_calc_md,
            diagram_render_fn=check6_diagram_fn,
            info_render_fn=check6_info_fn,
            anchor_id="vc",
        )

        # =====================================================
        # Check 7 — STEEL SHEAR CONTRIBUTION V_s
        # =====================================================
        # Step 7 details
        step7_details = f"""
*Purpose: Calculate the shear strength provided by ligatures $V_s$.*  



**Inputs:**  



- $A_{{sv}} = {Asv:.1f}$ mm², spacing $s = {s:.1f}$ mm  

- $f_{{sy,v}} = {f_syv:.1f}$ MPa  

- $d_v = {d_v:.1f}$ mm, $\\theta_v = {theta_v_deg:.1f}°$  



---



**Formula (AS 3600 Cl. 8.2.5.2(a)):**  



$$V_{{us}} = \\left(\\frac{{A_{{sv}} f_{{sy,v}} d_v}}{{s}}\\right)\\cot \\theta_v$$  



**Substitution:**  



$$V_{{us}} = \\left(\\frac{{{Asv:.1f} \\times {f_syv:.1f} \\times {d_v:.1f}}}{{{s:.1f}}}\\right) \\cot {theta_v_deg:.1f}° = {Vus_kN:,.1f}\\,\\text{{kN}}$$  



---



**Result:**  



- **Steel shear strength:** $V_s = V_{{us}} = {Vus_kN:,.1f}$ kN  

*(Concrete shear $V_{{uc}}$ was found in Check 6.)*

"""
        
        check7_calc_md = step7_details
        
        # Diagram render function
        def check7_diagram_fn():
            # Move the steel ligature diagram here
            _safe_image(
                "assets/shear_ligatures_and_crack.png",
                caption="Shear ligatures crossing a diagonal crack over $d_v \\cot\\theta_v$.",
            )

        # Info render function (popover)
        def check7_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(use_container_width=True):
                    st.markdown("### Check 7 – How stirrups contribute $V_s$")
                    calcbox(
                        r"""
**Steel contribution $V_s$**

- Vertical or inclined shear ligatures cross the **inclined crack length**  

  $$\ell_{cr} \approx d_v \cot\theta_v$$  

- Within a spacing $s$, the amount of steel crossing the crack is  

  $$n = \frac{d_v \cot\theta_v}{s}$$  

- The shear carried by stirrups is  

  $$V_s = V_{us} = \frac{A_{sv} f_{sy,v} d_v}{s}\,\cot\theta_v$$  

- Shear steel **raises total shear capacity**, but more importantly it provides **ductility** and helps control crack widths after concrete has cracked.
"""
                    )
        
        # Build summary line
        check7_summary = f"Check 7 — Steel shear strength $V_s$ | Result: $V_s = V_{{us}} = {Vus_kN:,.1f}$ kN"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check7",
            title="Check 7 — Steel shear strength V_s",
            summary_md=check7_summary,
            status_kind=None,
            calc_md=check7_calc_md,
            diagram_render_fn=check7_diagram_fn,
            info_render_fn=check7_info_fn,
            anchor_id="vs",
        )

        # =====================================================
        # Check 8 — COMBINED SHEAR STRENGTH AND SECTIONAL CHECK
        # =====================================================
        check8_calc_md = f"""
*Purpose: Combine concrete and steel contributions and check $\phi V_u$ against $V_{{eq}}^*$.*  



**Inputs:**  



- $V_{{uc}} = {Vuc_kN:,.1f}$ kN (from Check 6)  

- $V_s = {Vus_kN:,.1f}$ kN (from Check 7)  

- $P_v = {P_v:.1f}$ kN  

- Strength reduction: $\\phi = {phi:.2f}$  

- Demand: $V_{{eq}}^* = {V_eq:.1f}$ kN  



---



**Total sectional shear capacity (AS 3600 Cl. 8.2.3.1):**  



$$V_u = V_{{uc}} + V_s + P_v$$  



$$V_u = {Vuc_kN:,.1f} + {Vus_kN:,.1f} + {P_v:.1f} = {Vu_total_kN:,.1f}\\,\\text{{kN}}$$  



Design strength:  



$$\\phi V_u = {phi:.2f} \\times {Vu_total_kN:,.1f} = {phi_Vu:,.1f}\\,\\text{{kN}}$$  



---



**Sectional shear check:**  



- Requirement: $\\phi V_u \\ge V_{{eq}}^*$  

- Here: {phi_Vu:,.1f} kN vs {V_eq:.1f} kN → **{"OK" if shear_ok else "NOT OK"}**

"""
            
        # Diagram render function
        def check8_diagram_fn():
            _safe_step_diagram(6)  # or a new combined diagram if you add one later

        # Info render function (popover)
        def check8_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Sectional shear capacity (Vu components)"):
                    st.markdown(r"""
### Sectional shear capacity

**Concrete contribution (Vuc)**

Vuc is the concrete web contribution to shear resistance (as modified by kv and section geometry).

**Steel contribution (Vus)**

Vus is the stirrup contribution: shear reinforcement crossing diagonal cracks resists shear through tension.

**Why they add**

Concrete and stirrups act together, so the sectional capacity is taken as:

\[
V_u = V_{uc} + V_{us} + P_v
\]

and the design capacity is \( \phi V_u \).

This popover is intentionally capacity-only (no MCFT theory here).
                    """)
        
        # Build summary line
        pass_fail = "PASS" if shear_ok else "FAIL"
        check8_summary = f"Check 8 — Sectional shear capacity check | Result: $\\phi V_u = {phi_Vu:,.1f}$ kN vs $V_{{eq}}^* = {V_eq:.1f}$ kN → **{pass_fail}**"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check8",
            title="Check 8 — Sectional shear capacity",
            summary_md=check8_summary,
            status_kind=shear_status,
            calc_md=check8_calc_md,
            diagram_render_fn=check8_diagram_fn,
            info_render_fn=check8_info_fn,
        )

        # =====================================================
        # Check 9 — WEB CRUSHING CHECK
        # =====================================================
        if not web_ok:
            st.error("Web-crushing limit exceeded – revise section/ligs.")

        check9_calc_md = f"""
*Purpose: Check that combined shear + torsion does not exceed the web-crushing limit (Cl. 8.2.6).*  

**Inputs:**  

- $f'_c = {fc:.1f}$ MPa, $b_v = {b_v:.1f}$ mm, $d_v = {d_v:.1f}$ mm  
- $\\theta_v = {theta_v_deg:.1f}^\\circ$, $\\theta_1 = {theta_1_deg:.1f}^\\circ$  
- $P_v = {P_v:.1f}$ kN  
- Actions: $V^* = {V_star:.1f}$ kN, $T^* = {T_star:.1f}$ kNm  
- Torsion geometry: $u_h = {uh:.1f}$ mm, $A_{{oh}} = {A_oh:.1f}$ mm²  

---

**Web-crushing shear capacity (Cl. 8.2.6):**  

$$\\large V_{{u,\\max}} = 0.55 f'_c b_v d_v \\frac{{\\cot\\theta_v + \\cot\\theta_1}}{{1 + \\cot^2\\theta_v}} + P_v$$

**Substitution:**  

$$\\large V_{{u,\\max}} = 0.55 \\times {fc:.1f} \\times {b_v:.1f} \\times {d_v:.1f} \\times \\frac{{\\cot({theta_v_deg:.1f}^\\circ) + \\cot({theta_1_deg:.1f}^\\circ)}}{{1 + \\cot^2({theta_v_deg:.1f}^\\circ)}} + {P_v:.1f} = {Vu_max_kN:,.1f}\\,\\text{{kN}}$$

---

**Combined shear + torsion demand (per unit $b_v d_v$):**  

$$\\large \\text{{Demand}} = \\sqrt{{\\left(\\frac{{V^*}}{{b_v d_v}}\\right)^2 + \\left(\\frac{{T^* u_h}}{{1.7 A_{{oh}}^2}}\\right)^2}}$$

**Substitution:**  

$$\\large \\text{{Demand}} = \\sqrt{{\\left(\\frac{{{V_star:.1f}}}{{{b_v:.1f} \\times {d_v:.1f}}}\\right)^2 + \\left(\\frac{{{T_star:.1f} \\times {uh:.1f}}}{{1.7 \\times {A_oh:.1f}^2}}\\right)^2}} = {LHS:,.1f}$$

---

**Design limit (web-crushing capacity per unit $b_v d_v$):**  

$$\\large \\text{{Capacity}} = \\frac{{\\phi V_{{u,\\max}}}}{{b_v d_v}}$$

**Substitution:**  

$$\\large \\text{{Capacity}} = \\frac{{{phi:.2f} \\times {Vu_max_kN:,.1f}}}{{{b_v:.1f} \\times {d_v:.1f}}} = {RHS:,.1f}$$

---

**Web-crushing check:**  

- Requirement: Demand $\\le$ Capacity  
- Here: {LHS:,.1f} vs {RHS:,.1f} → **{"OK" if web_ok else "NOT OK"}**
"""
            
        # Diagram render function
        def check9_diagram_fn():
            _safe_step_diagram(7)

        # Info render function (popover)
        def check9_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Web crushing (strut failure cap)"):
                    st.markdown(r"""
### Web crushing (strut failure limit)

**What web crushing is**

Web crushing is failure of the diagonal concrete compression struts in a cracked web under high shear.

**Why it is independent of stirrups**

Once the compression struts reach their crushing capacity, adding more shear reinforcement cannot prevent failure.  

The limit is governed by concrete compressive capacity.

**Why it caps shear capacity**

This check provides an upper bound on shear resistance to prevent brittle compression failures.  

Regardless of reinforcement, design shear capacity cannot exceed this limit.
                    """)
        
        # Build summary line
        web_pass_fail = "PASS" if web_ok else "FAIL"
        check9_summary = f"Check 9 — Web-crushing strength check | Result: Demand {LHS:,.1f} vs Capacity {RHS:,.1f} → **{web_pass_fail}**"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check9",
            title="Check 9 — Web-crushing strength",
            summary_md=check9_summary,
            status_kind=web_status,
            calc_md=check9_calc_md,
            diagram_render_fn=check9_diagram_fn,
            info_render_fn=check9_info_fn,
            anchor_id="vu_max",
        )

    # =====================================================
    # TAB 3: Shear reinforcement checks
    # =====================================================
    with tab3:
        st.caption("Minimum shear reinforcement and detailing requirements.")

        # =====================================================
        # Check 10 — MINIMUM SHEAR REINFORCEMENT CHECK
        # =====================================================
        check10_calc_md = f"""
*Purpose: Check that provided shear reinforcement meets minimum requirements (AS 3600 Cl. 8.2.5).*

**Inputs:**

- Provided: $A_{{sv}} = {Asv:.1f}$ mm², spacing $s = {s:.1f}$ mm  
- Concrete: $f'_c = {fc:.1f}$ MPa  
- Geometry: $b_v = {b_v:.1f}$ mm  
- Steel: $f_{{sy,v}} = {f_syv:.1f}$ MPa  

---

**Provided reinforcement rate:**

$$\\frac{{A_{{sv}}}}{{s}} = \\frac{{{Asv:.1f}}}{{{s:.1f}}} = {Asv_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$$

**Minimum required (AS 3600 Cl. 8.2.5):**

$$\\left(\\frac{{A_{{sv}}}}{{s}}\\right)_{{min}} = 0.08\\sqrt{{f'_c}} \\cdot \\frac{{b_v}}{{f_{{sy,v}}}} = 0.08\\sqrt{{{fc:.1f}}} \\cdot \\frac{{{b_v:.1f}}}{{{f_syv:.1f}}} = {Asv_min_over_s:.3f}\\ \\text{{mm}}^2/\\text{{mm}}$$

---

**Check:**

- Requirement: $A_{{sv}}/s \\ge (A_{{sv}}/s)_{{min}}$  
- Here: {Asv_over_s_check10:.3f} vs {Asv_min_over_s_check10:.3f} → **{"OK" if min_shear_ok else "NOT OK"}**
"""
            
        # Diagram render function
        def check10_diagram_fn():
            _safe_step_diagram(8)  # Step 8 diagram (ligature spacing)
        
        # Info render function (popover)
        def check10_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Minimum shear reinforcement (ductility)"):
                    st.markdown(r"""
### Minimum shear reinforcement

**Why minimum stirrups are required**

Even if calculated shear demand is low, minimum transverse reinforcement is required to:

- control crack development,

- provide ductility and robustness, and

- ensure a reliable shear mechanism after cracking.

**What this check is doing**

This compares the provided reinforcement rate \(A_{sv}/s\) against the minimum required by AS 3600 for the given section and material properties.

If the provided rate is below minimum, shear behaviour assumptions become unreliable and detailing must be increased.
                    """)
        
        # Build summary line
        min_pass_fail = "PASS" if min_shear_ok else "FAIL"
        check10_summary = f"Check 10 — Minimum shear reinforcement check | Result: $A_{{sv}}/s = {Asv_over_s_check10:.3f}$ vs $(A_{{sv}}/s)_{{min}} = {Asv_min_over_s_check10:.3f}$ → **{min_pass_fail}**"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check10",
            title="Check 10 — Minimum shear reinforcement",
            summary_md=check10_summary,
            status_kind=min_shear_status,
            calc_md=check10_calc_md,
            diagram_render_fn=check10_diagram_fn,
            info_render_fn=check10_info_fn,
        )

        # =====================================================
        # Check 11 — DETAILING AND DEEP BEAM NOTE
        # =====================================================
        check11_calc_md = f"""
*Purpose: Provide guidance on ligature spacing, detailing requirements, and when strut-and-tie analysis is needed.*

**Ligature spacing and detailing along the span (AS 3600 Cl. 8.2.5.1):**

- Where the required shear reinforcement **$A_{{sv}}/s$ varies** along the member, the code assumes a **linear variation** over each segment.  
- Detailing should follow the **recommended patterns** (e.g. Figure C8.2.5.1), so that provided $A_{{sv}}/s$ ≥ required $A_{{sv}}/s$ in the **critical region**.  
- Proper spacing is essential because shear failure due to **yielding of ligatures** tends to occur in a **localized zone** near peak shear.  
- The goal is to avoid "gaps" in shear resistance where the **provided envelope drops below the required line**.

**Detailing requirements:**

- Stirrups must be properly anchored (AS 3600 Cl. 8.2.5)  
- Maximum spacing: $s \\le \\min(0.75D, 500\\ \\text{{mm}})$  
- Minimum spacing: sufficient for concrete placement and consolidation  

**When to use strut-and-tie model:**

- Deep beams (span/depth < 2.5)  
- Disturbed regions (loads within $d_v$ of support)  
- Significant point loads near supports  
- Complex geometry or loading patterns  

**Note:** This step is informational. Detailed strut-and-tie analysis should be performed separately when required.
"""
        
        # Diagram render function
        def check11_diagram_fn():
            # Ligature spacing diagram (moved from standalone section after Check 9)
            col_left, col_center, col_right = st.columns([1, 6, 1])
            with col_center:
                _safe_image(
                    "assets/shear_lig_spacing_code_diagram.png",
                    caption="Example of varying Asv/s along the span (AS 3600 Fig. C8.2.5.1).",
                )
        
        # Info render function (popover)
        def check11_info_fn():
            col_info_header, _ = st.columns([0.1, 0.9])
            with col_info_header:
                with info_i_button(help_text="Detailing + when strut-and-tie governs"):
                    st.markdown(r"""
### Detailing and deep-beam behaviour

**Why detailing matters**

Shear capacity equations assume:

- reinforcement is properly anchored,

- cracks are intercepted by stirrups,

- spacing is not excessive, and

- the shear-resisting zone is well confined.

**When to consider strut-and-tie**

For short shear spans (deep beams / disturbed regions), the stress field is not beam-like.  

In these cases, a strut-and-tie model may govern and web crushing / strut behaviour becomes critical.

**Placeholders for diagrams**

- [Diagram] θ definition / crack angle  

- [Diagram] Strut-and-tie behaviour in deep beams  

- [Diagram] Web crushing mechanism
                    """)

        # Build summary line
        check11_summary = "Check 11 — Detailing and deep-beam considerations | Informational guidance (no pass/fail check)"
        
        render_expandable_step(
            page_key="shear",
            step_id="shear_check11",
            title="Check 11 — Detailing and deep-beam considerations",
            summary_md=check11_summary,
            status_kind=None,
            calc_md=check11_calc_md,
            diagram_render_fn=check11_diagram_fn,
            info_render_fn=check11_info_fn,
        )

    # =======================================================
    # 9. SUMMARY TABLE + PUSH RESULTS
    # =======================================================
    # Note: torsion_required, V_eq, phi_Vu, etc. are computed inside tabs but need to be accessible here
    # They are already computed in tab_dim (torsion_required, V_eq) and tab_reinf (phi_Vu, shear_ok)
    # We need to ensure these are available at module scope or recompute them here
    # For now, we'll use the values computed in the tabs (they should be in scope)
    torsion_label = (
        "Yes (T* > 0.25 φT_cr)" if torsion_required else "No (strength check)"
    )

    shear_util = V_eq / phi_Vu if phi_Vu > 0 else float("nan")

    # Summary table data for clickable summary table
    rows_summary = [
        {
            "Check": "Torsion considered?",
            "Value": torsion_label,
            "Limit": "",
            "Utilisation": "—",
            "Status": "—",
        },
        {
            "Check": "Sectional shear capacity (φV_u vs V_eq*)",
            "Value": f"{V_eq:.1f} kN",
            "Limit": f"φV_u,cap = {phi_Vu:.1f} kN",
            "Utilisation": f"{shear_util:.2f}" if phi_Vu > 0 else "—",
            "Status": "OK" if shear_ok else "NG",
        },
        {
            "Check": "Concrete contribution V_c",
            "Value": f"{Vuc_kN:,.1f} kN",
            "Limit": "",
            "Utilisation": "—",
            "Status": "—",
        },
        {
            "Check": "Shear reinforcement V_s",
            "Value": f"{Vus_kN:,.1f} kN",
            "Limit": "",
            "Utilisation": "—",
            "Status": "—",
        },
        {
            "Check": "Web-crushing capacity V_u,max",
            "Value": f"{Vu_max_kN:,.1f} kN",
            "Limit": "Demand ≤ Capacity",
            "Utilisation": "—",
            "Status": "OK" if web_ok else "NG",
        },
        {
            "Check": "εₓ, k_v, θ_v",
            "Value": f"εₓ = {eps_x:.5f},  k_v = {k_v:.3f},  θ_v = {theta_v_deg:.1f}°",
            "Limit": "",
            "Utilisation": "—",
            "Status": "—",
        },
    ]

    # Publish key shear results for Inputs summary
    update_results(
        phi_Vu_cap=phi_Vu,
        Vu_utilisation=shear_util if not math.isnan(shear_util) else 0.0,
    )

    # Map summary rows -> step UIDs and anchor IDs
    check_to_uid = {
        "Torsion considered?": "shear_check1",
        "Sectional shear capacity (φV_u vs V_eq*)": "shear_check8",
        "Concrete contribution V_c": "shear_check6",
        "Shear reinforcement V_s": "shear_check7",
        "Web-crushing capacity V_u,max": "shear_check9",
        "εₓ, k_v, θ_v": "shear_check4",
    }
    
    # Map summary rows -> tab labels (for tab switching on click)
    check_to_tab = {
        "Torsion considered?": "Torsion + dimensions",
        "Sectional shear capacity (φV_u vs V_eq*)": "MCFT and strength checks",
        "εₓ, k_v, θ_v": "MCFT and strength checks",
        "Concrete contribution V_c": "MCFT and strength checks",
        "Shear reinforcement V_s": "MCFT and strength checks",
        "Web-crushing capacity V_u,max": "MCFT and strength checks",
    }

    # Build ROWS list for render_clickable_summary_table
    ROWS = []
    for row in rows_summary:
        check = row["Check"]
        uid = check_to_uid.get(check)
        if uid:  # Only include rows that have a matching calc step
            # Determine ok status for styling (True=pass/green, False=fail/red, None=neutral)
            status_str = row.get("Status", "")
            ok = None
            if status_str == "OK":
                ok = True
            elif status_str in ("NG", "Check", "FAIL"):
                ok = False
            
            tab = check_to_tab.get(check, "")
            ROWS.append({
                "uid": uid,
                "title": check,
                "value": row.get("Value", ""),
                "limit": row.get("Limit", ""),
                "util": row.get("Utilisation", ""),
                "status": status_str,
                "ok": ok,
                "tab": tab,
                "is_primary": (check == "Sectional shear capacity (φV_u vs V_eq*)"),
                "anchor_id": uid,  # always scroll to <div id="calc_{uid}">
            })
    
    # Sort ROWS so primary check is first
    priority = {
        "Sectional shear capacity (φV_u vs V_eq*)": 0,
        "Torsion considered?": 1,
        "Concrete contribution V_c": 2,
        "Shear reinforcement V_s": 3,
        "Web-crushing capacity V_u,max": 4,
        "εₓ, k_v, θ_v": 5,
    }
    ROWS.sort(key=lambda r: priority.get(r["title"], 99))

    # Render clickable summary table at the top (using placeholder created early)
    # Note: This renders at the end but the placeholder was created at the top
    with top_summary_placeholder.container():
        st.subheader("Shear – Summary")
        render_clickable_summary_table(ROWS, key_prefix="shear_summary")
        bind_summary_clicks()
        
        page_divider()


if __name__ == "__main__":
    render_shear()
