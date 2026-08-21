"""Shared native tab boundary for engineering result pages.

Tabs are presentation state only.  They must not own engineering state, invoke
page callbacks, or cause a server rerun merely because the visible panel
changes.  The helper intentionally mirrors the Bending page's proven native
``st.tabs`` structure and preserves the main Streamlit scroller while a tab
panel with a different height is selected.
"""

from __future__ import annotations

from collections.abc import Sequence
import html
from typing import Any


def render_stable_tabs(
    st_module: Any,
    *,
    labels: Sequence[str],
    scope_id: str,
    install_runtime: bool = True,
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

    # One document-level listener serves every explicitly marked stable tabset.
    # It never owns engineering state or keeps the page pinned. Any pending
    # correction is one-shot and yields immediately to user scroll intent.
    if install_runtime:
        import streamlit.components.v1 as components

        components.html(
        f"""
        <script>
        (function () {{
          const doc = window.parent.document;
          const listenerKey = "__sbStableInteractionRuntime";
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

          function tabsetAfterMarker(marker) {{
            let node = marker.closest('[data-testid="stElementContainer"]');
            while (node && (node = node.nextElementSibling)) {{
              const tabset = node.matches?.('[data-testid="stTabs"]')
                ? node
                : node.querySelector?.('[data-testid="stTabs"]');
              if (tabset) return tabset;
            }}
            return null;
          }}

          function tagStableTabsets() {{
            doc.querySelectorAll('[data-sb-tab-scope]').forEach(function (marker) {{
              const scope = marker.getAttribute('data-sb-tab-scope');
              const tabset = tabsetAfterMarker(marker);
              if (scope && tabset) tabset.dataset.sbTabScope = scope;
            }});
          }}

          function stableTabFor(target) {{
            const tab = target && target.closest
              ? target.closest('[role="tab"]')
              : null;
            const tabset = tab?.closest?.('[data-testid="stTabs"]');
            return tabset?.dataset?.sbTabScope ? {{ tab, tabset }} : null;
          }}

          let pendingTabRestore = null;

          function cancelPendingScrollPreservation() {{
            if (pendingTabRestore) pendingTabRestore.cancelled = true;
            pendingTabRestore = null;
          }}

          function resizeActivePlot(tabset) {{
            const activePlot = tabset?.querySelector(
              '[role="tabpanel"] .js-plotly-plot'
            );
            const plotly = window.parent.Plotly || window.Plotly;
            if (
              activePlot
              && plotly?.Plots
              && typeof plotly.Plots.resize === 'function'
            ) plotly.Plots.resize(activePlot);
          }}

          function snapshotTab(event) {{
            const stable = stableTabFor(event.target);
            if (!stable) return;
            const scroller = doc.querySelector('section.stMain');
            if (!scroller) return;
            const tabset = stable.tabset;
            const activePanel = tabset && tabset.querySelector('[role="tabpanel"]');
            if (tabset && activePanel) {{
              const panelHeight = Math.ceil(activePanel.getBoundingClientRect().height);
              tabset.dataset.sbStablePanelHeight = String(panelHeight);
              tabset.style.setProperty('--sb-stable-panel-height', panelHeight + 'px');
            }}
            pendingTabRestore = {{
              scroller: scroller,
              top: scroller.scrollTop,
              cancelled: false,
            }};
            window.parent.requestAnimationFrame(function () {{
              const pending = pendingTabRestore;
              pendingTabRestore = null;
              if (
                pending
                && !pending.cancelled
                && Math.abs(pending.scroller.scrollTop - pending.top) > 1
              ) pending.scroller.scrollTop = pending.top;
              window.parent.setTimeout(function () {{
                delete tabset.dataset.sbStablePanelHeight;
                tabset.style.removeProperty('--sb-stable-panel-height');
                resizeActivePlot(tabset);
              }}, 120);
            }});
          }}

          tagStableTabsets();
          const stableMarkerObserver = new MutationObserver(function () {{
            tagStableTabsets();
          }});
          stableMarkerObserver.observe(doc.body, {{ childList: true, subtree: true }});

          doc.addEventListener('wheel', cancelPendingScrollPreservation, {{
            capture: true,
            passive: true,
          }});
          doc.addEventListener('touchmove', cancelPendingScrollPreservation, {{
            capture: true,
            passive: true,
          }});

          doc.addEventListener('pointerdown', function (event) {{
            snapshotTab(event);
          }}, true);
          doc.addEventListener('keydown', function (event) {{
            if (event.key === 'Enter' || event.key === ' ') {{
              snapshotTab(event);
              return;
            }}
            if ([
              'PageDown', 'PageUp', 'ArrowDown', 'ArrowUp', 'Home', 'End'
            ].includes(event.key)) cancelPendingScrollPreservation();
          }}, true);
        }})();
        </script>
        """,
        height=0,
        )
    else:
        # The legacy zero-height component still occupied one Streamlit stack
        # slot. Preserve that exact blank allocation while reusing the shared
        # browser runtime so page geometry remains pixel-compatible.
        st_module.markdown(
            '<div data-sb-runtime-layout-slot aria-hidden="true" '
            'style="height:0;line-height:0">&#8203;</div>',
            unsafe_allow_html=True,
        )
    st_module.markdown(
        '<style>'
        'div[data-testid="stElementContainer"]:has([data-sb-tab-scope]){'
        'display:none!important;height:0!important;min-height:0!important;'
        'margin:0!important;padding:0!important;}'
        '</style>'
        f'<span data-sb-tab-scope="{html.escape(scope_id, quote=True)}" '
        'aria-hidden="true" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    return tuple(st_module.tabs(tab_labels))


def synchronize_stable_tab_scopes(
    st_module: Any,
    *,
    source_scope_id: str,
    target_scope_id: str,
    hide_target_tablist: bool = True,
    storage_key: str | None = None,
) -> None:
    """Synchronize two already-mounted native tab groups in the browser.

    The source tab group remains the user-facing selector. The target group is
    presentation-only and follows it without writing Streamlit widget state or
    requesting a Python rerun. This keeps one selector positioned independently
    from the panel it controls while preserving native tab accessibility.
    """

    source = str(source_scope_id).strip()
    target = str(target_scope_id).strip()
    if not source or not target:
        raise ValueError("source_scope_id and target_scope_id must be non-empty")
    persisted_key = storage_key or f"sb-tab-sync::{source}::{target}"

    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
        (function () {{
          const doc = window.parent.document;
          const sourceScope = {source!r};
          const targetScope = {target!r};
          const storageKey = {persisted_key!r};

          function tabsetFor(scope) {{
            const marker = doc.querySelector('[data-sb-tab-scope="' + scope + '"]');
            if (!marker) return null;
            let node = marker.closest('[data-testid="stElementContainer"]');
            while (node && (node = node.nextElementSibling)) {{
              const tabset = node.matches?.('[data-testid="stTabs"]')
                ? node
                : node.querySelector?.('[data-testid="stTabs"]');
              if (tabset) {{
                tabset.dataset.sbTabScope = scope;
                return tabset;
              }}
            }}
            return null;
          }}

          function install() {{
            const sourceTabs = tabsetFor(sourceScope);
            const targetTabs = tabsetFor(targetScope);
            if (!sourceTabs || !targetTabs) return false;
            const sourceButtons = [...sourceTabs.querySelectorAll('[role="tab"]')];
            const targetButtons = [...targetTabs.querySelectorAll('[role="tab"]')];
            if (!sourceButtons.length || sourceButtons.length !== targetButtons.length) return false;

            if ({str(bool(hide_target_tablist)).lower()}) {{
              const targetList = targetTabs.querySelector('[role="tablist"]');
              if (targetList) targetList.style.display = 'none';
            }}

            function select(index, persist) {{
              const safe = Math.max(0, Math.min(index, targetButtons.length - 1));
              if (targetButtons[safe].getAttribute('aria-selected') !== 'true') {{
                targetButtons[safe].click();
              }}
              if (persist) window.parent.sessionStorage.setItem(storageKey, String(safe));
            }}

            sourceButtons.forEach((button, index) => {{
              if (button.dataset.sbSyncInstalled === targetScope) return;
              button.dataset.sbSyncInstalled = targetScope;
              button.addEventListener('click', () => select(index, true));
              button.addEventListener('keydown', (event) => {{
                if (event.key === 'Enter' || event.key === ' ') select(index, true);
              }});
            }});

            const stored = Number(window.parent.sessionStorage.getItem(storageKey));
            const initial = Number.isInteger(stored) ? stored : 0;
            if (sourceButtons[initial] && sourceButtons[initial].getAttribute('aria-selected') !== 'true') {{
              sourceButtons[initial].click();
            }}
            select(initial, false);
            return true;
          }}

          if (!install()) {{
            let attempts = 0;
            const timer = window.parent.setInterval(() => {{
              attempts += 1;
              if (install() || attempts > 40) window.parent.clearInterval(timer);
            }}, 50);
          }}
        }})();
        </script>
        """,
        height=0,
    )


__all__ = [
    "render_stable_tabs",
    "synchronize_stable_tab_scopes",
]
