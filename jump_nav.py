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
(function () {{
  const targetId = "calc_{uid}";
  let attempts = 0;

  // 🔹 1) optimistic scroll (immediate)
  window.parent.scrollTo({{ top: 0, behavior: "auto" }});

  function tryScroll() {{
    const el = window.parent.document.getElementById(targetId);
    if (el) {{
      el.scrollIntoView({{ behavior: "smooth", block: "start" }});
      el.style.transition = "background-color 0.4s ease";
      el.style.backgroundColor = "rgba(255,230,150,0.5)";
      setTimeout(() => el.style.backgroundColor = "", 700);
    }} else if (attempts < 25) {{
      attempts += 1;
      // Faster polling: 20ms for first 15 attempts, then 30ms for remaining
      const delay = attempts <= 15 ? 20 : 30;
      setTimeout(tryScroll, delay);
    }}
  }}

  // Start immediately, no initial delay
  tryScroll();
}})();
</script>
""",
        height=0,
    )

    st.session_state["jump_to"] = None
