import math
import os
import pandas as pd
import streamlit as st

from state_and_helpers import (
    get_param,
    get_sync_callbacks,
    update_results,
)

# Shared helpers (same contract as Inputs/Bending)
from widgets_helpers import apply_global_widget_css, apply_calcbox_css, number_row


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
    7: ("shear_step7_Vumax.png", "Step 7 – web-crushing limit $V_{u,\\max}$"),
    8: ("shear_step8_lig_spacing.png", "Step 8 – ligature spacing and detailing"),
}


def _safe_step_diagram(step_no: int):
    """Always show the diagram for a step on the right; fail gracefully if missing."""
    fname, caption = STEP_DIAGRAMS.get(step_no, (None, None))
    if not fname:
        return
    path = os.path.join("assets", fname)
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
        st.markdown("### Step 1 – Shear + torsion cracking region")
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
        st.markdown("### Step 2 – Critical section at $d_v$")
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
        st.markdown("### Step 3 – Equivalent shear $V_{eq}^*$")
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
        st.markdown("### Step 4 – Longitudinal strain $\varepsilon_x$")
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
        st.markdown("### Step 5 – $k_v$ and $\theta_v$")
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
        st.markdown("### Step 6 – Concrete shear $V_{uc}$ and steel shear $V_s$")
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
        st.markdown("### Step 7 – Web-crushing limit $V_{u,\\max}$")
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
        st.markdown("### Step 8 – Ligature spacing and detailing")
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


def _inject_calcbox_css():
    """Inject CSS for blue blockquote styling."""
    st.markdown(
        """
<style>
blockquote {
  border-left: 4px solid #1f77b4 !important;
  background-color: rgba(31, 119, 180, 0.08) !important;
  padding: 0.75rem 1rem !important;
  margin: 0.5rem 0 0.75rem 0 !important;
  border-radius: 0 6px 6px 0 !important;
  color: #1a1a1a !important;
}
blockquote p, blockquote * { color: #1a1a1a !important; }
</style>
""",
        unsafe_allow_html=True,
    )


def calcbox(md: str):
    """Render a blue calculation box with proper LaTeX support."""
    # Convert \[...\] to $$...$$ for display math
    converted = md.replace("\\[", "$$").replace("\\]", "$$")
    # Convert \(...\) to $...$ for inline math
    converted = converted.replace("\\(", "$").replace("\\)", "$")
    
    # Convert to blockquote format
    lines = converted.strip().split("\n")
    blockquote = "\n".join("> " + line for line in lines)
    st.markdown(blockquote)


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
            with st.popover("ℹ️", use_container_width=True):
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
            with st.popover("ℹ️", use_container_width=True):
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
            with st.popover("ℹ️", use_container_width=True):
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
#  MAIN PAGE RENDER FUNCTION
# ------------------------------------------------------------
def render_shear():
    apply_global_widget_css()
    _inject_calcbox_css()

    st.title("Shear & Torsion")

    sync_callbacks = get_sync_callbacks()

    # --- Layout row: intro text (left) + dv diagram (right) ---
    col_left, col_right = st.columns([1, 1])  # 50/50 split

    with col_left:
        st.markdown(
            r"""
This page evaluates **design shear**, **shear reinforcement**, and **torsion resistance**
for reinforced concrete beams in accordance with **AS 3600:2018**, using the full MCFT-based 
shear method.

- Concrete shear strength $V_c$ (Cl. 8.2.7)  

- Shear reinforcement contribution $V_s$ (Cl. 8.2.8)  

- Design shear capacity $\phi V_{uc} = \phi (V_c + V_s)$  

- Shear stress $\tau_v = V^*/(b_w d_v)$ and web-crushing checks  

- Torsional cracking, torsional reinforcement, and design torsion capacity (Cl. 8.3.6–8.3.7)  

- Interaction of shear and torsion where applicable  

Results are expressed in kN and MPa, and directly feed into deflection, crack-width, and interaction checks.
        """
        )

    with col_right:
        # Use a fixed width (approximately 60% of half the page width)
        # For a typical page width of ~1200px, half is ~600px, 60% of that is ~360px
        _safe_image(
            "assets/shear_flexural_cracks_dv.png",
            caption=None,
            width=360,  # Fixed width - adjust as needed
        )

    # Summary table placeholder – appears directly under the blurb
    summary_placeholder = st.empty()

    # =====================================================
    # 1. DESIGN INPUTS (shared + local)  — SAME WIDGET CONTRACT
    # =====================================================
    st.subheader("Design Inputs")

    col_geom, col_actions, col_eps = st.columns(3)

    # ---------- 1.1 Geometry & materials (shared) ----------
    with col_geom:
        st.markdown("### Geometry & materials")

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

    # ---------- 1.2 Shear & torsion actions (shared) ----------
    with col_actions:
        st.markdown("### Shear, axial & torsion actions")

        number_row(
            "Design shear V* (kN)",
            "shear_Vu_star",
            get_param("Vu_star", 300.0),
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
            "Vertical prestress / axial P_v (kN)",
            "shear_P_star",
            get_param("P_star", 0.0),
            sync_callbacks,
            help_text="Prestress or vertical axial force assisting shear.",
        )
        number_row(
            "Torsion T* (kNm)",
            "shear_Tu_star",
            get_param("Tu_star", 0.0),
            sync_callbacks,
            help_text="Factored torsion at the section.",
        )

        phi = st.number_input(
            "φ – strength reduction for shear",
            value=0.75,
            min_value=0.5,
            max_value=0.9,
            step=0.05,
        )
        sigma_cp = st.number_input(
            "σ_cp – average prestress (MPa)",
            value=0.0,
            help="Used in torsion cracking torque T_cr (AS 3600 Cl. 8.3.4).",
        )

    # ---------- 1.3 εx helper inputs (local only) ----------
    with col_eps:
        st.markdown("### εₓ inputs (ULS flexural strain)")

        A_st = st.number_input(
            "A_st (mm²) – non-prestressed tension steel",
            value=float(4 * (math.pi * 20 ** 2 / 4)),
        )
        A_pt = st.number_input(
            "A_pt (mm²) – prestressing steel",
            value=0.0,
        )
        f_po = st.number_input(
            "f_po (MPa) – effective tendon stress",
            value=0.0,
        )
        A_ct = st.number_input(
            "A_ct (mm²) – area of concrete in tension",
            value=float((get_param("b", 300.0)) * (get_param("D", 600.0) / 2.0)),
        )

    # ---------- 1.4 Shear section inputs (for Step 3) ----------
    st.markdown("### Shear section parameters")
    col_shear1, col_shear2, col_shear3 = st.columns(3)

    with col_shear1:
        d_g = st.number_input(
            "Maximum aggregate size d_g (mm)",
            value=20.0,
            min_value=5.0,
            max_value=40.0,
        )
        sum_duct = st.number_input(
            "Sum of duct diameters crossing web (mm)",
            value=0.0,
            min_value=0.0,
        )

    with col_shear2:
        kd_opt = st.selectbox(
            "k_d factor for prestressing ducts",
            (
                ("None (no ducts in web)", 0.0),
                ("0.5 – steel ducts, grouted", 0.5),
                ("0.8 – plastic ducts, grouted", 0.8),
                ("1.2 – ungrouted ducts", 1.2),
            ),
            index=0,
            format_func=lambda kv: kv[0],
        )
        k_d = kd_opt[1]

    with col_shear3:
        method = st.radio(
            "k_v method",
            (
                "General εₓ-based (Cl. 8.2.4.2)",
                "Simplified non-prestressed (Cl. 8.2.4.3)",
            ),
            index=0,
        )
        use_general_kv = method.startswith("General")

    # --- Conceptual behaviour + shear transfer (flexural vs deep) ---
    st.markdown("---")
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

    M_star = get_param("Mu_star") or 0.0
    V_star = get_param("Vu_star") or 0.0
    T_star = get_param("Tu_star") or 0.0
    N_star = get_param("N_star") or 0.0
    P_v = get_param("P_star") or 0.0

    lig_d = get_param("lig_d")
    legs = get_param("lig_legs")
    s_lig = get_param("s_lig")

    if not (b and D and d):
        st.error("Geometry (b, D, d) not fully defined – check Inputs / Bending tab.")
        return

    # =====================================================
    # 2. STEP 1 — TORSION CRACKING CHECK (T_cr)
    # =====================================================
    st.markdown("---")

    col_main, col_side = st.columns([3, 2])

    with col_main:
        col_title, col_info = st.columns([1, 0.08])

        with col_title:
            st.markdown(
                "### Step 1 – Does torsion crack the section? "
                "(T_cr check, AS 3600 Cl. 8.3.4)"
            )

        with col_info:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown("### Step 1 – Shear + torsion cracking region")
                st.markdown(
                    r"""
**Why we convert torsion into equivalent shear**



- Torsion produces **diagonal tension** in the beam web, similar to shear-induced diagonal cracking.  

- Treating torsion as an **equivalent shear demand** is conservative and avoids separate iterative torsion–shear coupling.  

- Using an equivalent shear \(V_{eq}^*\) means:

  - We track a **single internal force state** through all MCFT steps.  

  - Longitudinal strain \( \varepsilon_x \) reflects the combined effect of **shear + torsion + axial**.  

  - We don't under-predict crack width or over-predict concrete shear strength.



This step tells you whether torsion must be treated as a **design action**, and if so, it will be rolled into \(V_{eq}^*\) in Step 2.

"""
                )

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

        calcbox(
            f"""
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
        )

    with col_side:
        _safe_step_diagram(1)
        # theory for Step 1 is now only in the ℹ️ popover

    # =====================================================
    # 3. STEP 2 — CONVERT TORSION INTO AN EQUIVALENT SHEAR V_eq*
    # =====================================================
    st.markdown("---")

    col_main, col_side = st.columns([3, 2])

    with col_main:
        col_title, col_info = st.columns([1, 0.08])

        with col_title:
            st.markdown(
                "### Step 2 – Convert torsion into an equivalent shear "
                "$V_{eq}^*$ (AS 3600 Cl. 8.2.3)"
            )

        with col_info:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown("### Step 2 – Critical section and equivalent shear")
                st.markdown(
                    r"""
**Why shear is checked at \(d_v\)**



- Tests show that **peak diagonal cracking** and shear demand occur about **one effective depth \(d_v\)** from the support.  

- Around this section:

  - Flexural cracks rotate into steeper **diagonal shear cracks**.  

  - **Aggregate interlock** begins to reduce.  

  - **Concrete compression struts** form between load and support.  



AS 3600 therefore takes the design shear at a distance **\(d_v\)** from the support.



**Why we use \(V_{eq}^*\) instead of \(V^*\)**



- MCFT works off a **single set of internal forces** to define the strain state.  

- Shear, torsion and axial force all influence the **longitudinal strain \(\varepsilon_x\)**.  

- Converting torsion into an equivalent shear \(V_{t,eq}\) and combining it with \(V^*\) gives:



  $$V_{eq}^* = \sqrt{(V^*)^2 + V_{t,eq}^2}$$  



so all subsequent steps use a **consistent combined shear demand**.

"""
                )

        # Convert torsion to Nmm (needed for εₓ and web-crushing even if torsion design not required)
        T_star_Nmm = T_star * 1e6

        if torsion_required:
            # --- Full equivalent shear including torsion ---
            torsion_eq_N = 0.9 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
            torsion_eq_kN = torsion_eq_N / 1e3
            V_eq = math.sqrt(V_star ** 2 + torsion_eq_kN ** 2)

            calcbox(
            f"""
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
- **$V_{{eq}}^* = {V_eq:.1f}$ kN** is used in Steps 4–7.
"""
            )

        else:
            # --- No torsion design: equivalent shear = shear only ---
            torsion_eq_kN = 0.0
            V_eq = V_star

            calcbox(
            f"""
*Purpose: Convert torsion into an equivalent shear force (if required).*

**Inputs:**

- Shear demand: $V^* = {V_star:.1f}$ kN  
- Torsion: $T^* = {T_star:.1f}$ kNm (from Step 1, torsion design is not required)  

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
- **$V_{{eq}}^* = {V_eq:.1f}$ kN** is used in Steps 4–7.
"""
            )

    with col_side:
        _safe_step_diagram(2)

    # =====================================================
    # 4. STEP 3 — EFFECTIVE SECTION & SHEAR REINFORCEMENT
    # =====================================================
    st.markdown("---")

    col_main, col_side = st.columns([3, 2])

    with col_main:
        col_title, col_info = st.columns([1, 0.08])

        with col_title:
            st.markdown("### Step 3 – Determine shear-resisting section (b_v, d_v, ligs)")

        with col_info:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown("### Step 3 – What this step is doing")
                st.markdown(
                    r"""
**Why we compute \(b_v\), \(d_v\) and \(A_{sv}\)**



- \(b_v\) is the **effective web width** after accounting for ducts in the web.  

- \(d_v\) is the **effective shear depth**, taken as:



  $$d_v = \max(0.72D,\ 0.9d)$$  



to reflect where diagonal cracking and compression struts develop.  

- \(A_{sv}\) and \(s\) define how much **shear reinforcement** crosses potential cracks:



  $$A_{sv} = n_{\text{legs}} \frac{\pi d_{lig}^2}{4}$$  



These parameters are the **geometry + steel inputs** that feed into:



- the strain calculation in Step 4,  

- the concrete shear contribution \(V_{uc}\) in Step 6, and  

- the steel contribution \(V_s\) in Step 6.

"""
                )

        # Use values from session state / inputs section
    lig_d = lig_d or 10.0
    legs = legs or 2.0
    s = s_lig or 200.0

    Asv = legs * math.pi * lig_d ** 2 / 4.0
    f_syv = fsy

    b_v = b - k_d * sum_duct
    d_v = max(0.72 * D, 0.9 * d)

    dv_1 = 0.72 * D
    dv_2 = 0.9 * d

    calcbox(
        f"""
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

*(These values are used in Step 4.)*
"""
        )

    with col_side:
        _safe_step_diagram(3)

    # =====================================================
    # 5. STEP 4 — LONGITUDINAL STRAIN εx
    # =====================================================
    st.markdown("---")

    col_main, col_side = st.columns([3, 2])

    with col_main:
        # Step 4 heading with info bubble
        col_title, col_info = st.columns([1, 0.08])

        with col_title:
            st.markdown(
                "### Step 4 – Calculate longitudinal strain "
                r"$\varepsilon_x$ for MCFT (Cl. 8.2.4.2.2)"
            )

        with col_info:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown("### Understanding the Longitudinal Strain Equations")

                st.markdown(
                    r"""
**Where is εₓ measured?**

- εₓ is the **longitudinal strain at the mid-depth** of the cross-section at the shear-critical location.  
- The sign of εₓ tells us whether the concrete at **mid-depth** is in:
  - **Tension** → cracking → reduced shear resistance  
  - **Slight compression** → concrete still helps → increased shear resistance  
"""
                )

                st.markdown("---")
                st.markdown("### **Equation (1) – mid-depth in tension (εₓ ≥ 0)**")

                st.markdown(
                    r"""
**Use when:**  
- The calculated εₓ is **zero or positive**.  
- Mid-depth is in **tension**, so concrete is cracked and does not contribute.  
- Only **steel stiffness** is included in the denominator.
"""
                )

                st.latex(
                    r"""
\varepsilon_x =
\frac{
\dfrac{|M^*|}{d_v} +
\sqrt{
(|V^*| - P_v)^2 +
\left(
    \dfrac{0.97\,T^*\,u_h}{2A_o}
\right)^2
}
+ 0.5N^* - A_{pt}f_{po}
}
{
2(E_s A_{st} + E_p A_{pt})
}
\quad\text{(AS 3600 8.2.4.2.2(1))}
"""
                )

                st.markdown("---")
                st.markdown("### **Equation (2) – mid-depth in slight compression (εₓ < 0)**")

                st.markdown(
                    r"""
**Use when:**  
- The εₓ from Equation (1) comes out **negative**.  
- Mid-depth is in **slight compression**, meaning the concrete **still carries compressive stress**.  
- The concrete term $E_c A_{ct}$ is added to the denominator.
"""
                )

                st.latex(
                    r"""
\varepsilon_x =
\frac{
\dfrac{|M^*|}{d_v} +
|V^*| - P_v +
0.5N^* - A_{pt}f_{po}
}
{
2(E_s A_{st} + E_p A_{pt} + E_c A_{ct})
}
\quad\text{(AS 3600 8.2.4.2.2(2))}
"""
                )

                st.markdown(
                    r"""
**Code limits:**  

- For the tension case (Eq. 1):  $\varepsilon_x \le 3.0\times10^{-3}$  
- For the compression case (Eq. 2):  $-2.0\times10^{-4} \le \varepsilon_x \le 0$
"""
                )

                st.markdown("---")

                st.markdown(
                    r"""
### **How the app uses these equations**

1. Compute εₓ using **Equation (1)**.  
2. If εₓ is **negative**, recompute using **Equation (2)**.  
3. Apply AS 3600 limits:  
   $$-2.0\times10^{-4} \le \varepsilon_x \le 3.0\times10^{-3}$$
4. Use the resulting εₓ to compute $k_v$ in Step 5.
"""
                )

        # ------------------------------
        #  Compute εx terms (numerical)
        # ------------------------------
        M_star_Nmm = abs(M_star) * 1e6
        term_M = M_star_Nmm / (d_v or 1.0)

        # Shear + torsion term for Eq. (1)
        Vprime_kN = abs(V_star) - P_v
        Vprime_N = Vprime_kN * 1e3

        torsion_N = 0.97 * T_star_Nmm * uh / (2.0 * (Ao or 1.0))
        sqrt_inner = math.sqrt(Vprime_N ** 2 + torsion_N ** 2)

        # Axial / prestress
        N_star_N = 0.5 * N_star * 1e3
        A_pt_fpo_N = A_pt * f_po

        # Common numerator for Eq. (1)
        numerator_1 = term_M + sqrt_inner + N_star_N - A_pt_fpo_N

        Ep = 195000.0  # tendon modulus, MPa
        denom1 = 2.0 * (Es * A_st + Ep * A_pt)
        eps_x_1 = numerator_1 / denom1 if denom1 > 0 else 0.0

        # For Eq. (2) we use |V*| (no torsion term in numerator; torsion is still handled via V_eq)
        V_abs_N = abs(V_star) * 1e3
        numerator_2 = term_M + V_abs_N - P_v * 1e3 + N_star_N - A_pt_fpo_N
        denom2 = 2.0 * (Es * A_st + Ep * A_pt + Ec * A_ct)
        eps_x_2 = numerator_2 / denom2 if denom2 > 0 else 0.0

        # Choose governing εx according to AS 3600
        if eps_x_1 >= 0:
            eps_x_raw = eps_x_1
            eq_used = "Equation (1) – mid-depth in tension"
        else:
            eps_x_raw = eps_x_2
            eq_used = "Equation (2) – mid-depth in slight compression"

        # Apply code limits
        eps_x = max(-0.0002, min(eps_x_raw, 0.003))

        sign_note = (
            " (mid-depth in **tension**, εₓ ≥ 0)"
            if eps_x >= 0
            else " (mid-depth in **slight compression**, εₓ < 0)"
        )

        # ------------------------------
        #  Calc box with full Equation + substitution
        # ------------------------------
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

        calcbox(
            f"""
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

This value is **{"positive (tension at mid-depth)" if eps_x >= 0 else "negative (slight compression at mid-depth)"}** and is used in **Step 5** to compute $k_v$ and $\\theta_v$.
"""
        )

    with col_side:
        _safe_step_diagram(4)

    # High-level MCFT / Vuc / kv insight tied to εx
    st.markdown("---")
    render_shear_mcft_block()

    # =====================================================
    # 6. STEP 5 — k_v AND θ_v
    # =====================================================
    st.markdown("---")

    col_main, col_side = st.columns([3, 2])

    with col_main:
        col_title, col_info = st.columns([1, 0.08])

        with col_title:
            st.markdown("### Step 5 – Get MCFT shear parameters: $k_v$ and $\\theta_v$")

        with col_info:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown("### Step 5 – What $k_v$ and $\\theta_v$ mean")
                st.markdown(
                    r"""
**What \(k_v\) represents**



- \(k_v\) is a **concrete shear-transfer efficiency factor** in MCFT.  

- It wraps up:

  - Residual concrete shear across cracks,  

  - **Aggregate interlock**,  

  - **Dowel action** from longitudinal bars,  

  - Friction along the crack faces.  



- For members with at least minimum shear reinforcement:



  $$k_v = \frac{0.4}{1 + 1500\varepsilon_x}$$  



- With less than minimum shear reinforcement, extra modifiers account for **member depth** and **crack spacing**.



As \( \varepsilon_x \) increases, cracks widen and **\(k_v\)** drops, reducing the concrete contribution \(V_{uc}\).



**What \(\\theta_v\) represents**



- \(\\theta_v\) is the **angle of the diagonal compression strut** in the web.  

- AS 3600 uses:



  $$\\theta_v = 29^\circ + 7000\varepsilon_x$$  



  with limits of **15°–50°**.  



- Higher \(\\varepsilon_x\) → flatter stress field → **larger \(\\theta_v\)**.  



Both \(k_v\) and \(\\theta_v\) control:



- Concrete shear strength \(V_{uc}\), and  

- Steel shear contribution \(V_s\) through \( \cot\\theta_v \).

"""
                )

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

        theta_v_rad = math.radians(theta_v_deg)

        # For the summary text inside the calcbox
        Asv_over_s = Asv / s
        Asv_min_over_s = 0.08 * math.sqrt(fc) * b_v / (f_syv or 1.0)
        k_dg_display = locals().get("k_dg", float("nan"))

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

        calcbox(
            f"""
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
        )

    # =====================================================
    # 7. STEP 6 — CONCRETE SHEAR CONTRIBUTION V_uc ONLY
    # =====================================================
    st.markdown("---")

    col_main, col_side = st.columns([3, 2])

    with col_main:
        col_title, col_info = st.columns([1, 0.08])

        with col_title:
            st.markdown("### Step 6 – Concrete shear strength $V_{uc}$")

        with col_info:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown("### Step 6 – Concrete contribution $V_{uc}$")
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

        # Concrete contribution only
        sqrt_fc_limited = min(math.sqrt(fc), 8.0)
        Vuc_N = k_v * b_v * d_v * sqrt_fc_limited
        Vuc_kN = Vuc_N / 1e3

        calcbox(
            f"""
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
        )

    with col_side:
        _safe_step_diagram(6)

    # =====================================================
    # 8. STEP 7 — STEEL SHEAR CONTRIBUTION V_s
    # =====================================================
    st.markdown("---")

    col_main, col_side = st.columns([3, 2])

    with col_main:
        col_title, col_info = st.columns([1, 0.08])

        with col_title:
            st.markdown("### Step 7 – Steel shear strength $V_s$")

        with col_info:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown("### Step 7 – How stirrups contribute $V_s$")
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

        # Steel contribution only
        Vus_N = (Asv * f_syv * d_v / s) * cot(theta_v_rad)
        Vus_kN = Vus_N / 1e3

        calcbox(
            f"""
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

*(Concrete shear $V_{{uc}}$ was found in Step 6.)*

"""
        )

    with col_side:
        # Move the steel ligature diagram here
        _safe_image(
            "assets/shear_ligatures_and_crack.png",
            caption="Shear ligatures crossing a diagonal crack over $d_v \\cot\\theta_v$.",
        )

    # =====================================================
    # 9. STEP 8 — COMBINED SHEAR STRENGTH AND SECTIONAL CHECK
    # =====================================================
    st.markdown("---")

    col_main, col_side = st.columns([3, 2])

    with col_main:
        col_title, col_info = st.columns([1, 0.08])

        with col_title:
            st.markdown(
                "### Step 8 – Combine $V_{uc}$ and $V_s$ and compare with $V_{eq}^*$"
            )

        with col_info:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown("### Step 8 – Sectional shear check")
                st.markdown(
                    r"""
This step adds:



- **Concrete shear strength** $V_{uc}$ (Step 6), and  

- **Steel shear strength** $V_s$ (Step 7), plus any **axial/prestress $P_v$**  



to give the total shear resistance:



$$V_u = V_{uc} + V_s + P_v$$  



Then we check the design strength:



$$\phi V_u \ge V_{eq}^*$$  



If this inequality is satisfied, the **sectional shear capacity** is adequate before web crushing is checked in the next step.

"""
                )

        Vu_total_kN = Vuc_kN + Vus_kN + P_v
        phi_Vu = phi * Vu_total_kN
        shear_ok = phi_Vu >= V_eq

        calcbox(
            f"""
*Purpose: Combine concrete and steel contributions and check $\phi V_u$ against $V_{{eq}}^*$.*  



**Inputs:**  



- $V_{{uc}} = {Vuc_kN:,.1f}$ kN (from Step 6)  

- $V_s = {Vus_kN:,.1f}$ kN (from Step 7)  

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
        )

    with col_side:
        _safe_step_diagram(6)  # or a new combined diagram if you add one later

    # =====================================================
    # 10. STEP 9 — WEB CRUSHING CHECK
    # =====================================================
    st.markdown("---")

    col_main, col_side = st.columns([3, 2])

    with col_main:
        col_title, col_info = st.columns([1, 0.08])

        with col_title:
            st.markdown("### Step 9 – Check web-crushing strength (AS 3600 Cl. 8.2.6)")

        with col_info:
            with st.popover("ℹ️", use_container_width=True):
                st.markdown("### Step 9 – Web-crushing limit \(V_{u,\max}\)")
                st.markdown(
                    r"""
**Why we check web crushing**



- Even with a lot of shear reinforcement, the concrete web can only carry a finite **compression strut force**.  

- Once the diagonal concrete strut reaches its **crushing limit**, the failure is **sudden and brittle**.  



AS 3600 caps the design shear by a web-crushing limit:



$$V_{u,\max} = 0.55\, f'_c b_v d_v \frac{\cot\\theta_v + \cot\\theta_1}{1 + \cot^2\\theta_v} + P_v$$  



- If the combined shear + torsion demand exceeds this, **increasing stirrups does not help**.  

- You need to **change the geometry** (web thickness, depth, load position) or reduce the demand.



This step ensures the design stays within the **concrete web strength envelope**, not just the stirrup capacity.

"""
                )

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

        if not web_ok:
            st.error("Web-crushing limit exceeded – revise section/ligs.")

        calcbox(
        f"""
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
        )

    with col_side:
        _safe_step_diagram(7)

    # Steel contribution + lig spacing / detailing insights
    st.markdown("---")
    render_shear_steel_and_spacing_block()

    # =======================================================
    # 9. SUMMARY BANNER + PUSH RESULTS
    # =======================================================
    torsion_label = (
        "Yes (T* > 0.25 φT_cr)" if torsion_required else "No (strength check)"
    )

    shear_util = V_eq / phi_Vu if phi_Vu > 0 else float("nan")

    # Deflection-style summary table
    rows_summary = [
        {
            "Check": "Torsion considered?",
            "Value": torsion_label,
            "Limit": "",
            "Utilisation": "—",
            "Status": "—",
        },
        {
            "Check": "Equivalent design shear V_eq*",
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

    summary_df = pd.DataFrame(rows_summary)

    def _highlight_status(row):
        status = row.get("Status", "")
        if status == "OK":
            color = "#d9ead3"
        elif status in ("NG", "Check"):
            color = "#f4cccc"
        else:
            color = ""
        return [f"background-color: {color}"] * len(row)

    styled_summary = summary_df.style.apply(_highlight_status, axis=1)

    # Publish key shear results for Inputs summary
    update_results(
        phi_Vu_cap=phi_Vu,
        Vu_utilisation=shear_util if not math.isnan(shear_util) else 0.0,
    )

    with summary_placeholder.container():
        st.markdown("### Shear / Torsion – Summary")
        st.dataframe(styled_summary, use_container_width=True, hide_index=True)
        st.markdown("---")


if __name__ == "__main__":
    render_shear()
