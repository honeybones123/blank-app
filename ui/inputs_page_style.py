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
        .fast-model-placeholder {
            min-height: 7.5rem;
            border: 1px dashed rgba(100, 116, 139, 0.28);
            border-radius: 12px;
            background: rgba(148, 163, 184, 0.08);
            margin: 0.2rem 0 0.55rem 0;
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
            background: rgba(224,49,49,0.08);
            border-left-color: #e03131;
        }
        .fast-guidance-item.warn {
            background: rgba(240,140,0,0.08);
            border-left-color: #f08c00;
        }
        .fast-guidance-item.pass {
            background: rgba(47,158,68,0.08);
            border-left-color: #2f9e44;
        }
        .fast-guidance-item.guidance-success {
            background: rgba(47,158,68,0.08);
            border-left-color: #2f9e44;
            border-top: none;
        }
        .fast-guidance-item.guidance-success .fast-guidance-badge.guidance-success {
            background: #2f9e44;
        }
        .fast-guidance-item.efficiency {
            background: rgba(66,99,235,0.08);
            border-left-color: #4263eb;
        }
        .fast-guidance-item.start {
            background: #F8FAFC;
            border-left-color: #64748b;
        }
        .dg-card {
            border: 1px solid rgba(47,158,68,0.28);
            border-left: 5px solid #2f9e44;
            border-radius: 14px;
            padding: 0;
            margin-top: 0.7rem;
            background: rgba(47,158,68,0.08);
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            color: #1f2937;
        }
        .dg-card.fast-guidance-item {
            border-top: 1px solid rgba(47,158,68,0.28);
            padding: 0;
            line-height: 1.32;
        }
        details.dg-card summary {
            list-style: none;
        }
        details.dg-card summary::-webkit-details-marker {
            display: none;
        }
        .dg-card--action,
        .dg-card.efficiency.dg-card--action {
            background: rgba(66,99,235,0.08);
            border-color: rgba(66,99,235,0.28);
            border-left-color: #4263eb;
        }
        .fast-guidance-item.error.dg-card--action {
            background: rgba(224,49,49,0.08);
            border-color: rgba(224,49,49,0.28);
            border-left-color: #e03131;
        }
        .dg-card--pass,
        .dg-card.guidance-success {
            background: rgba(47,158,68,0.08);
            border-color: rgba(47,158,68,0.28);
            border-left-color: #2f9e44;
        }
        .dg-card--blocked,
        .dg-card.efficiency.dg-card--blocked {
            background: rgba(66,99,235,0.08);
            border-color: rgba(66,99,235,0.28);
            border-left-color: #4263eb;
        }
        .dg-card--warning,
        .dg-card.warn {
            background: rgba(240,140,0,0.08);
            border-color: rgba(240,140,0,0.28);
            border-left-color: #f08c00;
        }
        .dg-card--error,
        .dg-card.fail {
            background: rgba(224,49,49,0.08);
            border-color: rgba(224,49,49,0.28);
            border-left-color: #e03131;
        }
        .fast-guidance-item.dg-card.dg-card--pass,
        .fast-guidance-item.pass.dg-card.dg-card--pass,
        .fast-guidance-item.guidance-success.dg-card.dg-card--pass,
        .fast-guidance-item.efficiency.dg-card.dg-card--pass,
        .dg-card.dg-card--pass {
            background: rgba(47,158,68,0.08);
            border-color: rgba(47,158,68,0.28);
            border-left-color: #2f9e44;
        }
        body:has([data-testid="design-guide-card"]) [data-testid="design-guide-proof-pending"],
        body:has([data-testid="design-guide-card"]) .dg-proof-pending-shell {
            display: none !important;
        }
        .dg-header {
            display: block;
            padding: 1.05rem 1.55rem;
            cursor: pointer;
            user-select: none;
            list-style: none;
        }
        .dg-header::-webkit-details-marker {
            display: none;
        }
        .dg-header-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }
        details.dg-card[open] > .dg-header {
            border-bottom: 1px solid rgba(15, 23, 42, 0.08);
        }
        .dg-header-left {
            display: inline-flex;
            align-items: center;
            gap: 0.8rem;
            min-width: 0;
        }
        .dg-status-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 4.2rem;
            padding: 0.34rem 0.78rem;
            border-radius: 999px;
            background: #2f9e44;
            color: #fff;
            font-size: 0.78rem;
            font-weight: 900;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            white-space: nowrap;
        }
        .dg-status-pill--action { background: #4263eb; }
        .fast-guidance-item.error .dg-status-pill--action { background: #e03131; }
        .dg-status-pill--blocked { background: #4263eb; }
        .dg-status-pill--pass { background: #2f9e44; }
        .dg-status-pill--warning { background: #f08c00; }
        .dg-status-pill--error { background: #e03131; }
        .dg-title {
            font-size: 1.12rem;
            font-weight: 900;
            color: #1f2937;
            letter-spacing: 0;
            overflow-wrap: anywhere;
        }
        .dg-util-pill {
            display: inline-flex;
            align-items: center;
            border: 1px solid rgba(47,158,68,0.28);
            background: rgba(47,158,68,0.08);
            color: #2f9e44;
            border-radius: 999px;
            padding: 0.42rem 0.95rem;
            font-size: 0.86rem;
            font-weight: 800;
            white-space: nowrap;
        }
        .dg-header-right {
            display: inline-flex;
            align-items: center;
            gap: 0.6rem;
            margin-left: auto;
        }
        .dg-expand-toggle {
            width: 1.85rem;
            height: 1.85rem;
            border-radius: 999px;
            border: 1px solid rgba(15, 23, 42, 0.14);
            background: rgba(255, 255, 255, 0.72);
            color: #475569;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9rem;
            font-weight: 900;
        }
        details.dg-card[open] .dg-expand-toggle {
            transform: rotate(90deg);
        }
        .dg-summary-line {
            padding: 0 1.55rem 1.05rem 1.55rem;
            margin-top: -0.2rem;
            color: rgba(71, 85, 105, 0.94);
            font-size: 0.9rem;
            font-weight: 650;
        }
        details.dg-card[open] .dg-summary-line {
            display: none;
        }
        .dg-header .dg-summary-line {
            padding: 0.75rem 0 0 0;
            margin-top: 0;
        }
        .dg-expanded-body {
            padding: 1.05rem 1.55rem 0 1.55rem;
        }
        .dg-card .dg-expanded-body {
            display: none;
        }
        details.dg-card[open] > .dg-expanded-body {
            display: block;
        }
        details.dg-card[open] > .dg-summary-line {
            display: none;
        }
        details.dg-card[open] > .dg-header .dg-summary-line {
            display: none;
        }
        details.dg-card[open] > .dg-header .dg-expand-toggle {
            transform: rotate(90deg);
        }
        .dg-card--action .dg-util-pill {
            border-color: rgba(66,99,235,0.28);
            background: rgba(66,99,235,0.08);
            color: #4263eb;
        }
        .fast-guidance-item.error.dg-card--action .dg-util-pill {
            border-color: rgba(224,49,49,0.28);
            background: rgba(224,49,49,0.08);
            color: #e03131;
        }
        .dg-card--warning .dg-util-pill {
            border-color: rgba(240,140,0,0.28);
            background: rgba(240,140,0,0.08);
            color: #f08c00;
        }
        .dg-card--error .dg-util-pill {
            border-color: rgba(224,49,49,0.28);
            background: rgba(224,49,49,0.08);
            color: #e03131;
        }
        .dg-current-title,
        .dg-section-title {
            margin: 0.85rem 0 0.45rem 0;
            font-size: 0.96rem;
            font-weight: 900;
            color: #1f2937;
        }
        .dg-current-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
        }
        .dg-current-chip {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 0.72rem;
            align-items: center;
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 10px;
            padding: 0.72rem 0.85rem;
            min-width: 0;
        }
        .dg-current-marker {
            width: 1.35rem;
            height: 1.35rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9rem;
            font-weight: 900;
        }
        .dg-current-chip--green .dg-current-marker { color: #2f9e44; border: 2px solid rgba(47,158,68,0.72); background: #fff; }
        .dg-current-chip--amber .dg-current-marker { color: #f08c00; background: rgba(240,140,0,0.18); }
        .dg-current-chip--red .dg-current-marker { color: #e03131; background: rgba(224,49,49,0.08); }
        .dg-current-chip--grey .dg-current-marker { color: #64748b; background: rgba(100, 116, 139, 0.14); }
        .dg-current-main {
            font-size: 0.94rem;
            font-weight: 800;
            color: #111827;
        }
        .dg-current-status {
            margin-top: 0.16rem;
            font-size: 0.78rem;
            font-weight: 900;
            text-transform: uppercase;
        }
        .dg-current-chip--green .dg-current-status { color: #2f9e44; }
        .dg-current-chip--amber .dg-current-status { color: #f08c00; }
        .dg-current-chip--red .dg-current-status { color: #e03131; }
        .dg-current-chip--grey .dg-current-status { color: #64748b; }
        .dg-preview-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.45rem;
            margin: 0.7rem 0 0.9rem 0;
        }
        .dg-preview-row {
            background: rgba(255,255,255,0.76);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 10px;
            padding: 0.55rem 0.65rem;
            color: rgba(30, 41, 59, 0.96);
            font-size: 0.86rem;
            font-weight: 650;
        }
        .dg-reason-list {
            display: grid;
            gap: 0.45rem;
            margin-bottom: 0.85rem;
        }
        .dg-reason-row {
            display: grid;
            grid-template-columns: 2.1rem minmax(6rem, 8rem) 1fr;
            gap: 0.72rem;
            align-items: center;
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 10px;
            padding: 0.55rem 0.7rem;
            font-size: 0.88rem;
        }
        .dg-reason-icon {
            width: 1.55rem;
            height: 1.55rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(66,99,235,0.08);
            color: #4263eb;
            font-weight: 900;
        }
        .dg-reason-label {
            font-weight: 900;
            color: #1f2937;
        }
        .dg-reason-text {
            color: #334155;
            overflow-wrap: anywhere;
        }
        .dg-details-row {
            margin: 0.85rem -1.55rem 0 -1.55rem;
            border-top: 1px solid rgba(15, 23, 42, 0.08);
            padding: 0.72rem 1.55rem;
            color: #64748b;
            font-weight: 700;
        }
        .dg-details-row summary {
            cursor: pointer;
            list-style: none;
        }
        .dg-details-row summary::-webkit-details-marker {
            display: none;
        }
        .dg-details-body {
            margin-top: 0.55rem;
            font-size: 0.78rem;
            font-weight: 500;
            line-height: 1.45;
            color: #475569;
            max-height: 18rem;
            overflow: auto;
        }
        @media (max-width: 900px) {
            .dg-current-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .dg-header {
                align-items: flex-start;
                flex-direction: column;
            }
            .dg-header-right {
                margin-left: 0;
            }
            .dg-preview-grid {
                grid-template-columns: 1fr;
            }
            .dg-reason-row {
                grid-template-columns: 2rem 1fr;
            }
            .dg-reason-text {
                grid-column: 2 / -1;
            }
        }
        @media (max-width: 560px) {
            .dg-current-grid {
                grid-template-columns: 1fr;
            }
        }
        .fast-guidance-item.secondary {
            margin-top: 1rem;
            border-left-width: 3px;
            box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.12);
        }
        .fast-guidance-item.secondary.fail {
            background: rgba(224,49,49,0.08);
            border-left-color: rgba(224,49,49,0.28);
        }
        .fast-guidance-item.secondary.warn {
            background: rgba(240,140,0,0.08);
            border-left-color: rgba(240,140,0,0.28);
        }
        .fast-guidance-item.secondary.pass {
            background: rgba(47,158,68,0.08);
            border-left-color: rgba(47,158,68,0.28);
        }
        .fast-guidance-item.secondary.efficiency {
            background: rgba(66,99,235,0.08);
            border-left-color: rgba(66,99,235,0.28);
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
            background: #e03131;
        }
        .fast-guidance-badge.warn {
            background: #f08c00;
        }
        .fast-guidance-badge.pass {
            background: #2f9e44;
        }
        .fast-guidance-badge.efficiency {
            background: #4263eb;
        }
        .fast-guidance-badge.start {
            background: #64748b;
        }
        .fast-guidance-item.secondary .fast-guidance-badge.fail {
            background: #e03131;
        }
        .fast-guidance-item.secondary .fast-guidance-badge.warn {
            background: #f08c00;
        }
        .fast-guidance-item.secondary .fast-guidance-badge.pass {
            background: #2f9e44;
        }
        .fast-guidance-item.secondary .fast-guidance-badge.efficiency {
            background: #4263eb;
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
