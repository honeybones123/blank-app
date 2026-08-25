"""Minimum-strength Bending teaching checks."""

from __future__ import annotations

import math

from widgets_helpers import apply_step_expander_css, step_expander_calcbox

def render_minimum_strength_checks(top_results, b, D, fc, fsy, Ast, summary_mode: bool = False, jump_uid: str | None = None):
    """Minimum strength requirements (summary_mode parameter ignored, kept for compatibility)."""
    """
    Tab 2 â€“ Minimum strength requirements.
    
    Args:
        summary_mode: If True, all steps are collapsed (expanded=False)
        jump_uid: Deprecated - kept for compatibility, not used anymore
    """
    fctf = top_results["fctf"]
    Z_gross = top_results["Z_gross"]
    Mcr = top_results["Mcr"]
    As_min = top_results["As_min"]

    fctf_as = fctf
    Zg = Z_gross
    Mcr_as = Mcr
    Mu_min_as = (
        1.2 * Mcr_as
        if Mcr_as is not None and not math.isnan(Mcr_as)
        else float("nan")
    )
    Ast_min_as = As_min

    # Apply CSS for compact collapsed steps
    apply_step_expander_css()

    # 2.1 f_ct,f
    section21_details = f"""
*Purpose: Estimate the concrete flexural tensile strength $f_{{ct,f}}$.*  

**Inputs:**  

- $f'_c = {fc:.1f}$ MPa  

---

**Formula (AS 3600 style):**

$$
f_{{ct,f}} \\approx 0.6 \\sqrt{{f'_c}}
$$

**Substitution:**

$$
f_{{ct,f}} \\approx 0.6 \\sqrt{{{fc:.1f}}}
          = {fctf_as:.3f}\\ \\text{{MPa}}
$$

---

**Result:**  
$f_{{ct,f}} \\approx {fctf_as:.3f}$ MPa.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_1",
        summary_line=f"Check 1 — Concrete flexural tensile strength $f_{{ct,f}}$ | Result: f_{{ct,f}} = {fctf_as:.3f} MPa",
        details_md=section21_details,
        status=None,
        render_policy="mounted",
    )

    # 2.2 Z_g
    section22_details = f"""
*Purpose: Calculate the gross section modulus $Z_g$ of the rectangular section.*  

**Inputs:**  

- Width $b = {b:.1f}$ mm  
- Overall depth $D = {D:.1f}$ mm  

---

**Formula:**

$$
Z_g = \\frac{{b D^2}}{{6}}
$$

**Substitution:**

$$
Z_g = \\frac{{{b:.1f} \\times {D:.1f}^2}}{{6}}
    = {Zg:,.3e}\\ \\text{{mm}}^3
$$

---

**Result:**  
$Z_g = {Zg:,.3e}\\ \\text{{mm}}^3$.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_2",
        summary_line=f"Check 2 — Gross section modulus Z_g | Result: Z_g = {Zg:,.3e} mm^3",
        details_md=section22_details,
        status=None,
        render_policy="mounted",
    )

    # 2.3 M_cr
    section23_details = f"""
*Purpose: Determine the cracking moment $M_{{cr}}$ for the section.*  

**Inputs:**  

- $f_{{ct,f}} = {fctf_as:.3f}$ MPa  
- $Z_g = {Zg:,.3e}\\ \\text{{mm}}^3$  

---

**Formula:**

$$
M_{{cr}} = \\frac{{f_{{ct,f}} Z_g}}{{10^6}}
$$

**Substitution:**

$$
M_{{cr}} = \\frac{{{fctf_as:.3f} \\times {Zg:,.3e}}}{{10^6}}
       = {Mcr_as:.2f}\\ \\text{{kNm}}
$$

---

**Result:**  
$M_{{cr}} \\approx {Mcr_as:.2f}$ kNm.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_3",
        summary_line=f"Check 3 — Cracking moment $M_{{cr}}$ | Result: M_{{cr}} = {Mcr_as:.2f} kNm",
        details_md=section23_details,
        status=None,
        render_policy="mounted",
    )

    # 2.4 Minimum required capacity (1.2 Mcr) - PASS/FAIL
    phi_Mu_cap = top_results.get("phi_Mu_cap", 0.0)
    Mu_min_ok = phi_Mu_cap >= Mu_min_as if (phi_Mu_cap > 0 and Mu_min_as > 0) else None
    Mu_min_status = "pass" if Mu_min_ok is True else "fail" if Mu_min_ok is False else None
    
    section24_details = f"""
*Purpose: Check the minimum required design capacity relative to cracking moment.*  

**Inputs:**  

- $M_{{cr}} = {Mcr_as:.2f}$ kNm  
- $\\phi M_{{u,cap}} = {phi_Mu_cap:.2f}$ kNm

---

**Formula:**

$$
(M_{{u,cap}})_{{min}} = 1.2\\, M_{{cr}}
$$

**Substitution:**

$$
(M_{{u,cap}})_{{min}}
= 1.2 \\times {Mcr_as:.2f}
= {Mu_min_as:.2f}\\ \\text{{kNm}}
$$

---

**Check:**  
$\\phi M_{{u,cap}} = {phi_Mu_cap:.2f} \\ge {Mu_min_as:.2f} = (M_{{u,cap}})_{{min}}$ â†’ {"âœ“ PASS" if Mu_min_ok else "âœ— FAIL" if Mu_min_ok is False else "â€”"}

**Result:**  
Minimum required design capacity $(M_{{u,cap}})_{{min}} = {Mu_min_as:.2f}$ kNm.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_4",
        summary_line=f"Check 4 — Minimum required design capacity (M_u,cap)_min | Result: phi_Mu_cap = {phi_Mu_cap:.2f} kNm vs (M_u,cap)_min = {Mu_min_as:.2f} kNm -> {'PASS' if Mu_min_ok else 'FAIL' if Mu_min_ok is False else '-'}",
        details_md=section24_details,
        status=Mu_min_status,
        render_policy="mounted",
    )

    # 2.5 Minimum tensile reinforcement - PASS/FAIL
    As_ok = Ast >= Ast_min_as if (Ast is not None and Ast_min_as is not None and not math.isnan(Ast_min_as)) else None
    As_status = "pass" if As_ok is True else "fail" if As_ok is False else None
    
    section25_details = f"""
*Purpose: Calculate minimum tensile reinforcement according to AS 3600 style rules and check provided area.*  

**Inputs:**  

- $f_{{ct,f}} = {fctf_as:.3f}$ MPa  
- $f_{{sy}} = {fsy:.1f}$ MPa  
- $b = {b:.1f}$ mm  
- Effective depth $d = {top_results['d']:.1f}$ mm  
- Provided area: $A_{{st}} = {Ast:.1f}$ mm^2

---

**Formula:**

$$
A_{{st,min}}
= 0.4\\;\\frac{{f_{{ct,f}}}}{{f_{{sy}}}}\\; b d
$$

**Substitution:**

$$
A_{{st,min}}
= 0.4 \\times \\frac{{{fctf_as:.3f}}}{{{fsy:.1f}}}
\\times {b:.1f} \\times {top_results['d']:.1f}
= {Ast_min_as:.1f}\\ \\text{{mm}}^2
$$

---

**Check:**  
$A_{{st}} = {Ast:.1f} \\ge {Ast_min_as:.1f} = A_{{st,min}}$ â†’ {"âœ“ PASS" if As_ok else "âœ— FAIL" if As_ok is False else "â€”"}

**Result:**  
Minimum tensile steel area $A_{{st,min}} = {Ast_min_as:.1f}$ mm^2.
"""
    
    step_expander_calcbox(
        uid="bending_min_2_5",
        summary_line=f"Check 5 — Minimum tensile reinforcement A_st,min | Result: A_st = {Ast:.1f} mm^2 vs A_st,min = {Ast_min_as:.1f} mm^2 -> {'PASS' if As_ok else 'FAIL' if As_ok is False else '-'}",
        details_md=section25_details,
        status=As_status,
        render_policy="mounted",
    )
