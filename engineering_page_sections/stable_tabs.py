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

    # This is deliberately a single document-level listener.  It never writes
    # a widget key or triggers a Streamlit rerun.  Capturing the position on
    # pointer-down (rather than click) matters: browser focus may otherwise
    # scroll the selected tab into view before the click handler can preserve
    # the original main-frame position.
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
            '}}',
            '[data-sb-plotly-visibility-ready="1"] .scatterlayer .trace[data-sb-plotly-state],',
            '[data-sb-plotly-visibility-ready="1"] g.shapelayer .shape-group[data-sb-plotly-state],',
            '[data-sb-plotly-visibility-ready="1"] .annotation[data-sb-plotly-state] {{',
            ' opacity: 0 !important;',
            '}}',
            '[data-sb-plotly-visibility-ready="1"][data-sb-preloaded-plotly-state="0"] .scatterlayer .trace[data-sb-plotly-state="0"],',
            '[data-sb-plotly-visibility-ready="1"][data-sb-preloaded-plotly-state="0"] g.shapelayer .shape-group[data-sb-plotly-state="0"],',
            '[data-sb-plotly-visibility-ready="1"][data-sb-preloaded-plotly-state="0"] .annotation[data-sb-plotly-state="0"],',
            '[data-sb-plotly-visibility-ready="1"][data-sb-preloaded-plotly-state="1"] .scatterlayer .trace[data-sb-plotly-state="1"],',
            '[data-sb-plotly-visibility-ready="1"][data-sb-preloaded-plotly-state="1"] g.shapelayer .shape-group[data-sb-plotly-state="1"],',
            '[data-sb-plotly-visibility-ready="1"][data-sb-preloaded-plotly-state="1"] .annotation[data-sb-plotly-state="1"],',
            '[data-sb-plotly-visibility-ready="1"][data-sb-preloaded-plotly-state="2"] .scatterlayer .trace[data-sb-plotly-state="2"],',
            '[data-sb-plotly-visibility-ready="1"][data-sb-preloaded-plotly-state="2"] g.shapelayer .shape-group[data-sb-plotly-state="2"],',
            '[data-sb-plotly-visibility-ready="1"][data-sb-preloaded-plotly-state="2"] .annotation[data-sb-plotly-state="2"] {{',
            ' opacity: 1 !important;',
            '}}'
          ].join('');
          doc.head.appendChild(style);

          function isNativeTab(target) {{
            const tab = target && target.closest
              ? target.closest('[role="tab"]')
              : null;
            return Boolean(tab);
          }}

          function snapshotTab(event) {{
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
            if (tabset) {{
              window.parent.setTimeout(function () {{
                delete tabset.dataset.sbStablePanelHeight;
                tabset.style.removeProperty('--sb-stable-panel-height');
                const activePlot = tabset.querySelector(
                  '[role="tabpanel"] .js-plotly-plot'
                );
                const plotly = window.parent.Plotly || window.Plotly;
                if (
                  activePlot
                  && plotly
                  && plotly.Plots
                  && typeof plotly.Plots.resize === 'function'
                ) {{
                  plotly.Plots.resize(activePlot);
                }}
              }}, 800);
            }}
          }}

          function tagWidgetMarkers() {{
            doc.querySelectorAll('[data-sb-widget-scroll-marker]').forEach(function (marker) {{
              const scope = marker.getAttribute('data-sb-widget-scroll-marker');
              const plotlyVisibilityScope = marker.getAttribute(
                'data-sb-widget-target-plotly-visibility'
              );
              let node = marker.closest('[data-testid="stElementContainer"]');
              while (node && (node = node.previousElementSibling)) {{
                const group = node.matches?.('[role="radiogroup"]')
                  ? node
                  : node.querySelector?.('[role="radiogroup"]');
                if (group) {{
                  group.dataset.sbStableWidgetScroll = scope;
                  if (plotlyVisibilityScope) {{
                    group.dataset.sbTargetPlotlyVisibility = plotlyVisibilityScope;
                    scheduleCurrentPlotlyVisibility(group);
                  }}
                  break;
                }}
              }}
            }});
          }}

          const pendingAttribute = 'data-sb-pending-widget-scroll';
          function switchPreloadedPlotlyVisibility(group, requestedIndex, recordTiming) {{
            const scope = group.dataset.sbTargetPlotlyVisibility;
            if (!scope) return;
            const marker = doc.querySelector(
              '[data-sb-plotly-visibility-scope="' + CSS.escape(scope) + '"]'
            );
            if (!marker) return;
            let node = marker.closest('[data-testid="stElementContainer"]');
            let plot = null;
            while (node && !plot && (node = node.nextElementSibling)) {{
              plot = node.querySelector?.('.js-plotly-plot') || null;
            }}
            if (!plot) return;
            const counts = function (name) {{
              return (marker.getAttribute(name) || '').split(',').map(Number);
            }};
            const stateForLayoutIndex = function (layoutIndex, groupCounts) {{
              let offset = 0;
              for (let groupIndex = 0; groupIndex < groupCounts.length; groupIndex += 1) {{
                offset += groupCounts[groupIndex];
                if (layoutIndex < offset) return groupIndex;
              }}
              return -1;
            }};
            const tagIndexedGroup = function (nodes, groupCounts) {{
              nodes.forEach(function (node, fallbackIndex) {{
                const parsedIndex = Number(node.getAttribute('data-index'));
                const layoutIndex = Number.isFinite(parsedIndex) ? parsedIndex : fallbackIndex;
                const groupIndex = stateForLayoutIndex(layoutIndex, groupCounts);
                node.dataset.sbPlotlyState = String(groupIndex);
              }});
            }};
            const tagTraceGroup = function (nodes) {{
              const stateOrder = (marker.getAttribute(
                'data-sb-trace-state-order'
              ) || '').split(',').map(Number);
              nodes.forEach(function (node, domIndex) {{
                node.dataset.sbPlotlyState = String(stateOrder[domIndex]);
              }});
            }};
            const started = window.parent.performance.now();
            const traceNodes = [...plot.querySelectorAll('.scatterlayer .trace')];
            const shapeNodes = [...plot.querySelectorAll('g.shapelayer .shape-group')];
            const annotationNodes = [...plot.querySelectorAll('.annotation')];
            const visibilityNodes = traceNodes.concat(shapeNodes, annotationNodes);
            if (
              plot.dataset.sbPlotlyVisibilityTagged !== '1'
              || visibilityNodes.some(node => !node.hasAttribute('data-sb-plotly-state'))
            ) {{
              tagTraceGroup(traceNodes);
              tagIndexedGroup(
                shapeNodes,
                counts('data-sb-shape-groups')
              );
              tagIndexedGroup(
                annotationNodes,
                counts('data-sb-annotation-groups')
              );
              plot.dataset.sbPlotlyVisibilityTagged = '1';
            }}
            const taggingComplete = visibilityNodes.length > 0 && visibilityNodes.every(
              function (node) {{
                const state = Number(node.getAttribute('data-sb-plotly-state'));
                return Number.isInteger(state) && state >= 0 && state <= 2;
              }}
            );
            if (!taggingComplete) {{
              plot.removeAttribute('data-sb-plotly-visibility-ready');
              return;
            }}
            plot.setAttribute('data-sb-preloaded-plotly-state', String(requestedIndex));
            plot.setAttribute('data-sb-plotly-visibility-ready', '1');
            const plotly = window.parent.Plotly || window.Plotly;
            if (plotly && plotly.Plots && typeof plotly.Plots.resize === 'function') {{
              window.parent.requestAnimationFrame(function () {{
                plotly.Plots.resize(plot);
              }});
            }}
            if (recordTiming) {{
              window.parent.requestAnimationFrame(function () {{
                doc.documentElement.setAttribute(
                  'data-sb-last-plotly-visibility-switch-ms',
                  String(window.parent.performance.now() - started)
                );
              }});
            }}
          }}
          function scheduleCurrentPlotlyVisibility(group) {{
            if (group.dataset.sbPlotlyVisibilityPending === '1') return;
            group.dataset.sbPlotlyVisibilityPending = '1';
            window.parent.requestAnimationFrame(function () {{
              delete group.dataset.sbPlotlyVisibilityPending;
              const radios = [...group.querySelectorAll('input[type="radio"]')];
              const requestedIndex = radios.findIndex(function (radio) {{
                return radio.checked;
              }});
              if (requestedIndex >= 0) {{
                switchPreloadedPlotlyVisibility(group, requestedIndex, false);
              }}
            }});
          }}
          function holdPosition(pending) {{
            if (Date.now() >= pending.expires) {{
              doc.documentElement.removeAttribute(pendingAttribute);
              return;
            }}
            const scroller = doc.querySelector('section.stMain');
            if (scroller && Math.abs(scroller.scrollTop - pending.top) > 1) {{
              scroller.scrollTop = pending.top;
            }}
            window.parent.requestAnimationFrame(function () {{ holdPosition(pending); }});
          }}

          function snapshotWidget(event) {{
            const group = event.target?.closest?.('[data-sb-stable-widget-scroll]');
            if (!group) return;
            const radios = [...group.querySelectorAll('input[type="radio"]')];
            const radio = event.target?.closest?.('label')?.querySelector?.(
              'input[type="radio"]'
            ) || event.target?.closest?.('input[type="radio"]');
            const requestedIndex = radios.indexOf(radio);
            if (requestedIndex >= 0) {{
              switchPreloadedPlotlyVisibility(group, requestedIndex, true);
            }}
            const scroller = doc.querySelector('section.stMain');
            if (!scroller) return;
            const pending = {{
              scope: group.dataset.sbStableWidgetScroll,
              top: scroller.scrollTop,
              expires: Date.now() + 3500,
            }};
            doc.documentElement.setAttribute(pendingAttribute, JSON.stringify(pending));
            function lockScroll() {{
              if (Date.now() < pending.expires) {{
                const activeScroller = doc.querySelector('section.stMain') || scroller;
                if (Math.abs(activeScroller.scrollTop - pending.top) > 1) {{
                  activeScroller.scrollTop = pending.top;
                }}
              }}
              const activeGroup = doc.activeElement?.closest?.(
                '[data-sb-stable-widget-scroll]'
              );
              if (activeGroup) doc.activeElement.blur();
            }}
            scroller.addEventListener('scroll', lockScroll, {{ passive: true }});
            const mutationGuard = new MutationObserver(lockScroll);
            mutationGuard.observe(doc.body, {{ childList: true, subtree: true }});
            window.parent.setTimeout(function () {{
              scroller.removeEventListener('scroll', lockScroll);
              mutationGuard.disconnect();
            }}, 3600);
            holdPosition(pending);
          }}

          tagWidgetMarkers();
          const widgetMarkerObserver = new MutationObserver(tagWidgetMarkers);
          widgetMarkerObserver.observe(doc.body, {{ childList: true, subtree: true }});

          doc.addEventListener('pointerdown', function (event) {{
            snapshotTab(event);
            snapshotWidget(event);
          }}, true);
          doc.addEventListener('keydown', function (event) {{
            if (event.key === 'Enter' || event.key === ' ') {{
              snapshotTab(event);
              snapshotWidget(event);
            }}
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


def preserve_scroll_for_preceding_widget(
    st_module: Any,
    *,
    scope_id: str,
    target_plotly_visibility_scope_id: str | None = None,
) -> None:
    """Keep the main scroller fixed while a widget reruns its fragment."""

    scope = str(scope_id).strip()
    if not scope:
        raise ValueError("scope_id must be non-empty")

    escaped_scope = html.escape(scope, quote=True)
    plotly_visibility_attribute = ""
    if target_plotly_visibility_scope_id is not None:
        visibility_scope = str(target_plotly_visibility_scope_id).strip()
        if not visibility_scope:
            raise ValueError(
                "target_plotly_visibility_scope_id must be non-empty when provided"
            )
        plotly_visibility_attribute = (
            ' data-sb-widget-target-plotly-visibility="'
            + html.escape(visibility_scope, quote=True)
            + '"'
        )
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
        f'<span data-sb-widget-scroll-marker="{escaped_scope}"'
        f'{plotly_visibility_attribute} '
        'aria-hidden="true" style="display:none"></span>',
        unsafe_allow_html=True,
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
