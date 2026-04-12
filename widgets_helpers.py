import streamlit as st
import os
import json
from state_and_helpers import _debug_log_path

# Debug log path used by optional widget debug blocks
log_path = os.devnull
try:
    log_path = _debug_log_path()
except Exception:
    pass
import streamlit.components.v1 as components
import re
import html

from state_and_helpers import TAB_KEYS, resolve_widget_key, NONZERO_REQUIRED_SHARED_KEYS, zero_allowed, _audit, mark_user_edit, set_shared

# Global rendered widget keys set (module-level)
_RENDERED_WIDGET_KEYS: set[str] = set()


def _register_rendered_key(key: str) -> None:
    """Register a widget key as rendered this run."""
    _RENDERED_WIDGET_KEYS.add(key)
    # Also maintain session_state version for backward compatibility
    rendered = st.session_state.get("_rendered_widget_keys")
    if not isinstance(rendered, set):
        rendered = set()
        st.session_state["_rendered_widget_keys"] = rendered
    rendered.add(key)


def get_rendered_widget_keys() -> list[str]:
    """Return keys rendered this run (sorted)."""
    return sorted(_RENDERED_WIDGET_KEYS)


def clear_rendered_widget_keys() -> None:
    """Call at start of each page render."""
    _RENDERED_WIDGET_KEYS.clear()
    # Also clear session_state version for backward compatibility
    if "_rendered_widget_keys" in st.session_state:
        st.session_state["_rendered_widget_keys"] = set()


def normalized_sec_shape_ui(raw: str | None) -> str:
    """RECT / T / I for UI branching (matches session sec_shape / inputs_sec_shape)."""
    s = str(raw or "RECT").strip().upper()
    if s in ("T", "T-SECTION", "T_SECTION", "T-BEAM"):
        return "T"
    if s in ("I", "I-SECTION", "I_SECTION", "I-BEAM"):
        return "I"
    return "RECT"


def longitudinal_reo_row_help_face(sec_shape: str | None, section_norm: str) -> str:
    """Phrase for help text: 'web top', 'web bottom', 'top', or 'bottom'."""
    sh = normalized_sec_shape_ui(sec_shape)
    if sh in ("T", "I"):
        return "web top" if section_norm == "top" else "web bottom"
    return "top" if section_norm == "top" else "bottom"


def main_longitudinal_reo_pair_labels(sec_shape: str | None, *, variant: str) -> tuple[str, str]:
    """
    Bottom / top display labels for the main (web) longitudinal groups — not flange reo.
    variant: 'inputs_compact' | 'inputs_detailed' | 'bending' | 'sentence_lower'
    """
    sh = normalized_sec_shape_ui(sec_shape)
    is_ti = sh in ("T", "I")
    if variant == "inputs_compact":
        if is_ti:
            return "Web bottom reo", "Web top reo"
        return "Bottom reo", "Top reo"
    if variant == "inputs_detailed":
        if is_ti:
            return "Web Bottom Longitudinal Reinforcement", "Web Top Longitudinal Reinforcement"
        return "Bottom Longitudinal Reinforcement", "Top Longitudinal Reinforcement"
    if variant == "bending":
        if is_ti:
            return "Web Bottom Reinforcement", "Web Top Reinforcement"
        return "Bottom Reinforcement", "Top Reinforcement"
    if variant == "sentence_lower":
        if is_ti:
            return "Web bottom longitudinal reinforcement", "Web top longitudinal reinforcement"
        return "Bottom longitudinal reinforcement", "Top longitudinal reinforcement"
    return "Bottom reo", "Top reo"


def main_longitudinal_reo_change_line_prefixes(state: dict | None) -> tuple[str, str]:
    """Labels for guidance diff lines, e.g. 'Web bottom reo: …'."""
    raw = (state or {}).get("sec_shape") or (state or {}).get("inputs_sec_shape")
    return main_longitudinal_reo_pair_labels(raw, variant="inputs_compact")


def _wrap_user_edit(widget_key: str, cb):
    """
    Wrap a callback to mark the widget as user-edited ONLY when we're not
    in hydration/restore/lock mode.

    Streamlit can trigger on_change from programmatic widget updates
    (e.g. hydrate_tab_widgets_from_shared). If we mark those as "user edits",
    the sync gate can incorrectly allow widget→shared writes and clobber values.
    """
    def _wrapped():
        if st.session_state.get("_sync_lock", False):
            return
        # Only block marking during ACTIVE lock/restore phases
        # Do NOT block on _restored_from_snapshot (that flag means "this boot came from snapshot",
        # not "we're currently restoring"). After restore completes, user edits should be allowed.
        if (
            st.session_state.get("_restore_guard_active", False)
        ):
            cb()
            return

        st.session_state["_last_user_widget_key"] = widget_key

        # Also mark the shared key if we can resolve it
        shared_key = TAB_KEYS.get(widget_key)
        if shared_key:
            mark_user_edit(widget_key, shared_key)

        cb()

    return _wrapped


def seed_widget_from_shared(widget_key: str, shared_key: str, fallback_default):
    """
    Contract-safe: only seed widget state ONCE if the widget key is missing.
    Never overwrites user edits during reruns.
    """
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state.get(shared_key, fallback_default)


def _register_rendered_key(key: str) -> None:
    """Register a widget key as rendered this run."""
    _RENDERED_WIDGET_KEYS.add(key)
    # Also maintain session_state version for backward compatibility
    rendered = st.session_state.get("_rendered_widget_keys")
    if not isinstance(rendered, set):
        rendered = set()
        st.session_state["_rendered_widget_keys"] = rendered
    rendered.add(key)


def apply_global_widget_css():
    """Global styling for every page (remove +/- etc.)."""
    st.markdown(
        """
        <style>
        /* Match Inputs page: main content breathing room on all pages */
        .main .block-container {
            padding-left: 3rem;
            padding-right: 3rem;
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
        }

        /* Hide browser spinner */
        input[type=number]::-webkit-inner-spin-button,
        input[type=number]::-webkit-outer-spin-button {
            -webkit-appearance: none !important;
            margin: 0 !important;
        }
        input[type=number] { -moz-appearance: textfield !important; }

        /* Hide Streamlit +/- buttons */
        div[data-testid="stNumberInput"] button {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            opacity: 0 !important;
        }

        /* Make input smaller */
        div[data-testid="stNumberInput"] input[type=number] {
            padding-top: 2px !important;
            padding-bottom: 2px !important;
            height: 2rem !important;
            font-size: 0.9rem !important;
        }

        /* Hover tooltip styles */
        .sb-label {
            font-size: 0.9rem;
            font-weight: 600;
            margin: 0.25rem 0 0.25rem 0;
        }
        .sb-tooltip {
            position: relative;
            display: inline-block;
        }
        .sb-tooltip-bubble {
            visibility: hidden;
            opacity: 0;
            width: 320px;
            max-width: 60vw;
            background: rgba(17,17,17,0.92);
            color: #fff;
            text-align: left;
            border-radius: 8px;
            padding: 10px 12px;
            position: absolute;
            z-index: 1000;
            left: 0;
            top: 125%;
            transition: opacity 0.15s ease;
            font-weight: 400;
            font-size: 0.82rem;
            line-height: 1.25rem;
            white-space: pre-wrap;
        }
        .sb-tooltip:hover .sb-tooltip-bubble {
            visibility: visible;
            opacity: 1;
        }

        /* --- Keep widgets from stretching across the page --- */
        :root {
            --sb-widget-max: 240px;   /* tweak 240–320 to taste */
        }

        /* Cap the container width of common widgets */
        div[data-testid="stNumberInput"],
        div[data-testid="stTextInput"],
        div[data-testid="stSelectbox"],
        div[data-testid="stMultiselect"],
        div[data-testid="stDateInput"],
        div[data-testid="stTimeInput"] {
            max-width: var(--sb-widget-max) !important;
        }

        /* Important: don't force them to full width */
        div[data-testid="stNumberInput"],
        div[data-testid="stTextInput"],
        div[data-testid="stSelectbox"],
        div[data-testid="stMultiselect"],
        div[data-testid="stDateInput"],
        div[data-testid="stTimeInput"] {
            width: auto !important;
        }

        /* Make the actual control fill the capped container (so it looks tidy) */
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input {
            width: 100% !important;
        }

        /* Info button styling - small blue "i" icon (no arrow, no emoji) */
        /* Target buttons inside popover containers (info buttons) */
        div[data-testid="stPopover"] button[kind="secondary"],
        div[data-testid="stPopover"] button[data-testid="baseButton-secondary"] {
            background-color: transparent !important;
            border: none !important;
            padding: 0 2px !important;
            margin: 0 !important;
            font-size: 0.85rem !important;
            color: #1f77b4 !important;
            font-weight: 400 !important;
            min-width: auto !important;
            width: auto !important;
            height: auto !important;
            line-height: 1.2 !important;
            cursor: pointer !important;
            box-shadow: none !important;
        }
        div[data-testid="stPopover"] button[kind="secondary"]:hover,
        div[data-testid="stPopover"] button[data-testid="baseButton-secondary"]:hover {
            color: #155a8a !important;
            background-color: transparent !important;
        }
        /* Remove any caret/arrow from popover buttons */
        div[data-testid="stPopover"] button::after,
        div[data-testid="stPopover"] button::before {
            display: none !important;
        }
        /* Ensure popover trigger buttons are small and inline */
        div[data-testid="stPopover"] {
            display: inline-block !important;
            vertical-align: middle !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_result_page_css():
    """Shared layout and heading styling for engineering result pages only."""
    st.markdown(
        """
<style>
/* Page chrome: vertical padding comes from apply_global_widget_css (.main .block-container) */

.result-page-title {
    font-size: 2.35rem;
    font-weight: 700;
    line-height: 1.05;
    margin-top: -0.55rem;
    margin-bottom: 0.08rem;
}

/* Compact vertical rhythm */
div[data-testid="stVerticalBlock"] > div {
    gap: 0.35rem;
}

/* Softer form labels */
label {
    font-size: 0.8rem !important;
    color: #555 !important;
    margin-bottom: 0.1rem !important;
}

/* Compact input feel */
div[data-baseweb="input"] {
    min-height: 32px;
}

/* Tighten heading rhythm */
h2, h3, h4 {
    margin-top: 0.6rem !important;
    margin-bottom: 0.5rem !important;
}

/* Tighten expanders */
.streamlit-expanderHeader {
    padding-top: 0.3rem !important;
    padding-bottom: 0.3rem !important;
}

/* Clean section titles */
.section-title {
    font-size: 1.05rem;
    font-weight: 600;
    margin-bottom: 0.4rem;
}

/* Consistent divider rhythm */
hr {
    margin: 1rem 0 !important;
}

/* Optional compact reinforcement/grouped-input styling */
.compact-reo label {
    font-size: 0.85rem !important;
}

.compact-reo div[data-baseweb="select"] span,
.compact-reo div[data-baseweb="input"] input {
    font-size: 0.85rem !important;
}

.compact-reo .sb-label {
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: rgba(49, 51, 63, 0.82) !important;
}

.compact-reo div[data-testid="stVerticalBlock"] > div {
    gap: 0.25rem;
}

.compact-reo p {
    margin-bottom: 0.2rem;
}

.compact-reo .reo-layer-title {
    display: block;
    min-height: 1.1rem;
    line-height: 1.1rem;
    margin: 0 0 0.18rem 0;
    font-size: 0.82rem;
    font-weight: 600;
    color: rgba(49, 51, 63, 0.9);
}

.compact-reo .reo-layer-spacer {
    display: block;
    min-height: 1.1rem;
    line-height: 1.1rem;
    margin: 0 0 0.18rem 0;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(title: str) -> None:
    """Render a consistent section title for result/check pages."""
    st.markdown(
        f"<div class='section-title'>{html.escape(str(title))}</div>",
        unsafe_allow_html=True,
    )


def render_result_page_title(title: str) -> None:
    """Render a tightly spaced main title for result/check pages."""
    st.markdown(
        f"<div class='result-page-title'>{html.escape(str(title))}</div>",
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------
#  🔵 Calcbox – Global Blue Calculation Box Styling
# ------------------------------------------------------------
def apply_calcbox_css():
    """Apply global CSS for the blue calculation boxes (blockquote styling)."""
    st.markdown(
        """
<style>
/* Style blockquotes as blue calc boxes */
blockquote {
  border-left: 4px solid #1f77b4 !important;
  background-color: rgba(31, 119, 180, 0.08) !important;
  padding: 0.75rem 1rem !important;
  margin: 0.5rem 0 0.75rem 0 !important;
  border-radius: 0 6px 6px 0 !important;
  color: #1a1a1a !important;
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.35;
}
blockquote p, blockquote * { color: #1a1a1a !important; }

/* Seamless calc system styles */
.calc-details {
  margin: 1rem 0;
}

.calc-details summary {
  cursor: pointer;
  padding: 0.5rem;
  font-weight: 600;
  border-left: 4px solid #1f77b4;
  background-color: rgba(31, 119, 180, 0.08);
  border-radius: 0 4px 4px 0;
}

.calc-body {
  margin-top: 0.5rem;
  padding-left: 1rem;
}

.calc-inner {
  padding: 0.75rem;
}

.calc-inner.flash {
  animation: flash-highlight 1.2s ease-out;
}

@keyframes flash-highlight {
  0% { background-color: rgba(255, 255, 0, 0.3); }
  100% { background-color: transparent; }
}

.row-link {
  cursor: pointer;
  text-decoration: underline;
  color: #1f77b4;
}

.row-link:hover {
  color: #155a8a;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def apply_step_expander_css():
    """Apply CSS to make collapsed step expanders tightly stacked."""
    st.markdown(
        """
<style>
/* Reduce expander header padding/margins for compact collapsed steps */
div[data-testid="stExpander"] {
    margin-top: 0.25rem !important;
    margin-bottom: 0.25rem !important;
}

div[data-testid="stExpander"] > details {
    margin-top: 0.25rem !important;
    margin-bottom: 0.25rem !important;
}

div[data-testid="stExpander"] > details > summary {
    padding-top: 0.4rem !important;
    padding-bottom: 0.4rem !important;
    padding-left: 0.5rem !important;
    padding-right: 0.5rem !important;
    margin-bottom: 0 !important;
}

/* Reduce default gap between expanders */
div[data-testid="stExpander"] + div[data-testid="stExpander"] {
    margin-top: 0.1rem !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def apply_step_summary_expander_css():
    """Apply CSS to make expander header look like calcbox in summary mode."""
    st.markdown(
        """
<style>
/* Hide the default expander arrow */
div[data-testid="stExpander"] details summary svg {
  display: none !important;
}

/* Tight spacing between steps */
div[data-testid="stExpander"] { margin: 0 !important; }
div[data-testid="stExpander"] details { margin: 0 !important; }

/* Make expander header look like your calcbox summary */
div[data-testid="stExpander"] details summary {
  border-left: 4px solid #1f77b4 !important;
  background: rgba(31,119,180,0.08) !important;
  margin: 0 !important;
  padding: 0.03rem 0.40rem !important;
  border-radius: 0 6px 6px 0 !important;
  color: #222 !important;
  cursor: pointer !important;
  list-style: none !important;
}
div[data-testid="stExpander"] details > div { padding-top: 0.02rem !important; }

/* Tight vertical spacing between summary cards */
div.element-container:has(div[data-testid="stExpander"]) {
  margin-top: 0 !important;
  margin-bottom: 0 !important;
}

div[data-testid="stExpander"] details:has(span.step-neutral) > summary {
  border-left-color: #1f77b4 !important;
  background: rgba(31,119,180,0.08) !important;
}

/* Themed accents (Design / SFD equilibrium steps) */
div[data-testid="stExpander"] details:has(span.step-accent-load) > summary {
  border-left-color: #f08c00 !important;
  background: rgba(240, 140, 0, 0.12) !important;
}
div[data-testid="stExpander"] details:has(span.step-accent-support) > summary {
  border-left-color: #2563eb !important;
  background: rgba(37, 99, 235, 0.12) !important;
}
div[data-testid="stExpander"] details:has(span.step-accent-reaction) > summary {
  border-left-color: #059669 !important;
  background: rgba(5, 150, 105, 0.12) !important;
}
div[data-testid="stExpander"] details:has(span.step-accent-fe) > summary {
  border-left-color: #7c3aed !important;
  background: rgba(124, 58, 237, 0.12) !important;
}
div[data-testid="stExpander"] details:has(span.step-accent-shear) > summary {
  border-left-color: #dc2626 !important;
  background: rgba(220, 38, 38, 0.12) !important;
}
div[data-testid="stExpander"] details:has(span.step-accent-moment) > summary {
  border-left-color: #db2777 !important;
  background: rgba(219, 39, 119, 0.12) !important;
}

/* Pass/fail last so they override accents */
div[data-testid="stExpander"] details:has(span.step-pass) > summary {
  border-left-color: #28a745 !important;
  background: rgba(40,167,69,0.10) !important;
}

div[data-testid="stExpander"] details:has(span.step-fail) > summary {
  border-left-color: #dc3545 !important;
  background: rgba(220,53,69,0.10) !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_page_explainer_expander(render_fn, label: str = "ℹ️ INFO") -> None:
    """Render a right-aligned page explainer popover."""
    _, info_col = st.columns([8, 1], vertical_alignment="center")
    with info_col:
        with st.popover(label):
            render_fn()


# Optional left-border / background accents for calc steps (Design / SFD page, etc.)
_CALC_ACCENTS: dict[str, tuple[str, str]] = {
    "load": ("#f08c00", "rgba(240, 140, 0, 0.12)"),
    "support": ("#2563eb", "rgba(37, 99, 235, 0.12)"),
    "reaction": ("#059669", "rgba(5, 150, 105, 0.12)"),
    "fe": ("#7c3aed", "rgba(124, 58, 237, 0.12)"),
    "shear": ("#dc2626", "rgba(220, 38, 38, 0.12)"),
    "moment": ("#db2777", "rgba(219, 39, 119, 0.12)"),
}


def _normalize_calc_accent(accent: str | None) -> str | None:
    if accent is None:
        return None
    key = str(accent).strip().lower()
    return key if key in _CALC_ACCENTS else None


def status_to_class(status=None):
    """Convert status to CSS class name. Supports both 'pass/fail' and 'OK/Check/NG' formats, plus True/False."""
    if status is None:
        return "step-neutral"
    
    # Handle boolean values
    if status is True:
        return "step-pass"
    if status is False:
        return "step-fail"
    
    # Normalize to lowercase for comparison
    status_lower = str(status).lower() if status else None
    
    # Map both formats to CSS classes
    if status_lower in ("pass", "ok"):
        return "step-pass"
    elif status_lower in ("fail", "check", "ng"):
        return "step-fail"
    else:
        return "step-neutral"


def step_expander_calcbox(
    uid: str,
    summary_line: str,
    details_md: str,
    status=None,
    diagram_fn=None,
    content_before=None,
    content_after=None,
    expanded=None,
    jump_uid=None,
    accent: str | None = None,
):
    """
    Render a step as an expandable card with summary header.
    Optional accent: load, support, reaction, fe, shear, moment (left border + calc box tint).
    """
    apply_step_summary_expander_css()

    # Anchor for scrolling with deterministic marker
    st.markdown(f"<div id='calc_{uid}'></div>", unsafe_allow_html=True)
    # marker that JS uses to find the next expander
    st.markdown(f"<div data-calc-uid='{uid}'></div>", unsafe_allow_html=True)

    # Auto-expand when step_open_{uid} is set (from jump_nav or manual toggle)
    # Allow explicit expanded parameter to override
    if expanded is not None:
        is_expanded = expanded
    else:
        is_expanded = st.session_state.get(f"step_open_{uid}", False)

    status_class = status_to_class(status)
    accent_key = _normalize_calc_accent(accent)
    accent_html = (
        f"<span class='step-accent-{accent_key}'></span>" if accent_key else ""
    )

    info_tip = ""
    if content_before:
        info_tip = " ℹ️"

    summary_line_norm = str(summary_line or "")
    # Normalize legacy numeric step labels (e.g. "1.2 Something ...")
    # to explicit check labels without touching already-numbered "Check X — ..." text.
    if not re.match(r"^\s*Check\s+\d+(?:\.\d+)?\s+—", summary_line_norm, flags=re.IGNORECASE):
        m = re.match(r"^\s*(\d+(?:\.\d+)?)\s+(.+)$", summary_line_norm)
        if m:
            number = m.group(1)
            rest = m.group(2).strip()
            summary_line_norm = f"Check {number} — {rest}"
    def _bold_first_summary_line(line: str) -> str:
        txt = str(line or "").strip()
        if not txt:
            return txt
        if txt.startswith("**") and txt.endswith("**"):
            return txt
        return f"**{txt}**"

    if " | " in summary_line_norm:
        first, rest = summary_line_norm.split(" | ", 1)
        formatted_summary = f"{_bold_first_summary_line(first)}  \n{rest}"
    else:
        formatted_summary = _bold_first_summary_line(summary_line_norm)
    label = f"{formatted_summary}{info_tip}".strip()

    with st.expander(label, expanded=is_expanded):
        # Inner target for flash highlight
        st.markdown(f"<div id='inner_{uid}'>", unsafe_allow_html=True)
        st.markdown(
            f"<span class='{status_class}'></span>{accent_html}",
            unsafe_allow_html=True,
        )

        if content_before:
            content_before()

        if diagram_fn:
            col_calc, col_fig = st.columns([2.0, 1.0], gap="large")
            with col_calc:
                calcbox(
                    details_md,
                    status=status,
                    uid=f"{uid}__details",
                    accent=accent_key,
                )
            with col_fig:
                pad, plot = st.columns([0.10, 0.90], gap="small")
                with plot:
                    diagram_fn()
        else:
            calcbox(
                details_md,
                status=status,
                uid=f"{uid}__details",
                accent=accent_key,
            )
        
        if content_after:
            content_after()
        
        # Close inner div for flash highlight
        st.markdown("</div>", unsafe_allow_html=True)


def apply_step_summary_card_css():
    """Apply CSS for summary mode step cards."""
    st.markdown(
        """
<style>
/* Summary card button should look like a calcbox */
div[data-testid="stButton"] > button.step-summary-card {
  width: 100% !important;
  text-align: left !important;
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
  margin: 0 !important;
}

.step-card {
  border-left: 4px solid #1f77b4;
  background: rgba(31,119,180,0.08);
  padding: 0.55rem 0.8rem;
  margin: 0.12rem 0 0.28rem 0;
  border-radius: 0 6px 6px 0;
  color: #1a1a1a;
}

.step-card.pass { border-left-color: #28a745; background: rgba(40,167,69,0.10); }

.step-card.fail { border-left-color: #dc3545; background: rgba(220,53,69,0.10); }

.step-card .title { font-weight: 600; margin-bottom: 2px; }

.step-card .sub   { font-size: 13px; color: rgba(50,50,50,0.85); }

.step-card .result{ font-size: 13px; margin-top: 2px; }

.step-card .chev {
  float: right;
  opacity: 0.75;
  font-size: 14px;
  margin-top: -2px;
}

/* kill extra gap under buttons */
div[data-testid="stButton"] { margin: 0.05rem 0 !important; }
</style>
        """,
        unsafe_allow_html=True,
    )


def label_with_hover(label: str, hover_md: str | None = None, *, required: bool = False):
    """
    Render a label with optional hover tooltip.
    - No visible icon.
    - Tooltip appears when user hovers the label text.
    """
    label_txt = html.escape(label + (" *" if required else ""))
    if not hover_md:
        st.markdown(f"<div class='sb-label'>{label_txt}</div>", unsafe_allow_html=True)
        return

    tip = html.escape(hover_md)
    st.markdown(
        f"""
<div class="sb-label sb-tooltip">
  <span class="sb-tooltip-target">{label_txt}</span>
  <span class="sb-tooltip-bubble">{tip}</span>
</div>
""",
        unsafe_allow_html=True,
    )


def _nonempty_label(label: str, fallback: str) -> str:
    label = (label or "").strip()
    return label if label else fallback


def number_row(
    label: str,
    key: str,
    default: float,
    sync_callbacks=None,
    help_text: str | None = None,
    required: bool = False,
    disabled: bool = False,
    step=None,
    use_columns: bool = True,
):
    """Create a number input row with label on the left and widget on the right (V2-safe)."""
    label_text = f"{label} *" if required else label
    if use_columns:
        col1, col2 = st.columns([1, 2], gap="medium")
        with col1:
            if help_text:
                label_with_hover(label_text, help_text, required=False)
            else:
                st.markdown(f"**{label_text}**")
        widget_container = col2
    else:
        if help_text:
            label_with_hover(label_text, help_text, required=False)
        else:
            st.markdown(f"**{label_text}**")
        widget_container = st.container()

    with widget_container:
        original_key = key
        # DO NOT resolve/alias widget keys across pages (causes cross-page key collisions)
        # Keep per-page keys stable and distinct.
        _register_rendered_key(key)

        # ---- callback lookup ----
        on_change_callback = None
        if sync_callbacks and isinstance(sync_callbacks, dict):
            raw_callback = sync_callbacks.get(original_key)
            if raw_callback:
                # Wrap callback to mark user edit before calling
                on_change_callback = _wrap_user_edit(original_key, raw_callback)


        # ---- shared-key lookup ----
        shared_key = TAB_KEYS.get(original_key)

        # Prefer shared value as the one-time seed default (if available and meaningful)
        # CRITICAL: If shared state is 0 but default is meaningful, use default instead
        # This prevents widgets from seeding to 0 when shared state is corrupted
        if shared_key is not None and shared_key in st.session_state:
            shared_val = st.session_state[shared_key]
            # If shared is 0 but default is meaningful, use default (shared state is corrupted)
            # BUT: Allow 0 for zero-allowed keys (like reo counts/spacing/diameters/legs)
            if (shared_val == 0 or shared_val == 0.0) and default not in (None, "", 0, 0.0):
                protected = (shared_key in NONZERO_REQUIRED_SHARED_KEYS) and (not zero_allowed(shared_key))
                if protected:
                    effective_default = default
                    # #region agent log
                    try:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"location": "widgets_helpers.py:number_row", "message": "Detected corrupted shared state (no write)", "data": {"key": original_key, "shared_key": shared_key, "old_shared": shared_val, "suggested_default": default}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "N"}) + "\n")
                    except: pass
                    # #endregion
                else:
                    effective_default = shared_val
            else:
                effective_default = shared_val
        else:
            effective_default = default

        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "widgets_helpers.py:number_row", "message": "Shared key lookup", "data": {"original_key": original_key, "shared_key": shared_key, "shared_value": st.session_state.get(shared_key) if shared_key else None, "effective_default": effective_default, "key_in_session": original_key in st.session_state, "session_value": st.session_state.get(original_key)}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
        except: pass
        # #endregion

        # Determine min_value based on key type
        min_val = None

        # counts/spacing/detailing can be 0
        if ("nb_or_s" in original_key) or original_key.startswith("inputs_nb_") or original_key.startswith("inputs_db_") or "rowgap" in original_key or "lig_" in original_key:
            min_val = 0.0

        # time-dependent inputs should never be 0
        if original_key in ("inputs_t_creep", "inputs_t_shrink", "inputs_age_at_loading"):
            min_val = 1.0

        # ---- V2: seed ONCE only; never reseed from shared on reruns ----
        # BUT: If widget exists with stale zero and shared/default has meaningful value, fix it
        value_before_seed = st.session_state.get(original_key)
        widget_is_stale_zero = (value_before_seed is None) or (
            (value_before_seed in (0, 0.0)) and (shared_key and not zero_allowed(shared_key))
        )
        
        # Check if shared OR default is meaningful (shared might be 0, but default might not be)
        shared_is_meaningful = effective_default not in (None, "", 0, 0.0)
        default_is_meaningful = default not in (None, "", 0, 0.0)
        has_meaningful_value = shared_is_meaningful or default_is_meaningful
        
        # CRITICAL: If widget is stale zero but shared/default is meaningful, fix the widget
        # This handles the case where shared state was overwritten to 0 by another page
        # BUT: Allow 0 for allow-zero keys (like reo counts)
        if original_key.startswith("inputs_") and widget_is_stale_zero and has_meaningful_value:
            # Check if this is a protected key (geometry, materials, design actions)
            # BUT exclude allow-zero keys (where 0 is legitimate)
            protected = (shared_key and (shared_key in NONZERO_REQUIRED_SHARED_KEYS) and (not zero_allowed(shared_key)))
            if protected:
                # Prefer shared value if meaningful, otherwise use default
                fix_value = effective_default if shared_is_meaningful else default
                cur = st.session_state.get(original_key)
                st.session_state[original_key] = float(fix_value)
                _audit("WIDGET_GUARD forced widget", shared_key, original_key, old=cur, new=fix_value)
                # Also fix shared state if it's 0 but default is meaningful
                if not shared_is_meaningful and default_is_meaningful and shared_key:
                    old_shared = st.session_state.get(shared_key)
                # #region agent log
                try:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"location": "widgets_helpers.py:number_row", "message": "Fixed stale zero widget", "data": {"key": original_key, "shared_key": shared_key, "old_value": value_before_seed, "new_value": fix_value, "would_fix_shared": not shared_is_meaningful and default_is_meaningful}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "M"}) + "\n")
                except: pass
                # #endregion
        
        if original_key not in st.session_state:
            try:
                st.session_state[original_key] = float(effective_default)
            except Exception:
                st.session_state[original_key] = effective_default
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "widgets_helpers.py:number_row", "message": "Seeded widget key", "data": {"key": original_key, "seeded_value": st.session_state[original_key], "effective_default": effective_default}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
            except: pass
            # #endregion
        else:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"location": "widgets_helpers.py:number_row", "message": "Widget key already exists", "data": {"key": original_key, "existing_value": st.session_state[original_key], "effective_default": effective_default}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
            except: pass
            # #endregion

        # ---- V2: DO NOT pass value= every rerun (lets session_state persist) ----
        # Safety net: never render a number input with a None session value
        if original_key in st.session_state and st.session_state.get(original_key) is None:
            st.session_state[original_key] = effective_default
        # Streamlit requires consistent numeric types across value/min/max/step.
        # This helper always configures number_input as float-style (format %.1f),
        # so coerce any pre-existing int session values to float before render.
        if original_key in st.session_state:
            current_num = st.session_state.get(original_key)
            if isinstance(current_num, (int, float)) and not isinstance(current_num, bool):
                st.session_state[original_key] = float(current_num)
        
        session_value_before_widget = st.session_state.get(original_key)
        _safe_label = _nonempty_label(str(label), f"_{original_key}_label")
        # Session state is seeded above; with key=, Streamlit reads the value from
        # st.session_state[original_key]. Do not pass value= — it competes with the
        # Session State API and triggers Streamlit warnings when the key is hydrated.
        ni_kwargs = dict(
            min_value=min_val,
            format="%.1f",
            label_visibility="collapsed",
            on_change=on_change_callback,
            disabled=disabled,
        )
        if step is not None:
            ni_kwargs["step"] = step
        else:
            ni_kwargs["step"] = 1.0
        value = st.number_input(_safe_label, key=original_key, **ni_kwargs)
        session_value_after_widget = st.session_state.get(original_key)

        # #region agent log
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps({"location": "widgets_helpers.py:number_row", "message": "Widget created", "data": {"key": original_key, "returned_value": value, "session_value_before": session_value_before_widget, "session_value_after": session_value_after_widget, "value_changed": session_value_before_widget != session_value_after_widget}, "timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
        except: pass
        # #endregion

    return value


def select_row(
    label,
    key,
    options,
    default=None,
    sync_callbacks=None,
    help_text: str | None = None,
    required: bool = False,
    on_change=None,
    args=None,
    kwargs=None,
    *,
    disabled: bool = False,
    use_columns: bool = True,
):
    """
    Selectbox row with label + hover help.
    Contract-safe:
      - seeds widget value ONCE only if key missing
      - never overwrites user edits on reruns
      - uses sync_callbacks + TAB_KEYS mapping like number_row
    """
    # Ensure args/kwargs are safe defaults
    args = args or ()
    kwargs = kwargs or {}

    original_key = key
    _safe_label = _nonempty_label(str(label), f"_{original_key}_label")
    _register_rendered_key(original_key)

    # options may be list[str] or list of things; convert to list for membership checks
    _opts = list(options) if not isinstance(options, dict) else list(options.keys())

    # Seed ONCE only
    if original_key not in st.session_state:
        # Prefer shared if present, otherwise default
        shared_key = TAB_KEYS.get(original_key)
        candidate = st.session_state.get(shared_key, default) if shared_key else default
        # Ensure candidate is one of the options; otherwise fallback safely
        if candidate in _opts:
            st.session_state[original_key] = candidate
        else:
            st.session_state[original_key] = default if default in _opts else _opts[0]

    on_change_final = on_change
    if on_change_final is None and sync_callbacks and isinstance(sync_callbacks, dict):
        on_change_final = sync_callbacks.get(original_key)
    if on_change_final is not None:
        on_change_final = _wrap_user_edit(original_key, on_change_final)
    def _coerce_current_value():
        cur = st.session_state.get(original_key, default)
        if cur in _opts:
            return cur

        # Migration map for renamed options (add pairs as needed)
        MIGRATIONS = {
            "General εₓ-based (Cl. 8.2.4.2)": "General εx-based (Cl. 8.2.4.2)",
        }
        migrated = MIGRATIONS.get(cur)
        if migrated in _opts:
            st.session_state[original_key] = migrated
            return migrated

        fallback = default if default in _opts else _opts[0]
        st.session_state[original_key] = fallback
        return fallback

    selectbox_kwargs = {
        "help": help_text,
        "on_change": on_change_final,
        "args": args,
        "kwargs": kwargs,
    }
    if isinstance(options, dict):
        selectbox_kwargs["format_func"] = lambda k: str(options.get(k, str(k)))

    # ---- SAFE: allow disabling internal columns for compact multi-column bands (reo rows) ----
    label_text = f"{_safe_label} *" if required else _safe_label
    if use_columns:
        col1, col2 = st.columns([1, 2], gap="medium")
        with col1:
            if help_text:
                label_with_hover(label_text, help_text, required=False)
            else:
                st.markdown(f"**{label_text}**")
        with col2:
            _ = _coerce_current_value()
            return st.selectbox(
                _safe_label,
                options=_opts,
                key=original_key,
                label_visibility="collapsed",
                disabled=disabled,
                **selectbox_kwargs,
            )
    if help_text:
        label_with_hover(label_text, help_text, required=False)
    else:
        st.markdown(f"**{label_text}**")
    _ = _coerce_current_value()
    return st.selectbox(
        _safe_label,
        options=_opts,
        key=original_key,
        label_visibility="collapsed",
        disabled=disabled,
        **selectbox_kwargs,
    )


def _render_reo_row_controls(
    *,
    mode: str,
    default_bars: int,
    default_dia: int,
    row_index: int,
    row_face: str,
    sync_callbacks: dict,
    count_options,
    spacing_options,
    dia_options,
    bars_key: str,
    spacing_key: str,
    dia_key: str,
    bars_shared_key: str,
    spacing_shared_key: str,
    dia_shared_key: str,
) -> None:
    """Bars or Spacing, then Ø (mm); label-left / widget-right rows; keys unchanged."""
    if mode == "Count":
        select_row(
            "Bars",
            bars_key,
            count_options,
            int(st.session_state.get(bars_shared_key, default_bars if row_index == 1 else 0)),
            sync_callbacks,
            help_text=f"Number of bars in {row_face} row {row_index}.",
        )
    else:
        select_row(
            "Spacing",
            spacing_key,
            spacing_options,
            int(st.session_state.get(spacing_shared_key, 200)),
            sync_callbacks,
            help_text=f"Centre-to-centre spacing for {row_face} row {row_index} (mm).",
        )
    select_row(
        "Ø (mm)",
        dia_key,
        dia_options,
        int(st.session_state.get(dia_shared_key, default_dia)),
        sync_callbacks,
        help_text=f"Nominal bar diameter for {row_face} row {row_index} (mm).",
    )


def _longitudinal_reo_sync_row_count_state(
    *, page_prefix: str, section: str, max_rows: int
) -> tuple[str, str, str, str, int]:
    """
    Normalize section (bot/top), read clamped row count, refresh memory key only.

    Do not assign to row_count_widget_key here: this runs both inside the info popover
    (before/after the Rows select) and again in render_longitudinal_reo_rows; writing
    the widget key after the Rows widget is instantiated raises StreamlitAPIException.
    The Rows widget owns that session key once rendered; callbacks may update it.

    Returns (section_norm, row_count_shared_key, row_count_widget_key, row_count_memory_key, current_row_count).
    """
    section_norm = "top" if section == "top" else "bot"
    row_count_shared_key = f"{section_norm}_row_count"
    row_count_widget_key = f"{page_prefix}_{section_norm}_row_count"
    row_count_memory_key = f"_{page_prefix}_{section_norm}_row_count_previous"
    current_row_count = int(
        st.session_state.get(row_count_widget_key, st.session_state.get(row_count_shared_key, 1)) or 1
    )
    current_row_count = max(1, min(max_rows, current_row_count))
    st.session_state[row_count_memory_key] = current_row_count
    return section_norm, row_count_shared_key, row_count_widget_key, row_count_memory_key, current_row_count


def render_longitudinal_reo_row_config_controls(
    *,
    page_prefix: str,
    section: str,
    sync_callbacks: dict,
    max_rows: int = 4,
    rowgap_widget_key: str | None = None,
    rowgap_default: float = 60.0,
    rowgap_help_text: str | None = None,
    sec_shape: str | None = None,
) -> None:
    """
    Row count and layer row-gap controls for one longitudinal reo column.
    Render inside that column's top-right info popover; same widget keys as before.
    """
    (
        section_norm,
        row_count_shared_key,
        row_count_widget_key,
        row_count_memory_key,
        current_row_count,
    ) = _longitudinal_reo_sync_row_count_state(page_prefix=page_prefix, section=section, max_rows=max_rows)

    _row_face = longitudinal_reo_row_help_face(sec_shape, section_norm)

    st.markdown("**Row configuration**")
    st.caption("Number of layers and vertical gap between layers (when more than one row is used).")

    def _on_row_count_change():
        new_count = int(st.session_state.get(row_count_widget_key, current_row_count) or current_row_count)
        new_count = max(1, min(max_rows, new_count))
        old_count = int(st.session_state.get(row_count_memory_key, current_row_count) or current_row_count)
        set_shared(row_count_shared_key, new_count, source=f"{page_prefix}:set_reo_row_count")
        if new_count < old_count:
            for row_index in range(new_count + 1, old_count + 1):
                set_shared(f"{section_norm}_row_{row_index}_bars", 0, source=f"{page_prefix}:set_reo_row_count")
                set_shared(f"{section_norm}_row_{row_index}_spacing", 0.0, source=f"{page_prefix}:set_reo_row_count")
                st.session_state[f"{page_prefix}_{section_norm}_row_{row_index}_bars"] = 0
                st.session_state[f"{page_prefix}_{section_norm}_row_{row_index}_spacing"] = 0.0
        st.session_state[row_count_widget_key] = new_count
        st.session_state[row_count_memory_key] = new_count

    select_row(
        "Rows",
        row_count_widget_key,
        list(range(1, max_rows + 1)),
        current_row_count,
        None,
        help_text=f"Choose how many {_row_face} reinforcement rows to show.",
        on_change=_on_row_count_change,
    )

    if rowgap_widget_key:
        n_for_gap = int(
            st.session_state.get(row_count_widget_key, current_row_count) or current_row_count
        )
        n_for_gap = max(1, min(max_rows, n_for_gap))
        number_row(
            "Row gap",
            rowgap_widget_key,
            float(rowgap_default),
            sync_callbacks,
            help_text=rowgap_help_text
            or "Clear vertical gap between reinforcement rows (mm).",
            disabled=n_for_gap < 2,
        )
        if n_for_gap < 2:
            st.caption("Row gap applies when two or more rows are enabled.")


def render_longitudinal_reo_rows(
    *,
    page_prefix: str,
    section: str,
    sync_callbacks: dict,
    title: str | None = None,
    layout_modes,
    count_options,
    spacing_options,
    dia_options,
    max_rows: int = 4,
    single_column: bool = False,
    sec_shape: str | None = None,
):
    """
    Each reinforcement row: Layout, then Bars or Spacing, then Ø (mm) as label-left / widget-right rows.
    Row count and row gap render in the column info popover.
    single_column is ignored (kept for call-site compatibility).
    """
    _ = single_column
    section_norm, _, _, _, current_row_count = _longitudinal_reo_sync_row_count_state(
        page_prefix=page_prefix, section=section, max_rows=max_rows
    )
    row_face = longitudinal_reo_row_help_face(sec_shape, section_norm)
    default_bars = 2 if section_norm == "top" else 4
    default_dia = 16 if section_norm == "top" else 20

    if title:
        st.markdown(title)

    for row_index in range(1, current_row_count + 1):
        st.markdown(f'<div class="reo-layer-title">Row {row_index}</div>', unsafe_allow_html=True)
        mode_key = f"{page_prefix}_{section_norm}_row_{row_index}_mode"
        bars_key = f"{page_prefix}_{section_norm}_row_{row_index}_bars"
        spacing_key = f"{page_prefix}_{section_norm}_row_{row_index}_spacing"
        dia_key = f"{page_prefix}_{section_norm}_row_{row_index}_dia"
        mode_shared_key = f"{section_norm}_row_{row_index}_mode"
        bars_shared_key = f"{section_norm}_row_{row_index}_bars"
        spacing_shared_key = f"{section_norm}_row_{row_index}_spacing"
        dia_shared_key = f"{section_norm}_row_{row_index}_dia"

        select_row(
            "Layout",
            mode_key,
            layout_modes,
            st.session_state.get(mode_shared_key, "Count"),
            sync_callbacks,
            help_text=f"Choose whether Row {row_index} uses bar count or spacing.",
        )
        mode = st.session_state.get(mode_key, st.session_state.get(mode_shared_key, "Count"))
        _render_reo_row_controls(
            mode=mode,
            default_bars=default_bars,
            default_dia=default_dia,
            row_index=row_index,
            row_face=row_face,
            sync_callbacks=sync_callbacks,
            count_options=count_options,
            spacing_options=spacing_options,
            dia_options=dia_options,
            bars_key=bars_key,
            spacing_key=spacing_key,
            dia_key=dia_key,
            bars_shared_key=bars_shared_key,
            spacing_shared_key=spacing_shared_key,
            dia_shared_key=dia_shared_key,
        )


def show_reo_message(msg_key: str, layer: str = "", s_min: float = None):
    """Show a reinforcement message based on session state key."""
    if msg_key == "spacing_clamped":
        s_min_val = s_min if s_min is not None else 25.0
        msg = f"⚠️ **{layer} spacing clamped**: Minimum spacing of {s_min_val:.1f} mm applied to meet code requirements."
    else:
        messages = {
            "auto_layer2": f"💡 **Auto-placed {layer}**: The second layer was automatically added to meet spacing requirements.",
            "layer2_overwritten": f"⚠️ **{layer} overwritten**: You manually changed the second layer, so auto-placement is disabled.",
        }
        msg = messages.get(msg_key, "")
    
    if msg:
        st.info(msg)


def info_i_button(content=None, help_text=None, key=None, use_container_width=False):
    """
    Render a small blue "i" icon info button that opens a popover.
    
    Args:
        content: Callable function that renders content inside the popover, or None if using help_text
        help_text: Optional help text (alternative to content function)
        key: Optional unique key for the popover (not supported by st.popover, ignored)
        use_container_width: Whether to use container width (for content function)
    
    Returns:
        The popover context manager
    """
    # Use "i" as the trigger text (lowercase i, no emoji, no arrow)
    trigger_text = "i"
    
    # Create popover with appropriate parameters
    # Note: st.popover() doesn't support 'key' parameter, so we ignore it
    if help_text:
        return st.popover(trigger_text, help=help_text)
    else:
        kwargs = {}
        if use_container_width:
            kwargs["use_container_width"] = use_container_width
        return st.popover(trigger_text, **kwargs)


def render_calc_section_heading(text: str) -> None:
    """
    Bold calc-section title with minimal gap before ``render_expandable_step`` below.
    Streamlit's default ``st.markdown("**…**")`` uses a ``<p>`` with large bottom margin.
    """
    import html as _html

    st.markdown(
        f'<p class="calc-section-heading-tight">{_html.escape(text)}</p>',
        unsafe_allow_html=True,
    )


def page_divider():
    """
    Render a consistent page divider between major sections.
    
    Use page_divider() for all section breaks. Do not insert raw dividers elsewhere.
    This ensures consistent spacing and visual rhythm across all pages.
    
    Allowed locations:
    - Between major page sections (Summary → Steps, Inputs → Results)
    - Between top-level headings (st.header / page sections)
    - Between major design check blocks
    
    Not allowed:
    - Between individual widgets
    - Between rows in a column
    - Inside expandable steps
    - Inside calc boxes
    - Before or after info popovers
    """
    st.divider()


def calcbox(
    md: str,
    status: str | None = None,
    uid: str | None = None,
    accent: str | None = None,
):
    """
    Render a status-aware calculation box with LaTeX support.
    
    Args:
        md: Markdown content (with LaTeX using \[ \] or \( \))
        status: "pass" (green), "fail" (red), or None (blue / accent)
        uid: Unique identifier for CSS scoping (auto-generated if None)
        accent: optional theme key (load, support, reaction, fe, shear, moment); ignored if status is pass/fail
    """
    # Generate unique ID if not provided
    if uid is None:
        if "_cb_i" not in st.session_state:
            st.session_state["_cb_i"] = 0
        st.session_state["_cb_i"] += 1
        uid = f"cb_{st.session_state['_cb_i']}"
    
    # --- normalise status so calcbox accepts the same labels as the step summaries ---
    if isinstance(status, bool):
        status = "pass" if status else "fail"
    elif isinstance(status, str):
        s = status.strip().lower()
        if s in ("pass", "ok", "✅", "true"):
            status = "pass"
        elif s in ("fail", "check", "ng", "❌", "false"):
            status = "fail"
        else:
            status = None
    
    # Convert LaTeX markers: \[ \] → $$ $$, \( \) → $ $
    md_converted = md
    md_converted = re.sub(r'\\\[', '$$', md_converted)
    md_converted = re.sub(r'\\\]', '$$', md_converted)
    md_converted = re.sub(r'\\\(', '$', md_converted)
    md_converted = re.sub(r'\\\)', '$', md_converted)
    
    # If md already contains blockquote formatting, keep it.
    # Otherwise, convert it to a blockquote.
    lines = md_converted.splitlines()
    already_blockquote = any(l.lstrip().startswith(">") for l in lines)
    
    if already_blockquote:
        blockquote_md = md_converted
    else:
        blockquote_md = "\n".join([f"> {l}" if l.strip() else ">" for l in lines])
    
    # Inject scoped CSS for status / accent
    accent_key = _normalize_calc_accent(accent)
    if status == "pass":
        border_color = "#28a745"
        bg_color = "rgba(40, 167, 69, 0.1)"
    elif status == "fail":
        border_color = "#dc3545"
        bg_color = "rgba(220, 53, 69, 0.1)"
    elif accent_key and accent_key in _CALC_ACCENTS:
        border_color, bg_color = _CALC_ACCENTS[accent_key]
    else:
        border_color = "#1f77b4"
        bg_color = "rgba(31, 119, 180, 0.08)"
    
    css = f"""
<style>
/* Style the blockquote that lives in the same element-container as our marker span */
div.element-container:has(span#{uid}) blockquote {{
  border-left: 4px solid {border_color} !important;
  background-color: {bg_color} !important;
  padding: 0.75rem 1rem !important;
  border-radius: 10px !important;
}}
</style>
"""
    
    st.markdown(css, unsafe_allow_html=True)
    
    # Marker + markdown MUST be in the same st.markdown call
    st.markdown(f"<span id='{uid}'></span>\n\n{blockquote_md}", unsafe_allow_html=True)


def clickable_calcbox(
    *,
    uid: str,
    status: str | None = None,
    summary_html: str,
    details_html: str,
    height: int = 520,
):
    """
    Render a clickable, expandable calculation box with MathJax support.
    
    Args:
        uid: Unique identifier for this calcbox
        status: "pass" (green), "fail" (red), or None (blue)
        summary_html: HTML for the collapsed summary (no LaTeX)
        details_html: Markdown/HTML for expanded details (with LaTeX)
        height: Expanded height in pixels (default 520)
    """
    # Determine colors based on status
    if status == "pass":
        border_color = "#28a745"
        bg_color = "rgba(40, 167, 69, 0.1)"
        css_class = "calcbox-pass"
    elif status == "fail":
        border_color = "#dc3545"
        bg_color = "rgba(220, 53, 69, 0.1)"
        css_class = "calcbox-fail"
    else:
        border_color = "#1f77b4"
        bg_color = "rgba(31, 119, 180, 0.08)"
        css_class = "calcbox-neutral"
    
    # Parse summary to extract title, includes, result
    # Remove markdown bold, LaTeX, HTML tags
    summary_clean = summary_html
    summary_clean = re.sub(r'\*\*(.+?)\*\*', r'\1', summary_clean)
    summary_clean = re.sub(r'\$.*?\$', '', summary_clean)
    summary_clean = re.sub(r'<[^>]+>', '', summary_clean)
    
    # Extract title (first line, bold)
    lines = summary_html.split('\n')
    title_text = ""
    includes_text = ""
    result_text = ""
    
    for line in lines:
        line_clean = re.sub(r'<[^>]+>', '', line)
        if "Step" in line_clean or "**Step" in line:
            title_text = re.sub(r'\*\*(.+?)\*\*', r'\1', line_clean).strip()
        elif "Includes:" in line_clean or "includes:" in line_clean.lower():
            includes_text = line_clean.replace("Includes:", "").replace("includes:", "").strip()
        elif "Result:" in line_clean or "result:" in line_clean.lower():
            result_text = line_clean.replace("Result:", "").replace("result:", "").strip()
    
    # Fallback parsing if structured format not found
    if not title_text:
        title_text = lines[0] if lines else "Calculation"
        title_text = re.sub(r'\*\*(.+?)\*\*', r'\1', title_text)
        title_text = re.sub(r'<[^>]+>', '', title_text).strip()
    
    if not includes_text and len(lines) > 1:
        includes_text = lines[1] if len(lines) > 1 else ""
        includes_text = re.sub(r'<[^>]+>', '', includes_text).strip()
    
    if not result_text and len(lines) > 2:
        result_text = lines[2] if len(lines) > 2 else ""
        result_text = re.sub(r'<[^>]+>', '', result_text).strip()
    
    # Convert details_html markdown to HTML
    details_formatted = details_html
    # Convert LaTeX markers: \[ \] → $$ $$, \( \) → $ $
    details_formatted = re.sub(r'\\\[', '$$', details_formatted)
    details_formatted = re.sub(r'\\\]', '$$', details_formatted)
    details_formatted = re.sub(r'\\\(', '$', details_formatted)
    details_formatted = re.sub(r'\\\)', '$', details_formatted)
    
    # Convert markdown to HTML for details
    details_html_content = details_formatted
    # Convert **bold** to <strong>
    details_html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', details_html_content)
    # Convert *italic* to <em>
    details_html_content = re.sub(r'(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', details_html_content)
    # Convert headers
    details_html_content = re.sub(r'^### (.+)$', r'<h4>\1</h4>', details_html_content, flags=re.MULTILINE)
    details_html_content = re.sub(r'^## (.+)$', r'<h3>\1</h3>', details_html_content, flags=re.MULTILINE)
    details_html_content = re.sub(r'^# (.+)$', r'<h3>\1</h3>', details_html_content, flags=re.MULTILINE)
    # Convert horizontal rules
    details_html_content = re.sub(r'^---$', r'<hr>', details_html_content, flags=re.MULTILINE)
    # Convert bullet points
    lines = details_html_content.split('\n')
    in_list = False
    result_lines = []
    for line in lines:
        if line.strip().startswith('- '):
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            result_lines.append(f'<li>{line.strip()[2:]}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if line.strip():
                # Preserve lines with LaTeX delimiters as-is
                if '$$' in line or '\\[' in line or '\\]' in line or '\\(' in line or '\\)' in line:
                    result_lines.append(line)
                elif line.strip().startswith('<'):
                    result_lines.append(line)
                else:
                    result_lines.append(f'<p>{line}</p>')
            else:
                result_lines.append('<br>')
    if in_list:
        result_lines.append('</ul>')
    details_html_content = '\n'.join(result_lines)
    
    # Build vertical summary
    summary_vertical = f"""
    <div class="sum-title">{title_text}</div>
    <div class="sum-includes">Includes: {includes_text}</div>
    <div class="sum-result">Result: {result_text}</div>
    <div class="chev">▸</div>
    """
    
    expanded_height = height
    
    # CSS
    css = f"""
    <style>
    body {{
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        font-size: 14px;
        line-height: 1.25;
        color: #222;
    }}
    body, details, summary {{
        font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        font-size: 14px;
        line-height: 1.25;
        color: #222;
    }}
    b, strong, .sum-title {{
        font-weight: 600;
    }}
    html, body {{
        margin: 0;
        padding: 0;
        height: 100%;
        overflow: hidden;
    }}
    #wrap-{uid} {{
        height: auto;
        overflow: hidden;
    }}
    .{css_class} {{
        border-left: 4px solid {border_color} !important;
        background-color: {bg_color} !important;
        padding: 0.50rem 0.70rem !important;
        margin: 0.12rem 0 0.35rem 0 !important;
        border-radius: 0 6px 6px 0 !important;
        color: #222 !important;
    }}
    
    .{css_class} details {{
        border: none !important;
        background: transparent !important;
        margin: 0.12rem 0 0.35rem 0 !important;
        padding: 0.50rem 0.70rem !important;
    }}
    
    .{css_class} summary {{
        cursor: pointer !important;
        list-style: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }}
    
    .{css_class} summary::-webkit-details-marker {{
        display: none !important;
    }}
    
    .{css_class} .sum-title {{
        font-weight: 600;
        margin-bottom: 2px;
    }}
    
    .{css_class} .sum-includes {{
        font-size: 13px;
        color: rgba(50, 50, 50, 0.85);
        margin-bottom: 2px;
    }}
    
    .{css_class} .sum-result {{
        font-size: 13px;
    }}
    
    .{css_class} .chev {{
        float: right;
        font-size: 14px;
        opacity: 0.75;
        margin-top: -2px;
        transition: transform 0.2s ease;
    }}
    
    .{css_class} details[open] .chev {{
        transform: rotate(90deg);
    }}
    
    .{css_class} .details-body {{
        display: none;
    }}
    
    .{css_class} details[open] .details-body {{
        display: block;
    }}
    
    .{css_class} .details-content {{
        margin-top: 0.45rem;
        padding-top: 0.35rem;
        border-top: 1px solid rgba(0, 0, 0, 0.12);
        max-height: calc({expanded_height}px - 110px);
        overflow-y: auto;
        padding-right: 6px;
    }}
    
    .{css_class} .details-content p {{
        color: #222 !important;
        margin: 0.15rem 0 !important;
    }}
    
    .{css_class} .details-content ul {{
        margin: 0.15rem 0 0.25rem 1.1rem !important;
    }}
    
    .{css_class} .details-content li {{
        margin: 0.10rem 0 !important;
    }}
    
    .{css_class} .details-content br {{
        line-height: 1.05;
    }}
    
    .{css_class} .details-content * {{
        color: #222 !important;
    }}
    
    .{css_class} .details-content p:first-child {{
        margin-top: 0 !important;
    }}
    
    .{css_class} .details-content p:last-child {{
        margin-bottom: 0 !important;
    }}
    
    .{css_class} .details-content mjx-container[jax="CHTML"][display="true"] {{
        margin: 0.25rem 0 !important;
    }}
    
    .{css_class} .details-content mjx-container {{
        font-size: 1.0em !important;
    }}
    </style>
    """
    
    # Full HTML with MathJax
    full_html = f"""
    {css}
    <script>
      window.MathJax = {{
        tex: {{
          inlineMath: [['$', '$'], ['\\(', '\\)']],
          displayMath: [['$$','$$'], ['\\[','\\]']],
          processEscapes: true
        }},
        chtml: {{
          linebreaks: {{ automatic: false }}
        }},
        options: {{
          skipHtmlTags: ['script','noscript','style','textarea','pre','code']
        }}
      }};
    </script>
    <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
    <div id="wrap-{uid}">
        <div class="{css_class}">
            <details id="cb-{uid}">
                <summary>{summary_vertical}</summary>
                <div class="details-body">
                    <div class="details-content" id="details-{uid}">
                        <div class="mj-target" id="mj_target__{uid}">
                            {details_html_content}
                        </div>
                    </div>
                </div>
            </details>
        </div>
    </div>
    <script>
    const UID = '{uid}';
    
    function typeset(uid) {{
        if (!(window.MathJax && MathJax.typesetPromise)) return;
        const el = document.getElementById('mj_target__' + uid);
        if (!el) return;
        return MathJax.typesetPromise([el]);
    }}
    
    const wrap = document.getElementById('wrap-{uid}');
    const d = document.getElementById('cb-{uid}');
    const EXP = {expanded_height};
    
    function setCollapsed() {{
        const summary = d.querySelector('summary');
        const h = summary.getBoundingClientRect().height + 8;
        wrap.style.height = h + 'px';
        document.body.style.height = h + 'px';
    }}
    
    function setExpanded() {{
        wrap.style.height = EXP + 'px';
        document.body.style.height = EXP + 'px';
    }}
    
    function syncChevronAndHeights() {{
        if (d.open) {{
            setExpanded();
        }} else {{
            setCollapsed();
        }}
        const chev = d.querySelector('.chev');
        if (chev) chev.textContent = d.open ? '▾' : '▸';
    }}
    
    d.addEventListener('toggle', function() {{
        syncChevronAndHeights();
        // Notify parent window of expansion state (for diagram visibility)
        if (window.parent && window.parent !== window) {{
            window.parent.postMessage({{
                type: 'calcbox_toggle',
                uid: UID,
                open: d.open
            }}, '*');
        }}
        if (d.open) {{
            requestAnimationFrame(function() {{
                setTimeout(function() {{
                    typeset(UID);
                }}, 80);
            }});
        }}
    }});
    
    window.addEventListener('load', function() {{
        syncChevronAndHeights();
        setTimeout(function() {{
            typeset(UID);
        }}, 80);
    }});
    
    window.addEventListener('resize', function() {{
        if (!d.open) setCollapsed();
    }});
    
    // MutationObserver for dynamic content changes
    let t = null;
    const mjTarget = document.getElementById('mj_target__' + UID);
    if (mjTarget) {{
        const obs = new MutationObserver(function() {{
            if (!d.open) return;
            clearTimeout(t);
            t = setTimeout(function() {{
                typeset(UID);
            }}, 120);
        }});
        obs.observe(mjTarget, {{ childList: true, subtree: true }});
    }}
    </script>
    """
    
    components.html(full_html, height=expanded_height, scrolling=False)


# ============================================================
#  STEP EXPANDER HELPER - Single source of truth
# ============================================================
def render_step(step_id: str, title: str, summary_md: str, body_fn: callable, status=None, summary_mode: bool = True):
    """Render a step as an expandable card with summary header."""
    # Apply CSS for expander styling
    apply_step_summary_expander_css()
    
    # Determine status class using the helper
    status_class = status_to_class(status)
    
    with st.expander(f"**{title}**  \n{summary_md}", expanded=not summary_mode):
        # Marker span inside expander for CSS targeting
        st.markdown(f"<span class='{status_class}'></span>", unsafe_allow_html=True)
        body_fn()


def render_jumpable_step(
    *,
    uid: str,
    title: str,
    summary_md: str,
    body_fn: callable,
    expanded: bool,
    status=None,
):
    """
    Exactly like render_step(), but:
      - injects an anchor div id="calc_<uid>"
      - allows expanded control from ?jump=<uid>
      - flashes when expanded
    """
    # Apply CSS for expander styling
    apply_step_summary_expander_css()
    
    # Determine status class using the helper
    status_class = status_to_class(status)
    
    # anchor for scroll
    st.markdown(f"<div id='calc_{uid}'></div>", unsafe_allow_html=True)
    # marker that JS uses to find the next expander
    st.markdown(f"<div data-calc-uid='{uid}'></div>", unsafe_allow_html=True)

    with st.expander(f"**{title}**  \n{summary_md}", expanded=expanded):
        # Marker span inside expander for CSS targeting
        st.markdown(f"<span class='{status_class}'></span>", unsafe_allow_html=True)
        if expanded:
            st.markdown("<div class='flash'>", unsafe_allow_html=True)
            body_fn()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            body_fn()


# ============================================================
#  V2-SAFE WIDGET WRAPPERS (seed once, never pass value=/index=)
# ============================================================

def v2_number_input(*, label, key, default, min_value=None, max_value=None, step=None,
                    format=None, help=None, disabled=False, label_visibility="visible",
                    on_change=None):
    """V2-safe number_input: seed once, then never pass value= again."""
    key = resolve_widget_key(key)
    _register_rendered_key(key)
    if on_change is not None:
        on_change = _wrap_user_edit(key, on_change)
    if key not in st.session_state:
        st.session_state[key] = default
    # Safety net: never render a number input with a None session value
    if key in st.session_state and st.session_state.get(key) is None:
        st.session_state[key] = default
    return st.number_input(
        label,
        key=key,
        min_value=min_value,
        max_value=max_value,
        step=step,
        format=format,
        help=help,
        disabled=disabled,
        label_visibility=label_visibility,
        on_change=on_change,
    )


def v2_checkbox(*, label, key, default=False, help=None, disabled=False, label_visibility="visible",
                on_change=None):
    """V2-safe checkbox: seed once, then never pass value= again."""
    key = resolve_widget_key(key)
    _register_rendered_key(key)
    if on_change is not None:
        on_change = _wrap_user_edit(key, on_change)
    if key not in st.session_state:
        st.session_state[key] = bool(default)
    return st.checkbox(
        label,
        key=key,
        help=help,
        disabled=disabled,
        label_visibility=label_visibility,
        on_change=on_change,
    )


def v2_selectbox(*, label, key, options, default_index=0, format_func=None,
                 help=None, disabled=False, label_visibility="visible", on_change=None):
    """V2-safe selectbox: seed once, then never pass index= again."""
    key = resolve_widget_key(key)
    _register_rendered_key(key)
    if on_change is not None:
        on_change = _wrap_user_edit(key, on_change)
    if key not in st.session_state:
        # seed with the option value itself (not index)
        st.session_state[key] = options[default_index]
    kwargs = {
        "label": label,
        "options": options,
        "key": key,
        "help": help,
        "disabled": disabled,
        "label_visibility": label_visibility,
        "on_change": on_change,
    }
    if format_func is not None:
        kwargs["format_func"] = format_func
    return st.selectbox(**kwargs)


def v2_radio(*, label, key, options, default_index=0, format_func=None,
             help=None, disabled=False, horizontal=False, label_visibility="visible",
             on_change=None):
    """V2-safe radio: seed once, then never pass index= again."""
    key = resolve_widget_key(key)
    _register_rendered_key(key)
    if key not in st.session_state:
        st.session_state[key] = options[default_index]
    kwargs = {
        "label": label,
        "options": options,
        "key": key,
        "help": help,
        "disabled": disabled,
        "horizontal": horizontal,
        "label_visibility": label_visibility,
        "on_change": on_change,
    }
    if format_func is not None:
        kwargs["format_func"] = format_func
    return st.radio(**kwargs)
