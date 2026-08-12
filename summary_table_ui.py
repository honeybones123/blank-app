import streamlit as st
import streamlit.components.v1 as components


def render_clickable_summary_table(rows, key="summary"):
    """
    Render summary table matching the test app style.
    Uses HTML table with clickable row links.
    
    Args:
        rows: List of row dicts with keys: uid, title/check, value, limit, util, status, ok, tab, is_primary
        key: Key prefix for session state tracking
    
    Returns:
        str or None: The clicked row uid if a row was clicked, None otherwise
    """
    # Check for clicked uid in query parameters (set by JavaScript on click)
    clicked_uid_key = f"{key}_clicked_uid"
    clicked_uid = None
    
    # Check query parameters first (set by JavaScript)
    query_params = st.query_params
    if clicked_uid_key in query_params:
        clicked_uid = query_params[clicked_uid_key]
        # Store in session state and clear query param
        st.session_state[clicked_uid_key] = clicked_uid
        # Clear the query param to avoid re-triggering
        params = dict(query_params)
        del params[clicked_uid_key]
        st.query_params.update(**params)
    else:
        # Also check session state (in case it was set previously)
        clicked_uid = st.session_state.get(clicked_uid_key)
        # Clear after reading (one-time use)
        if clicked_uid_key in st.session_state:
            del st.session_state[clicked_uid_key]
    
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

    # Build HTML table exactly like test app
    html = ['<div class="summary-wrap"><table class="summary-table">']
    html.append(
        """
<thead>
<tr>
  <th style="width:34%">Check</th>
  <th style="width:22%">Value</th>
  <th style="width:26%">Limit</th>
  <th style="width:8%">Util</th>
  <th style="width:10%">Status</th>
</tr>
</thead>
<tbody>
"""
    )

    for r in rows:
        uid = r["uid"]
        # Support both "title" and "check" for the check name
        check = r.get("title") or r.get("check", uid)
        value = r.get("value", "")
        limit = r.get("limit", "")
        util = r.get("util", "")
        status = r.get("status", "")
        ok = r.get("ok")
        tab = r.get("tab", "")
        
        cls = "pass" if ok is True else "fail" if ok is False else ""
        primary = "primary" if r.get("is_primary") else ""
        row_class = f"{cls} {primary}".strip()
        
        # Support custom anchor_id for scrolling (if provided, use it instead of calc_ + uid)
        anchor_id = r.get("anchor_id")
        anchor_attr = f' data-anchor-id="{anchor_id}"' if anchor_id else ""
        
        html.append(
            f"""
<tr class="{row_class}" data-tab="{tab}">
  <td>
    {check} <span class="hint">↳ jump to calc</span>
    <a class="row-link" href="#" data-uid="{uid}" data-tab="{tab}"{anchor_attr}></a>
  </td>
  <td>{value}</td>
  <td>{limit}</td>
  <td>{util}</td>
  <td>{status}</td>
</tr>
"""
        )

    html.append("</tbody></table></div>")
    st.markdown("".join(html), unsafe_allow_html=True)
    
    # Bind JavaScript to handle clicks and store clicked uid in session state
    _bind_summary_clicks(key)
    
    return clicked_uid


def _bind_summary_clicks(key_prefix="summary"):
    """
    Binds JavaScript to handle opening expanders and smooth scrolling when summary rows are clicked.
    Finds expanders by searching all expanders and picking the one that comes after the marker in document order.
    Also stores the clicked uid in session state so it can be returned by render_clickable_summary_table.
    """
    clicked_uid_key = f"{key_prefix}_clicked_uid"
    
    components.html(
        f"""
<script>
(function() {{
  const doc = window.parent.document;
  const clickedUidKey = "{clicked_uid_key}";

  function isScrollable(el) {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const oy = style.overflowY;
    const canScroll = (oy === "auto" || oy === "scroll");
    return canScroll && el.scrollHeight > el.clientHeight + 2;
  }}

  function findBestScroller() {{
    const candidates = [
      doc.querySelector('section.main'),
      doc.querySelector('[data-testid="stAppViewContainer"]'),
      doc.querySelector('[data-testid="stMain"]'),
      doc.querySelector('.main'),
    ].filter(Boolean);

    for (const c of candidates) {{
      if (isScrollable(c)) return c;
      if (isScrollable(c.parentElement)) return c.parentElement;
    }}
    if (isScrollable(doc.body)) return doc.body;
    if (isScrollable(doc.documentElement)) return doc.documentElement;
    return null;
  }}

  function scrollToAnchor(anchor) {{
    const scroller = findBestScroller();
    if (!scroller) {{
      const y = anchor.getBoundingClientRect().top + window.parent.scrollY - 12;
      window.parent.scrollTo({{ top: y, behavior: "smooth" }});
      return;
    }}

    const aRect = anchor.getBoundingClientRect();
    const sRect = scroller.getBoundingClientRect ? scroller.getBoundingClientRect() : {{ top: 0 }};
    const targetTop = (scroller.scrollTop || 0) + (aRect.top - sRect.top) - 12;

    try {{ scroller.scrollTo({{ top: targetTop, behavior: "smooth" }}); }}
    catch (e) {{ scroller.scrollTop = targetTop; }}
  }}

  function switchToTab(tabName) {{
    if (!tabName) return Promise.resolve();
    
    // Find radio buttons (Streamlit radio for tabs)
    const radios = doc.querySelectorAll('input[type="radio"]');
    for (const radio of radios) {{
      const label = radio.closest('label') || radio.parentElement?.querySelector('label');
      if (label && label.textContent.trim() === tabName) {{
        if (!radio.checked) {{
          console.log("Switching to tab:", tabName);
          radio.click();
          // Wait a bit for tab to switch
          return new Promise(resolve => setTimeout(resolve, 300));
        }}
        return Promise.resolve();
      }}
    }}
    return Promise.resolve();
  }}

  function findExpanderForUid(uid) {{
    console.log("=== Finding expander for uid:", uid, "===");
    
    // Find the marker
    const marker = doc.querySelector(`[data-calc-uid="${{uid}}"]`);
    if (!marker) {{
      console.warn("Marker not found for uid:", uid);
      return null;
    }}
    console.log("Found marker:", marker);
    
    // Streamlit expanders are wrapped in div[data-testid="stExpander"] which contains a <details> element
    // Find ALL expander divs, then get their details children
    const expanderDivs = Array.from(doc.querySelectorAll('div[data-testid="stExpander"]'));
    console.log("Found", expanderDivs.length, "total expander divs on page");
    
    // Extract the details elements from each expander div
    const allDetails = expanderDivs.map(div => div.querySelector('details')).filter(Boolean);
    console.log("Found", allDetails.length, "details elements in expanders");
    
    // Find the first details element that comes after the marker in document order
    for (const details of allDetails) {{
      // Check if this expander comes after the marker in document order
      const position = marker.compareDocumentPosition(details);
      const isAfter = (position & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
      
      if (isAfter) {{
        // Found an expander after the marker
        // Check if they're reasonably close by finding common ancestor depth
        let commonAncestor = null;
        let m = marker.parentElement;
        let d = details.parentElement;
        let depth = 0;
        
        // Climb up to find common ancestor
        while (m && d && depth < 20) {{
          if (m === d) {{
            commonAncestor = m;
            break;
          }}
          m = m.parentElement;
          d = d.parentElement;
          depth++;
        }}
        
        if (commonAncestor && depth < 20) {{
          // They're reasonably close in the tree, this is likely the right expander
          console.log("Found expander (shared ancestor at depth", depth, ") for uid:", uid);
          return details;
        }}
        
        // If depth is reasonable or we're at the first one, use it
        // (sometimes the marker and expander are in different containers but still related)
        if (depth < 25) {{
          console.log("Found expander (after marker, depth", depth, ") for uid:", uid);
          return details;
        }}
      }}
    }}
    
    // Fallback: If no expander found after marker, try finding the first expander
    // that's visible in the current tab context
    if (allDetails.length > 0) {{
      console.log("Using fallback: first visible expander");
      return allDetails[0];
    }}
    
    console.error("Could not find expander for uid:", uid);
    return null;
  }}

  function openExpander(details) {{
    if (!details) {{
      console.warn("openExpander: details is null");
      return false;
    }}
    
    console.log("Opening expander, currently open:", details.open);
    
    if (details.open) {{
      console.log("Expander already open");
      return true;
    }}

    // Try multiple methods to open
    const summary = details.querySelector("summary");
    
    if (summary) {{
      console.log("Found summary element, attempting to open...");
      
      // Method 1: Direct click on summary
      try {{
        summary.click();
        console.log("Clicked summary");
        
        // Check if it opened after a brief delay
        setTimeout(() => {{
          if (!details.open) {{
            console.log("Click didn't open, trying attribute...");
            details.open = true;
            
            // Also try a mouse event
            const clickEvent = new MouseEvent('click', {{
              bubbles: true,
              cancelable: true,
              view: window
            }});
            summary.dispatchEvent(clickEvent);
          }} else {{
            console.log("✓ Expander opened successfully via click!");
          }}
        }}, 50);
        
        return true;
      }} catch (e) {{
        console.error("Error clicking summary:", e);
      }}
    }}
    
    // Method 2: Set open attribute directly
    console.log("Setting open attribute directly");
    details.open = true;
    
    // Method 3: Dispatch toggle event
    try {{
      const toggleEvent = new Event('toggle', {{ bubbles: true }});
      details.dispatchEvent(toggleEvent);
      console.log("Dispatched toggle event");
    }} catch (e) {{
      console.error("Error dispatching toggle:", e);
    }}
    
    return true;
  }}

  function flash(uid) {{
    const inner = doc.getElementById("inner_" + uid);
    if (!inner) {{
      console.warn("Flash target not found for uid:", uid);
      return;
    }}
    inner.classList.add("flash-target");
    setTimeout(() => inner.classList.remove("flash-target"), 1200);
  }}

  async function openAndScroll(uid, tabName, customAnchorId) {{
    console.log("=== openAndScroll: uid=", uid, "tab=", tabName, "anchor=", customAnchorId || "calc_" + uid, "===");
    
    // Step 1: Switch tab if needed
    if (tabName) {{
      await switchToTab(tabName);
      // Wait a bit longer for tab content to fully render
      await new Promise(resolve => setTimeout(resolve, 300));
    }}
    
    // Step 2: Find anchor (for scrolling)
    // Check if row has a custom anchor_id, otherwise use calc_ + uid
    const anchorId = customAnchorId || ("calc_" + uid);
    const anchor = doc.getElementById(anchorId);
    if (!anchor) {{
      console.error("Anchor not found for id:", anchorId);
      return;
    }}
    console.log("Found anchor:", anchor, "with id:", anchorId);
    
    // Step 3: Find expander (with retries)
    let details = null;
    for (let attempt = 0; attempt < 5; attempt++) {{
      details = findExpanderForUid(uid);
      if (details) {{
        console.log("✓ Found expander on attempt", attempt + 1);
        break;
      }}
      console.log("Retry finding expander, attempt", attempt + 1);
      await new Promise(resolve => setTimeout(resolve, 200));
    }}
    
    // Step 4: Open expander
    if (details) {{
      console.log("Attempting to open expander...");
      const opened = openExpander(details);
      
      // Wait for expander animation
      await new Promise(resolve => setTimeout(resolve, 300));
      
      if (details.open) {{
        console.log("✓ Expander is now open!");
      }} else {{
        console.warn("⚠ Expander still not open after attempts");
      }}
    }} else {{
      console.error("✗ Could not find expander for uid:", uid);
    }}
    
    // Step 5: Scroll (this part works)
    console.log("Scrolling to anchor...");
    scrollToAnchor(anchor);
    
    // Step 6: Flash after delay
    setTimeout(() => {{
      flash(uid);
    }}, 400);
  }}

  function bind() {{
    const links = doc.querySelectorAll(".row-link[data-uid]");
    console.log("=== Binding", links.length, "row links ===");
    
    links.forEach((a, index) => {{
      if (a.dataset.bound === "1") {{
        return;
      }}
      a.dataset.bound = "1";
      const uid = a.dataset.uid;
      const tab = a.dataset.tab || "";
      console.log(`Binding link ${{index}}: uid=${{uid}}, tab=${{tab}}`);

      a.addEventListener("click", async (e) => {{
        e.preventDefault();
        e.stopPropagation();
        const clickedUid = a.dataset.uid;
        const clickedTab = a.dataset.tab || "";
        const customAnchorId = a.dataset.anchorId;
        
        if (!clickedUid) {{
          console.warn("No uid found for row link");
          return;
        }}
        
        console.log("=== Row clicked: uid=", clickedUid, "tab=", clickedTab, "anchor=", customAnchorId || "calc_" + clickedUid, "===");
        
        // Store clicked uid in URL query parameter to trigger Streamlit rerun
        // This allows Python to read the clicked uid on the next render
        try {{
          const url = new URL(window.parent.location.href);
          url.searchParams.set(clickedUidKey, clickedUid);
          // Use replaceState to avoid adding to history, but trigger Streamlit rerun
          window.parent.history.replaceState({{}}, '', url);
          // Trigger Streamlit to detect the URL change
          window.parent.dispatchEvent(new PopStateEvent('popstate'));
        }} catch (e) {{
          console.warn("Could not update URL:", e);
          // Fallback: use localStorage
          try {{
            window.parent.localStorage.setItem(clickedUidKey, clickedUid);
          }} catch (e2) {{
            console.warn("Could not use localStorage:", e2);
          }}
        }}
        
        await openAndScroll(clickedUid, clickedTab, customAnchorId);
      }});
    }});
  }}

  // Bind immediately and retry (Streamlit can re-render)
  console.log("=== Initial bind attempt ===");
  bind();
  setTimeout(() => {{
    console.log("=== Retry bind (300ms) ===");
    bind();
  }}, 300);
  setTimeout(() => {{
    console.log("=== Retry bind (1000ms) ===");
    bind();
  }}, 1000);
  setTimeout(() => {{
    console.log("=== Retry bind (2000ms) ===");
    bind();
  }}, 2000);
  
}})();
</script>
""",
        height=0,
    )

