🔧 Replace just this block in render_shear()

In your render_shear() function, find this bit near the top:

    # --- Layout row: intro text (left) + dv diagram (right) ---
    col_left, col_right = st.columns([1, 1])  # 50/50 split

    with col_left:
        st.markdown(
            r"""
This page evaluates **design shear**, **shear reinforcement**, and **torsion resistance**
...
        """
        )

    with col_right:
        _safe_image(
            "assets/shear_flexural_cracks_dv.png",
            caption=None,
        )


Delete that whole block and replace it with this:

    # --- Layout row: intro text (left) + smaller dv diagram (right with info) ---
    # Make the image column narrower so the diagram is ~half the previous size
    col_left, col_right = st.columns([2, 1])  # ~2/3 text, ~1/3 diagram

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
        # Put the drawing and info button on the same row
        img_col, info_col = st.columns([4, 1])

        with img_col:
            _safe_image(
                "assets/shear_flexural_cracks_dv.png",
                caption=None,
            )

        # Tiny info popover sitting beside the drawing
        with info_col:
            with st.popover("ℹ️", use_container_width=True):
                calcbox(
                    r"""
**What is shear and why at $d_v$?**



- Shear forces act **perpendicular to the beam axis** – like a stack of playing cards trying to slide.  
- In a beam, one part of the section wants to slide relative to the next, creating **internal shear stresses**.  

**Critical section for shear – $d_v$**

- Tests show peak **diagonal cracking** and shear demand occur at about **one effective depth $d_v$** from the support.  
- AS 3600 therefore takes the design shear at a distance **$d_v$ from the face of the support**,  
  ignoring any distributed load between the support and this section.  
- If significant point loads fall inside this region the behaviour is closer to a **deep beam / STM**, so a strut-and-tie model is required.  
- Effective shear depth is defined as  

  $$d_v = \max\left(0.72D,\;0.9d_0\right)$$  

  where $d_0$ is the depth to the centroid of the **tension reinforcement** in the tensile zone.
"""
                )

What this change does

col_left, col_right = st.columns([2, 1])
→ right column is now ~⅓ of the page, so the image is about half the size it was.

Nested img_col, info_col = st.columns([4, 1])
→ image takes most of that right column, with a slim info column for the ℹ️ button.

st.popover("ℹ️", ...)
→ the info tab sits right beside the drawing and opens your explanation inside a calcbox.

No extra heading above the image — only the main “Shear & Torsion” title + your text.

Reload the app after this change and the dv diagram should be smaller and have the info tab sitting on it like you wanted.

You said:
im happy with the column size i just wanted to shink the image a bit
ChatGPT said:
Thought for 9s

Gotcha – leave the columns as they are, just:

Make the image itself smaller

Put the ℹ️ popover back next to the drawing

Here’s exactly what to change.

1️⃣ Update _safe_image so it can shrink images

Right now it ignores the width argument.
Change it from:

def _safe_image(path: str, caption: str | None = None, width: int | None = None):
    """Tiny helper so missing images don't break the app."""
    if os.path.exists(path):
        st.image(path, caption=caption, use_container_width=True)
    else:
        st.info(f"💡 Add image file at `{path}` for: {caption or 'shear illustration'}")


to:

def _safe_image(path: str, caption: str | None = None, width: int | None = None):
    """Tiny helper so missing images don't break the app."""
    if os.path.exists(path):
        if width is not None:
            st.image(path, caption=caption, width=width)
        else:
            st.image(path, caption=caption, use_container_width=True)
    else:
        st.info(f"💡 Add image file at `{path}` for: {caption or 'shear illustration'}")


Everywhere else that calls _safe_image without width will behave the same as before.

2️⃣ Change just the intro dv block

In render_shear(), keep your col_left, col_right = st.columns([1, 1]) as is, but replace the with col_right: section with this:

    with col_right:
        # Image + info button in a small row
        img_col, info_col = st.columns([5, 1])

        with img_col:
            # shrink the image – tweak 300 → 280/320 to taste
            _safe_image(
                "assets/shear_flexural_cracks_dv.png",
                caption=None,
                width=300,
            )

        with info_col:
            with st.popover("ℹ️", use_container_width=True):
                calcbox(
                    r"""
**What is shear and why at $d_v$?**



- Shear forces act **perpendicular to the beam axis** – like a stack of playing cards trying to slide.  
- In a beam, one part of the section wants to slide relative to the next, creating **internal shear stresses**.  

**Critical section for shear – $d_v$**

- Tests show peak **diagonal cracking** and shear demand occur at about **one effective depth $d_v$** from the support.  
- AS 3600 therefore takes the design shear at a distance **$d_v$ from the face of the support**,  
  ignoring any distributed load between the support and this section.  
- If significant point loads fall inside this region the behaviour is closer to a **deep beam / STM**, so a strut-and-tie model is required.  
- Effective shear depth is defined as  

  $$d_v = \max\left(0.72D,\;0.9d_0\right)$$  

  where $d_0$ is the depth to the centroid of the **tension reinforcement** in the tensile zone.
"""
                )


Columns stay 50/50.

The dv image is now ~half the previous width (controlled by width=300).

The ℹ️ button sits right beside the drawing and opens the explanation.
