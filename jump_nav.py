import streamlit as st


def get_jump_uid(param_name: str = "jump") -> str | None:
    """
    Reads ?jump=<uid>, stores it in st.session_state.jump_to, sets step_open_{uid} = True,
    then removes ONLY the 'jump' param (keeps routing params like page=...).
    """
    if "jump_to" not in st.session_state:
        st.session_state.jump_to = None
    
    jump = st.query_params.get(param_name)
    if isinstance(jump, list):
        jump = jump[0]
    
    if jump:
        uid = str(jump)
        st.session_state.jump_to = uid
        # Open the expander by setting step_open_{uid} = True
        st.session_state[f"step_open_{uid}"] = True
        
        # Remove ONLY the jump param; keep all other params (e.g., page routing)
        try:
            del st.query_params[param_name]
        except Exception:
            # fallback: rebuild params without jump
            params = dict(st.query_params)
            params.pop(param_name, None)
            st.query_params.clear()
            for k, v in params.items():
                st.query_params[k] = v
        
        return uid
    
    return st.session_state.jump_to


def scroll_to_jump_after_render(offset_px: int = 96, duration_ms: int = 850):
    """
    After rerun, scroll to <div id="calc_<uid>"></div> and flash it.
    """
    uid = st.session_state.get("jump_to")
    if not uid:
        return

    import streamlit.components.v1 as components
    
    components.html(
        f"""
<script>
(function() {{
  const targetId = "calc_{uid}";
  const startT = Date.now();
  const maxMs = 2500;
  const offset = {int(offset_px)};
  const duration = {int(duration_ms)};

  function easeInOutCubic(t) {{
    return t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3)/2;
  }}

  function animatedScrollTo(targetY) {{
    const doc = window.parent;
    const startY = doc.scrollY || doc.pageYOffset;
    const delta = targetY - startY;
    const t0 = performance.now();

    function step(now) {{
      const t = Math.min(1, (now - t0) / duration);
      const y = startY + delta * easeInOutCubic(t);
      doc.scrollTo(0, y);
      if (t < 1) requestAnimationFrame(step);
    }}
    requestAnimationFrame(step);
  }}

  function tryScroll() {{
    const doc = window.parent.document;
    const el = doc.getElementById(targetId);
    if (el) {{
      const rect = el.getBoundingClientRect();
      const absoluteY = (window.parent.scrollY || window.parent.pageYOffset) + rect.top - offset;

      // Run scroll a tiny bit later to let expand/collapse finish
      setTimeout(() => {{
        animatedScrollTo(absoluteY);
        el.classList.add("flash-target");
        setTimeout(() => el.classList.remove("flash-target"), 1200);
      }}, 90);

      return;
    }}

    if (Date.now() - startT < maxMs) {{
      setTimeout(tryScroll, 80);
    }}
  }}

  setTimeout(tryScroll, 120);
}})();
</script>
""",
        height=0,
    )

    st.session_state["jump_to"] = None
