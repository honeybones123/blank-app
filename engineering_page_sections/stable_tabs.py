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


def preserve_scroll_for_preceding_widget(
    st_module: Any,
    *,
    scope_id: str,
) -> None:
    """Keep the main scroller fixed while a widget reruns its fragment."""

    scope = str(scope_id).strip()
    if not scope:
        raise ValueError("scope_id must be non-empty")

    import streamlit.components.v1 as components

    escaped_scope = html.escape(scope, quote=True)
    st_module.markdown(
        '<style>'
        'div[data-testid="stElementContainer"]:has([data-sb-widget-scroll-marker]){'
        'display:none!important;height:0!important;min-height:0!important;'
        'margin:0!important;padding:0!important;}'
        'div[data-testid="stElementContainer"]:has([data-sb-widget-scroll-marker])'
        '+div[data-testid="stElementContainer"]:has(iframe){'
        'display:none!important;height:0!important;min-height:0!important;'
        'margin:0!important;padding:0!important;}'
        '</style>'
        f'<span data-sb-widget-scroll-marker="{escaped_scope}" '
        'aria-hidden="true" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    components.html(
        f"""
        <script>
        (function () {{
          const doc = window.parent.document;
          const scope = {scope!r};
          const markerSelector = '[data-sb-widget-scroll-marker="' + scope + '"]';

          function tagWidget() {{
            const marker = doc.querySelector(markerSelector);
            if (!marker) return false;
            let node = marker.closest('[data-testid="stElementContainer"]');
            while (node && (node = node.previousElementSibling)) {{
              const group = node.matches?.('[role="radiogroup"]')
                ? node
                : node.querySelector?.('[role="radiogroup"]');
              if (group) {{
                group.dataset.sbStableWidgetScroll = scope;
                return true;
              }}
            }}
            return false;
          }}

          if (!tagWidget()) {{
            let attempts = 0;
            const tagTimer = window.parent.setInterval(function () {{
              attempts += 1;
              if (tagWidget() || attempts > 40) window.parent.clearInterval(tagTimer);
            }}, 50);
          }}

          function installParentRuntime() {{
            const pendingAttribute = 'data-sb-pending-widget-scroll';

            function holdPosition(pending) {{
              if (Date.now() >= pending.expires) {{
                document.documentElement.removeAttribute(pendingAttribute);
                return;
              }}
              const scroller = document.querySelector('section.stMain');
              if (scroller && Math.abs(scroller.scrollTop - pending.top) > 1) {{
                scroller.scrollTop = pending.top;
              }}
              window.requestAnimationFrame(function () {{
                holdPosition(pending);
              }});
            }}

            function snapshot(event) {{
              const group = event.target?.closest?.(
                '[data-sb-stable-widget-scroll]'
              );
              if (!group) return;
              // Avoid focusing a radio that Streamlit is about to remount.
              // The click event still changes the selected state.
              if (event.type === 'pointerdown') event.preventDefault();
              const scroller = document.querySelector('section.stMain');
              if (!scroller) return;
              const pending = {{
                scope: group.dataset.sbStableWidgetScroll,
                top: scroller.scrollTop,
                expires: Date.now() + 3500,
              }};
              document.documentElement.setAttribute(
                pendingAttribute,
                JSON.stringify(pending)
              );
              function lockScroll() {{
                if (
                  Date.now() < pending.expires &&
                  Math.abs(
                    (document.querySelector('section.stMain') || scroller).scrollTop -
                      pending.top
                  ) > 1
                ) {{
                  (document.querySelector('section.stMain') || scroller).scrollTop =
                    pending.top;
                }}
                const activeGroup = document.activeElement?.closest?.(
                  '[data-sb-stable-widget-scroll]'
                );
                if (activeGroup) document.activeElement.blur();
              }}
              scroller.addEventListener('scroll', lockScroll, {{ passive: true }});
              const mutationGuard = new MutationObserver(lockScroll);
              mutationGuard.observe(document.body, {{ childList: true, subtree: true }});
              window.setTimeout(function () {{
                scroller.removeEventListener('scroll', lockScroll);
                mutationGuard.disconnect();
              }}, 3600);
              holdPosition(pending);
            }}

            document.addEventListener('pointerdown', snapshot, true);
            document.addEventListener('keydown', function (event) {{
              if (event.key === 'Enter' || event.key === ' ') snapshot(event);
            }}, true);
          }}

          // Install the listener in the parent document's JavaScript realm so
          // it survives removal of this component iframe during a fragment rerun.
          const runtimeId = 'sb-stable-widget-scroll-runtime';
          if (!doc.getElementById(runtimeId)) {{
            const runtime = doc.createElement('script');
            runtime.id = runtimeId;
            runtime.textContent = '(' + installParentRuntime.toString() + ')();';
            doc.head.appendChild(runtime);
          }}
        }})();
        </script>
        """,
        height=0,
    )


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
    "preserve_scroll_for_preceding_widget",
    "render_stable_tabs",
    "synchronize_stable_tab_scopes",
]
