"""Shared native tab boundary for engineering result pages.

Tabs are presentation state only.  They must not own engineering state, invoke
page callbacks, or cause a server rerun merely because the visible panel
changes.  The helper intentionally mirrors the Bending page's proven native
``st.tabs`` structure and preserves the main Streamlit scroller while a tab
panel with a different height is selected.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def render_stable_tabs(
    st_module: Any,
    *,
    labels: Sequence[str],
    scope_id: str,
) -> tuple[Any, ...]:
    """Render local native tabs that keep the main frame at its current position.

    ``scope_id`` is a stable presentation identifier only.  It does not enter
    the engineering snapshot or session-state authority.
    """

    tab_labels = tuple(str(label) for label in labels)
    if not tab_labels:
        raise ValueError("labels must contain at least one tab")
    if not scope_id.strip():
        raise ValueError("scope_id must be non-empty")

    # This is deliberately a single document-level listener.  It never writes
    # a widget key or triggers a Streamlit rerun.  Capturing the position on
    # pointer-down (rather than click) matters: browser focus may otherwise
    # scroll the selected tab into view before the click handler can preserve
    # the original main-frame position.
    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
        (function () {{
          const doc = window.parent.document;
          const listenerKey = "__sbStableTabScrollListener";
          if (doc[listenerKey]) return;
          doc[listenerKey] = true;

          const style = doc.createElement('style');
          style.textContent = [
            '[data-testid="stTabs"][data-sb-stable-panel-height]',
            ' [role="tabpanel"] {{',
            ' min-height: var(--sb-stable-panel-height) !important;',
            '}}'
          ].join('');
          doc.head.appendChild(style);

          function isNativeTab(target) {{
            const tab = target && target.closest
              ? target.closest('[role="tab"]')
              : null;
            return Boolean(tab);
          }}

          function snapshot(event) {{
            if (!isNativeTab(event.target)) return;
            const scroller = doc.querySelector('section.stMain');
            if (!scroller) return;
            const tabset = event.target.closest('[data-testid="stTabs"]');
            const activePanel = tabset && tabset.querySelector('[role="tabpanel"]');
            if (tabset && activePanel) {{
              const panelHeight = Math.ceil(activePanel.getBoundingClientRect().height);
              tabset.dataset.sbStablePanelHeight = String(panelHeight);
              tabset.style.setProperty('--sb-stable-panel-height', panelHeight + 'px');
            }}
            const before = scroller.scrollTop;
            [0, 50, 150, 350, 750].forEach(function (delay) {{
              window.parent.setTimeout(function () {{
                if (Math.abs(scroller.scrollTop - before) > 1) {{
                  scroller.scrollTop = before;
                }}
              }}, delay);
            }});
          }}

          doc.addEventListener('pointerdown', snapshot, true);
          doc.addEventListener('keydown', function (event) {{
            if (event.key === 'Enter' || event.key === ' ') {{
              snapshot(event);
            }}
          }}, true);
        }})();
        </script>
        """,
        height=0,
    )
    return tuple(st_module.tabs(tab_labels))


__all__ = ["render_stable_tabs"]
