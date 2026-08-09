import json

import streamlit as st

from ui.streamlit_iframe import render_trusted_iframe

# Session key: Streamlit tab label to activate before scrolling (cross-page jump only).
JUMP_NAV_TAB_KEY = "_jump_nav_tab"


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
            # fallback: do not clear routing params in page code
            pass

        return uid

    return st.session_state.jump_to


def scroll_to_jump_after_render(offset_px: int = 96, duration_ms: int = 850):
    """
    After rerun, optionally switch Streamlit tab (cross-page handoff), then scroll to
    <div id="calc_<uid>"></div> and flash it.

    Pages may set st.session_state[JUMP_NAV_TAB_KEY] to a tab button label (e.g. \"ULS Checks\")
    so anchors inside inactive tabs exist in the DOM before scroll.
    """
    uid = st.session_state.get("jump_to")
    if not uid:
        return

    tab_label = st.session_state.pop(JUMP_NAV_TAB_KEY, None)
    tab_json = json.dumps(str(tab_label)) if tab_label else "null"

    uid_json = json.dumps(str(uid))

    render_trusted_iframe(st,
        f"""
<script>
(function () {{
  const doc = window.top.document;
  const tabName = {tab_json};
  const targetId = "calc_" + {uid_json};
  let attempts = 0;

  function findByIdUnderNode(root, id) {{
    function walk(n) {{
      if (!n) return null;
      if (n.nodeType === 1 && n.id === id) return n;
      if (n.children) {{
        for (const ch of n.children) {{
          const r = walk(ch);
          if (r) return r;
        }}
      }}
      if (n.shadowRoot) {{
        for (const ch of n.shadowRoot.children) {{
          const r = walk(ch);
          if (r) return r;
        }}
      }}
      return null;
    }}
    return walk(root);
  }}

  function getElementByIdDeepDoc(d, id) {{
    let el = findByIdUnderNode(d.documentElement, id);
    if (el) return el;
    const frames = d.querySelectorAll("iframe");
    for (let i = 0; i < frames.length; i++) {{
      try {{
        const idoc = frames[i].contentDocument;
        if (idoc) {{
          el = getElementByIdDeepDoc(idoc, id);
          if (el) return el;
        }}
      }} catch (e) {{}}
    }}
    return null;
  }}

  function switchToTab(name) {{
    if (!name) return Promise.resolve();
    const tabButtons = doc.querySelectorAll('button[data-baseweb="tab"]');
    for (const button of tabButtons) {{
      if (button.textContent.trim() === name) {{
        if (button.getAttribute("aria-selected") !== "true") {{
          button.click();
          return new Promise(function (resolve) {{ setTimeout(resolve, 350); }});
        }}
        return Promise.resolve();
      }}
    }}
    const radios = doc.querySelectorAll('input[type="radio"]');
    for (const radio of radios) {{
      const label = radio.closest("label") || radio.parentElement && radio.parentElement.querySelector("label");
      if (label && label.textContent.trim() === name) {{
        if (!radio.checked) {{
          radio.click();
          return new Promise(function (resolve) {{ setTimeout(resolve, 350); }});
        }}
        return Promise.resolve();
      }}
    }}
    return Promise.resolve();
  }}

  window.top.scrollTo({{ top: 0, behavior: "auto" }});

  function tryScroll() {{
    const el = getElementByIdDeepDoc(doc, targetId);
    if (el) {{
      el.scrollIntoView({{ behavior: "smooth", block: "start" }});
      el.style.transition = "background-color 0.4s ease";
      el.style.backgroundColor = "rgba(255,230,150,0.5)";
      setTimeout(function () {{ el.style.backgroundColor = ""; }}, 700);
    }} else if (attempts < 40) {{
      attempts += 1;
      const delay = attempts <= 20 ? 25 : 50;
      setTimeout(tryScroll, delay);
    }}
  }}

  switchToTab(tabName).then(function () {{ tryScroll(); }});
}})();
</script>
""",
        height=0,
    )

    st.session_state["jump_to"] = None
