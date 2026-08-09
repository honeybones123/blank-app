import html as html_stdlib
import streamlit as st

from ui.streamlit_iframe import render_trusted_iframe

from engineering_check_ui import (
    ENGINEERING_CHECK_COLUMNS,
    resolve_jump_target_id,
    summary_cell_display,
)
from ui.summary_sections import (
    SUMMARY_DASH as _shared_summary_dash,
    build_final_summary_check_card_html as _shared_build_final_summary_check_card_html,
    build_final_summary_check_card_model as _shared_build_final_summary_check_card_model,
    build_summary_check_card_html as _shared_build_summary_check_card_html,
    normalise_summary_display_value as _shared_normalise_summary_display_value,
    render_clickable_summary_table as _shared_render_clickable_summary_table,
    summary_card_css as _shared_summary_card_css,
)


def inject_seamless_steps_css():
    st.markdown(
        """
<style>
/* flash animation */
@keyframes flash {
  0% { box-shadow: none; }
  15% { box-shadow: 0 0 0 6px rgba(255,193,7,0.6); }
  100% { box-shadow: none; }
}
.flash-target {
  animation: flash 1.25s ease-in-out 1;
  border-radius: 8px;
}

/* step wrapper spacing */
.step-wrap { margin: 10px 0; }

/* Make scroll land nicely below the header */
[id^="calc_"] {
  scroll-margin-top: 96px;
}

/* expander styling to match test app */
div[data-testid="stExpander"] {
  margin: 0.15rem 0 !important;
}

div[data-testid="stExpander"] details {
  border: 1px solid rgba(49,51,63,0.15) !important;
  border-radius: 10px !important;
  overflow: hidden !important;
}

div[data-testid="stExpander"] summary {
  background: rgba(49,51,63,0.03) !important;
  padding: 0.65rem 0.85rem !important;
  font-weight: 600 !important;
  cursor: pointer;
}

div[data-testid="stExpander"] .stMarkdown,
div[data-testid="stExpander"] .stAlert {
  padding-left: 0.85rem !important;
  padding-right: 0.85rem !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_clickable_summary_table_legacy(rows, key_prefix="summary", columns=None):
    """
    Render summary table matching the test app style.
    Uses HTML table with clickable row links.
    """
    st.markdown("""
<style>
.summary-wrap {
  border: 1px solid rgba(49,51,63,0.15);
  border-radius: 10px;
  overflow: hidden;
}

.summary-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 16px;
}

.summary-table th {
  background: rgba(49,51,63,0.05);
  text-align: left;
  padding: 14px;
  color: rgba(49,51,63,0.7);
}

.summary-table td {
  padding: 14px;
  border-top: 1px solid rgba(49,51,63,0.1);
  position: relative;
}

/* Default neutral background (matches calcbox blue) - only for rows without pass/fail/warn classes */
.summary-table tbody tr:not(.pass):not(.fail):not(.warn) td {
  background: rgba(31, 119, 180, 0.08);
}

tr.pass td { background: rgba(0,128,0,0.12); }
tr.fail td { background: rgba(255,0,0,0.12); }
tr.warn td { background: rgba(255,193,7,0.15); }

tr.primary td {
  font-weight: 700;
}

tr:hover td { background: rgba(0,0,0,0.04); }

.row-link {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: block;
  cursor: pointer;
}

.hint {
  opacity: 0;
  font-size: 0.9em;
  margin-left: 6px;
  color: rgba(49,51,63,0.6);
}
tr:hover .hint { opacity: 1; }
</style>
""", unsafe_allow_html=True)

    # Build HTML table exactly like test app (avoid name "html" — shadows stdlib html module)
    html_parts = ['<div class="summary-wrap"><table class="summary-table">']
    if columns is None:
        columns = list(ENGINEERING_CHECK_COLUMNS)

    header_cells = []
    for col in columns:
        width = col.get("width")
        width_attr = f' style="width:{width}"' if width else ""
        header_cells.append(f"<th{width_attr}>{col.get('label','')}</th>")

    html_parts.append(
        f"""
<thead>
<tr>
  {''.join(header_cells)}
</tr>
</thead>
<tbody>
"""
    )

    for r in rows:
        uid = r["uid"]
        jump_id = resolve_jump_target_id(r)
        # Support both "title" and "check" for the check name
        check = r.get("title") or r.get("check", uid)
        ok = r.get("ok")
        tab = r.get("tab", "")
        status = r.get("status", "")
        
        status_norm = str(status).upper()
        if r.get("is_informational") or status_norm == "INFO":
            cls = ""
        else:
            cls = (
                "pass" if ok is True
                else "fail" if ok is False
                else "warn" if status_norm in ("NEAR LIMIT", "WARN", "CHECK")
                else ""
            )
        primary = "primary" if r.get("is_primary") else ""
        row_class = f"{cls} {primary}".strip()
        
        cells = []
        for i, col in enumerate(columns):
            key = col.get("key")
            if i == 0:
                text = r.get(key)
                if text is None and key in ("title", "check"):
                    text = check
                elif text is None:
                    text = check
                cell = f"""
  <td>
    {text} <span class="hint">↳ jump to calc</span>
    <a class="row-link" href="#" data-uid="{html_stdlib.escape(str(uid), quote=True)}" data-jump-target="{html_stdlib.escape(str(jump_id), quote=True)}" data-tab="{html_stdlib.escape(str(tab), quote=True)}"></a>
  </td>
"""
            else:
                if key in ("capacity", "action", "calculated", "requirement"):
                    val = summary_cell_display(r, key)
                else:
                    val = r.get(key, "")
                cell = f"  <td>{val}</td>"
            cells.append(cell)

        html_parts.append(
            f"""
<tr class="{row_class}" data-tab="{tab}">
{''.join(cells)}
</tr>
"""
        )

    html_parts.append("</tbody></table></div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


# Public summary-section API now lives in ui.summary_sections. Keep the legacy
# ui_seamless_steps names stable for existing imports and session-state behavior.
_summary_card_css = _shared_summary_card_css
SUMMARY_DASH = _shared_summary_dash
build_final_summary_check_card_html = _shared_build_final_summary_check_card_html
build_final_summary_check_card_model = _shared_build_final_summary_check_card_model
build_summary_check_card_html = _shared_build_summary_check_card_html
normalise_summary_display_value = _shared_normalise_summary_display_value
render_clickable_summary_table = _shared_render_clickable_summary_table


def bind_summary_clicks():
    """
    Binds JavaScript to handle opening expanders and smooth scrolling when summary rows are clicked.
    Finds expanders by searching all expanders and picking the one that comes after the marker in document order.
    """
    render_trusted_iframe(st,
        r"""
<script>
(function() {
  const doc = window.parent.document;

  function isScrollable(el) {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const oy = style.overflowY;
    const canScroll = (oy === "auto" || oy === "scroll");
    return canScroll && el.scrollHeight > el.clientHeight + 2;
  }

  function findBestScroller() {
    const candidates = [
      doc.querySelector('section.main'),
      doc.querySelector('[data-testid="stAppViewContainer"]'),
      doc.querySelector('[data-testid="stMain"]'),
      doc.querySelector('.main'),
    ].filter(Boolean);

    for (const c of candidates) {
      if (isScrollable(c)) return c;
      if (isScrollable(c.parentElement)) return c.parentElement;
    }
    if (isScrollable(doc.body)) return doc.body;
    if (isScrollable(doc.documentElement)) return doc.documentElement;
    return null;
  }

  function scrollToAnchor(anchor) {
    const scroller = findBestScroller();
    if (!scroller) {
      const y = anchor.getBoundingClientRect().top + window.parent.scrollY - 12;
      window.parent.scrollTo({ top: y, behavior: "smooth" });
      return;
    }

    const aRect = anchor.getBoundingClientRect();
    const sRect = scroller.getBoundingClientRect ? scroller.getBoundingClientRect() : { top: 0 };
    const targetTop = (scroller.scrollTop || 0) + (aRect.top - sRect.top) - 12;

    try { scroller.scrollTo({ top: targetTop, behavior: "smooth" }); }
    catch (e) { scroller.scrollTop = targetTop; }
  }

  function switchToTab(tabName) {
    if (!tabName) return Promise.resolve();
    
    // Try to find Streamlit tabs (rendered as buttons with data-baseweb="tab")
    const tabButtons = doc.querySelectorAll('button[data-baseweb="tab"]');
    for (const button of tabButtons) {
      const buttonText = button.textContent.trim();
      if (buttonText === tabName) {
        // Check if tab is already selected (has aria-selected="true")
        if (button.getAttribute('aria-selected') !== 'true') {
          console.log("Switching to tab:", tabName);
          button.click();
          // Wait a bit for tab to switch
          return new Promise(resolve => setTimeout(resolve, 300));
        }
        return Promise.resolve();
      }
    }
    
    // Fallback: try to find radio buttons (for backward compatibility)
    const radios = doc.querySelectorAll('input[type="radio"]');
    for (const radio of radios) {
      const label = radio.closest('label') || radio.parentElement?.querySelector('label');
      if (label && label.textContent.trim() === tabName) {
        if (!radio.checked) {
          console.log("Switching to tab (radio):", tabName);
          radio.click();
          return new Promise(resolve => setTimeout(resolve, 300));
        }
        return Promise.resolve();
      }
    }
    return Promise.resolve();
  }

  function findExpanderForUid(uid) {
    console.log("=== Finding expander for uid:", uid, "===");
    
    // First, try to find custom details element from clickable_calcbox (id="cb-{uid}")
    const customDetails = doc.getElementById(`cb-${uid}`);
    if (customDetails) {
      console.log("Found custom details element for uid:", uid);
      return customDetails;
    }
    
    // Find the marker
    const marker = doc.querySelector(`[data-calc-uid="${uid}"]`);
    if (!marker) {
      console.warn("Marker not found for uid:", uid);
      return null;
    }
    console.log("Found marker:", marker);
    
    // Streamlit expanders are wrapped in div[data-testid="stExpander"] which contains a <details> element
    // Find ALL expander divs, then get their details children
    const expanderDivs = Array.from(doc.querySelectorAll('div[data-testid="stExpander"]'));
    console.log("Found", expanderDivs.length, "total expander divs on page");
    
    // Extract the details elements from each expander div
    const allDetails = expanderDivs.map(div => div.querySelector('details')).filter(Boolean);
    console.log("Found", allDetails.length, "details elements in expanders");
    
    // Find the first details element that comes after the marker in document order
    for (const details of allDetails) {
      // Check if this expander comes after the marker in document order
      const position = marker.compareDocumentPosition(details);
      const isAfter = (position & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
      
      if (isAfter) {
        // Found an expander after the marker
        // Check if they're reasonably close by finding common ancestor depth
        let commonAncestor = null;
        let m = marker.parentElement;
        let d = details.parentElement;
        let depth = 0;
        
        // Climb up to find common ancestor
        while (m && d && depth < 20) {
          if (m === d) {
            commonAncestor = m;
            break;
          }
          m = m.parentElement;
          d = d.parentElement;
          depth++;
        }
        
        if (commonAncestor && depth < 20) {
          // They're reasonably close in the tree, this is likely the right expander
          console.log("Found expander (shared ancestor at depth", depth, ") for uid:", uid);
          return details;
        }
        
        // If depth is reasonable or we're at the first one, use it
        // (sometimes the marker and expander are in different containers but still related)
        if (depth < 25) {
          console.log("Found expander (after marker, depth", depth, ") for uid:", uid);
          return details;
        }
      }
    }
    
    // Fallback: If no expander found after marker, try finding the first expander
    // that's visible in the current tab context
    if (allDetails.length > 0) {
      console.log("Using fallback: first visible expander");
      return allDetails[0];
    }
    
    console.error("Could not find expander for uid:", uid);
    return null;
  }

  function openExpander(details) {
    if (!details) {
      console.warn("openExpander: details is null");
      return false;
    }
    
    console.log("Opening expander, currently open:", details.open);
    
    if (details.open) {
      console.log("Expander already open");
      return true;
    }

    // Try multiple methods to open
    const summary = details.querySelector("summary");
    
    if (summary) {
      console.log("Found summary element, attempting to open...");
      
      // Method 1: Direct click on summary
      try {
        summary.click();
        console.log("Clicked summary");
        
        // Check if it opened after a brief delay
        setTimeout(() => {
          if (!details.open) {
            console.log("Click didn't open, trying attribute...");
            details.open = true;
            
            // Also try a mouse event
            const clickEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
              view: window
            });
            summary.dispatchEvent(clickEvent);
          } else {
            console.log("✓ Expander opened successfully via click!");
          }
        }, 50);
        
        return true;
      } catch (e) {
        console.error("Error clicking summary:", e);
      }
    }
    
    // Method 2: Set open attribute directly
    console.log("Setting open attribute directly");
    details.open = true;
    
    // Method 3: Dispatch toggle event
    try {
      const toggleEvent = new Event('toggle', { bubbles: true });
      details.dispatchEvent(toggleEvent);
      console.log("Dispatched toggle event");
    } catch (e) {
      console.error("Error dispatching toggle:", e);
    }
    
    return true;
  }

  function flash(uid) {
    const inner = doc.getElementById("inner_" + uid);
    if (!inner) {
      console.warn("Flash target not found for uid:", uid);
      return;
    }
    inner.classList.add("flash-target");
    setTimeout(() => inner.classList.remove("flash-target"), 1200);
  }

  async function openAndScroll(jumpId, tabName) {
    console.log("=== openAndScroll: jumpId=", jumpId, "tab=", tabName, "===");
    
    // Step 1: Switch tab if needed
    if (tabName) {
      await switchToTab(tabName);
      // Wait a bit longer for tab content to fully render
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    
    // Step 2: Find anchor (for scrolling)
    const anchor = doc.getElementById("calc_" + jumpId);
    if (!anchor) {
      console.error("Anchor not found for jumpId:", jumpId);
      return;
    }
    console.log("Found anchor:", anchor);
    
    // Step 3: Find expander (with retries)
    let details = null;
    for (let attempt = 0; attempt < 5; attempt++) {
      details = findExpanderForUid(jumpId);
      if (details) {
        console.log("✓ Found expander on attempt", attempt + 1);
        break;
      }
      console.log("Retry finding expander, attempt", attempt + 1);
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    
    // Step 4: Open expander
    if (details) {
      console.log("Attempting to open expander...");
      const opened = openExpander(details);
      
      // Wait for expander animation
      await new Promise(resolve => setTimeout(resolve, 300));
      
      if (details.open) {
        console.log("✓ Expander is now open!");
      } else {
        console.warn("⚠ Expander still not open after attempts");
      }
    } else {
      console.error("✗ Could not find expander for uid:", uid);
    }
    
    // Step 5: Scroll (this part works)
    console.log("Scrolling to anchor...");
    scrollToAnchor(anchor);
    
    // Step 6: Flash after delay
    setTimeout(() => {
      flash(jumpId);
    }, 400);
  }

  function bind() {
    const links = doc.querySelectorAll(".row-link[data-uid]");
    console.log("=== Binding", links.length, "row links ===");
    
    links.forEach((a, index) => {
      if (a.dataset.bound === "1") {
        return;
      }
      a.dataset.bound = "1";
      const uid = a.dataset.uid;
      const jumpId = (a.dataset.jumpTarget || "").trim() || uid;
      const tab = a.dataset.tab || "";
      console.log(`Binding link ${index}: uid=${uid}, jumpId=${jumpId}, tab=${tab}`);

      a.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const clickedUid = a.dataset.uid;
        const clickedJump = (a.dataset.jumpTarget || "").trim() || clickedUid;
        const clickedTab = a.dataset.tab || "";
        
        if (!clickedUid) {
          console.warn("No uid found for row link");
          return;
        }
        
        console.log("=== Row clicked: uid=", clickedUid, "jumpId=", clickedJump, "tab=", clickedTab, "===");
        await openAndScroll(clickedJump, clickedTab);
      });
    });
  }

  // Bind immediately and retry (Streamlit can re-render)
  console.log("=== Initial bind attempt ===");
  bind();
  setTimeout(() => {
    console.log("=== Retry bind (300ms) ===");
    bind();
  }, 300);
  setTimeout(() => {
    console.log("=== Retry bind (1000ms) ===");
    bind();
  }, 1000);
  setTimeout(() => {
    console.log("=== Retry bind (2000ms) ===");
    bind();
  }, 2000);
})();
</script>
""",
        height=0,
    )


def step_card(uid: str, title: str, summary: str = "", status: str | None = None):
    """
    Deterministic expandable step:
    - always uses st.session_state[f"step_open_{uid}"] as the single source of truth
    - can be forced open by code (summary click)
    """
    # Anchor for scrolling
    st.markdown(f"<div id='calc_{uid}'></div>", unsafe_allow_html=True)

    open_key = f"step_open_{uid}"
    is_open = bool(st.session_state.get(open_key, False))

    # Header row as a button (toggle)
    header = title if not summary else f"{title} — {summary}"

    def _toggle():
        st.session_state[open_key] = not bool(st.session_state.get(open_key, False))

    # Make it look like a row
    st.button(header, key=f"step_btn_{uid}", on_click=_toggle)

    # Body container
    body = st.container()
    if is_open:
        return body  # caller writes into this container
    return None
