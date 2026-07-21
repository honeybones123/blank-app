from __future__ import annotations

import streamlit as st


def apply_inputs_page_css():
    # Main block padding is applied app-wide via apply_global_widget_css() in app.py.

    # Extra CSS so special widgets (side cover + exposure class)
    # use the same effective width as the standard number_row inputs.
    st.markdown(
        """
        <style>
        .nr-field select,
        .nr-field input {
            width: 100% !important;
        }

        /* Remove any container framing around Plotly charts */
        div[data-testid="stPlotlyChart"], 
        div[data-testid="stPlotlyChart"] > div,
        div[data-testid="stPlotlyChart"] > div > div {
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }
        .inputs-page-main-diagram-wrap {
            margin: 0;
            padding: 0;
        }
        /* Main inputs diagram: cap height to reduce overflow (complements reduced Plotly layout height) */
        .inputs-page-main-diagram-wrap div[data-testid="stPlotlyChart"] {
            max-height: min(52vh, 560px);
        }
        @media print {
          .inputs-diagram-materials-group {
            break-inside: avoid;
            page-break-inside: avoid;
          }
        }
        .fast-start-here {
            background: rgba(30, 41, 59, 0.12);
            border: 1px solid rgba(30, 41, 59, 0.22);
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
            border-radius: 14px;
            padding: 1rem 1rem;
            margin: 0.25rem 0 1rem 0;
        }
        .fast-start-here-kicker {
            font-size: 0.8rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(15, 23, 42, 0.82);
            margin-bottom: 0.2rem;
        }
        .fast-start-here-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: rgba(15, 23, 42, 0.96);
        }
        .fast-phase-label {
            margin: 0.45rem 0 0.45rem 0;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: rgba(100, 116, 139, 0.95);
        }
        .fast-next-hint {
            background: rgba(59, 130, 246, 0.09);
            border: 1px solid rgba(59, 130, 246, 0.18);
            color: rgba(30, 64, 175, 0.95);
            border-radius: 12px;
            padding: 0.55rem 0.8rem;
            margin: 0.15rem 0 0.55rem 0;
            font-size: 0.92rem;
            font-weight: 600;
        }
        .fast-next-hint.fast-next-hint--design-guide-follow {
            display: block;
            width: 100%;
            box-sizing: border-box;
            margin-top: 0.65rem;
            margin-bottom: 0.15rem;
        }
        .stButton > button {
            padding-top: 0.35rem !important;
            padding-bottom: 0.35rem !important;
        }
        .stMarkdown h2, .stMarkdown h3 {
            margin-top: 0.6rem !important;
            margin-bottom: 0.25rem !important;
        }
        .stMarkdown h2 {
            font-size: 1.65rem !important;
            font-weight: 800 !important;
        }
        .stMarkdown h3 {
            font-size: 1.35rem !important;
            font-weight: 800 !important;
        }
        .fast-live-checks {
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.9);
            padding: 0.7rem 0.85rem;
            margin-top: 0.55rem;
        }
        .fast-live-check-row {
            display: grid;
            grid-template-columns: 1.3fr 0.8fr 0.7fr;
            gap: 0.5rem;
            align-items: center;
            padding: 0.3rem 0;
            border-top: 1px solid rgba(49, 51, 63, 0.08);
            font-size: 0.92rem;
        }
        .fast-live-check-row:first-of-type {
            border-top: none;
        }
        .fast-live-check-status {
            text-align: right;
            font-weight: 700;
        }
        .fast-guidance-item {
            border-top: 1px solid rgba(49, 51, 63, 0.08);
            border-left: 4px solid transparent;
            border-radius: 10px;
            padding: 0.92rem 0.95rem;
            margin-top: 0.7rem;
            line-height: 1.42;
        }
        .fast-guidance-item:first-of-type {
            border-top: none;
            margin-top: 0;
        }
        .fast-guidance-item.fail {
            background: #FEF2F2;
            border-left-color: #dc2626;
        }
        .fast-guidance-item.warn {
            background: #FFF7ED;
            border-left-color: #f59e0b;
        }
        .fast-guidance-item.pass {
            background: #F0FDF4;
            border-left-color: #16a34a;
        }
        .fast-guidance-item.guidance-success {
            background: #ECFDF5;
            border-left-color: #15803d;
            border-top: none;
        }
        .fast-guidance-item.guidance-success .fast-guidance-badge.guidance-success {
            background: #15803d;
        }
        .fast-guidance-item.efficiency {
            background: #EFF6FF;
            border-left-color: #2563eb;
        }
        .fast-guidance-item.start {
            background: #F8FAFC;
            border-left-color: #64748b;
        }
        .fast-guidance-item.secondary {
            margin-top: 1rem;
            border-left-width: 3px;
            box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.12);
        }
        .fast-guidance-item.secondary.fail {
            background: #FFF7F7;
            border-left-color: rgba(220, 38, 38, 0.38);
        }
        .fast-guidance-item.secondary.warn {
            background: #FFFAF2;
            border-left-color: rgba(245, 158, 11, 0.42);
        }
        .fast-guidance-item.secondary.pass {
            background: #F7FCF8;
            border-left-color: rgba(22, 163, 74, 0.34);
        }
        .fast-guidance-item.secondary.efficiency {
            background: #F5F9FF;
            border-left-color: rgba(37, 99, 235, 0.34);
        }
        .fast-guidance-head {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.32rem;
        }
        .fast-guidance-badge {
            font-size: 0.68rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            padding: 0.18rem 0.48rem;
            border-radius: 999px;
            color: #fff;
        }
        .fast-guidance-badge.fail {
            background: #dc2626;
        }
        .fast-guidance-badge.warn {
            background: #f59e0b;
        }
        .fast-guidance-badge.pass {
            background: #16a34a;
        }
        .fast-guidance-badge.efficiency {
            background: #2563eb;
        }
        .fast-guidance-badge.start {
            background: #64748b;
        }
        .fast-guidance-item.secondary .fast-guidance-badge.fail {
            background: rgba(220, 38, 38, 0.82);
        }
        .fast-guidance-item.secondary .fast-guidance-badge.warn {
            background: rgba(245, 158, 11, 0.84);
        }
        .fast-guidance-item.secondary .fast-guidance-badge.pass {
            background: rgba(22, 163, 74, 0.8);
        }
        .fast-guidance-item.secondary .fast-guidance-badge.efficiency {
            background: rgba(37, 99, 235, 0.82);
        }
        .fast-guidance-title-wrap {
            display: inline-flex;
            flex-wrap: wrap;
            align-items: baseline;
            gap: 0.38rem;
        }
        .fast-guidance-title {
            font-weight: 800;
            font-size: 0.98rem;
        }
        .fast-guidance-title-util {
            font-size: 0.84rem;
            color: rgba(71, 85, 105, 0.88);
            font-weight: 600;
        }
        .fast-guidance-action {
            font-size: 0.93rem;
            line-height: 1.35;
        }
        .fast-guidance-primary {
            font-size: 0.98rem;
            line-height: 1.42;
            font-weight: 800;
            margin-top: 0.18rem;
            color: rgba(15, 23, 42, 0.96);
        }
        .fast-guidance-secondary {
            margin-top: 0.28rem;
            font-size: 0.84rem;
            color: rgba(71, 85, 105, 0.84);
        }
        .fast-guidance-reason {
            margin-top: 0.24rem;
            font-size: 0.83rem;
            color: rgba(71, 85, 105, 0.95);
        }
        .fast-guidance-proposed {
            margin-top: 0.32rem;
            padding: 0.5rem 0.55rem;
            border-radius: 8px;
            background: rgba(241, 245, 249, 0.75);
            border: 1px solid rgba(148, 163, 184, 0.35);
            font-size: 0.84rem;
            line-height: 1.45;
            color: rgba(30, 41, 59, 0.96);
        }
        .fast-guidance-levers {
            margin-top: 0.22rem;
            font-size: 0.81rem;
            color: rgba(100, 116, 139, 0.98);
        }
        .fast-guidance-list {
            margin: 0.45rem 0 0 1rem;
            padding: 0;
            color: rgba(51, 65, 85, 0.96);
            font-size: 0.88rem;
        }
        .fast-guidance-list li {
            margin: 0.16rem 0;
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"] {
            justify-content: flex-start;
            align-items: flex-start;
            text-align: left;
            white-space: normal;
            height: auto;
            min-height: 0;
            padding: 0.92rem 0.95rem;
            border-radius: 10px;
            border: 1px solid rgba(15, 23, 42, 0.12);
            border-left: 4px solid transparent;
            background: #ffffff;
            color: #0f172a;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
            opacity: 1 !important;
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 14px rgba(15, 23, 42, 0.10);
            border-color: rgba(15, 23, 42, 0.18);
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"]:disabled {
            opacity: 1 !important;
            cursor: default;
            transform: none;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
            border-color: rgba(15, 23, 42, 0.12);
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"] p {
            margin: 0;
            line-height: 1.42;
        }
        .element-container:has(.fast-guidance-action-anchor) + div button[kind="secondary"] em {
            color: rgba(71, 85, 105, 0.9);
        }
        .element-container:has(.fast-guidance-action-anchor--fail) + div button[kind="secondary"] {
            background: #FEF2F2;
            border-left-color: #dc2626;
        }
        .element-container:has(.fast-guidance-action-anchor--warn) + div button[kind="secondary"] {
            background: #FFF7ED;
            border-left-color: #f59e0b;
        }
        .element-container:has(.fast-guidance-action-anchor--pass) + div button[kind="secondary"] {
            background: #F0FDF4;
            border-left-color: #16a34a;
        }
        .element-container:has(.fast-guidance-action-anchor--efficiency) + div button[kind="secondary"] {
            background: #EFF6FF;
            border-left-color: #2563eb;
        }
        .element-container:has(.fast-guidance-action-anchor--start) + div button[kind="secondary"] {
            background: #F8FAFC;
            border-left-color: #64748b;
        }
        .element-container:has(.fast-guidance-action-anchor--secondary) + div button[kind="secondary"] {
            margin-top: 1rem;
            border-left-width: 3px;
            box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.12);
        }
        .element-container:has(.fast-guidance-action-anchor--secondary.fast-guidance-action-anchor--fail) + div button[kind="secondary"] {
            background: #FFF7F7;
            border-left-color: rgba(220, 38, 38, 0.38);
        }
        .element-container:has(.fast-guidance-action-anchor--secondary.fast-guidance-action-anchor--warn) + div button[kind="secondary"] {
            background: #FFFAF2;
            border-left-color: rgba(245, 158, 11, 0.42);
        }
        .element-container:has(.fast-guidance-action-anchor--secondary.fast-guidance-action-anchor--pass) + div button[kind="secondary"] {
            background: #F7FCF8;
            border-left-color: rgba(22, 163, 74, 0.34);
        }
        .element-container:has(.fast-guidance-action-anchor--secondary.fast-guidance-action-anchor--efficiency) + div button[kind="secondary"] {
            background: #F5F9FF;
            border-left-color: rgba(37, 99, 235, 0.34);
        }
        .fast-auto-design-summary {
            margin: 0.55rem 0 0.7rem 0;
            padding: 0.75rem 0.85rem;
            border-radius: 12px;
            border: 1px solid rgba(37, 99, 235, 0.18);
            background: rgba(239, 246, 255, 0.92);
        }
        .fast-auto-design-summary.success {
            border-color: rgba(22, 163, 74, 0.2);
            background: rgba(240, 253, 244, 0.94);
        }
        .fast-auto-design-summary-title {
            font-size: 0.92rem;
            font-weight: 800;
            color: rgba(15, 23, 42, 0.96);
            margin-bottom: 0.35rem;
        }
        .fast-auto-design-summary-step {
            font-size: 0.84rem;
            color: rgba(30, 41, 59, 0.92);
            margin-top: 0.16rem;
        }
        .element-container:has(.fast-guidance-action-anchor--static) + div button[kind="secondary"] em {
            color: rgba(100, 116, 139, 0.9);
        }
    </style>
    """,
        unsafe_allow_html=True,
    )


__all__ = ["apply_inputs_page_css"]
