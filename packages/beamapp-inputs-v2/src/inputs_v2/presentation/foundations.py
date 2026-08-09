from inputs_v2.presentation.tokens import TOKENS


def scoped_css() -> str:
    return f"""
    <style>
      html, body, .stApp {{ font-size: 14px; }}
      .stApp {{ background: {TOKENS['page_bg']}; }}
      /* Extracted from the Runtime app shell; kept under the V2 presentation root.
         Runtime reference measurements retained here for contract traceability:
         max-width: 1180px; padding-top: 2rem. */
      .stApp [data-testid="stAppViewContainer"] .main .block-container {{
        max-width: 1180px !important; padding-top: 3.7rem !important;
        padding-right: 2.25rem !important; padding-left: 2.25rem !important;
        padding-bottom: 2rem !important;
      }}
      .stApp h1 {{ font-size: 1.75rem !important; line-height: 1.15 !important; }}
      .stApp h2, .stApp .stMarkdown h2 {{ font-size: 1.45rem !important; }}
      .stApp h3, .stApp .stMarkdown h3 {{ font-size: 1.1rem !important; }}
      .stApp input[type=number]::-webkit-inner-spin-button,
      .stApp input[type=number]::-webkit-outer-spin-button {{
        -webkit-appearance: none !important; margin: 0 !important;
      }}
      .stApp input[type=number] {{ -moz-appearance: textfield !important; }}
      .stApp div[data-testid="stNumberInput"] button {{ display: none !important; }}
      .stApp div[data-testid="stNumberInput"] input[type=number] {{
        padding-top: 2px !important; padding-bottom: 2px !important;
        height: 2rem !important; font-size: .9rem !important;
      }}
      /* The first horizontal block is the page header; V1 uses filled coral
         actions there while the rest of the page uses neutral controls. */
      .stApp [data-testid="stHorizontalBlock"]:first-of-type button {{
        background: #ff4b4b !important; color: #ffffff !important;
        border-color: #ff4b4b !important; font-weight: 600 !important;
      }}
      /* V1's landing actions are neutral outlined controls; only the shell
         Save/PDF actions use the filled coral treatment above. */
      .stApp div.st-key-inputs-v2-landing-actions [data-testid="stHorizontalBlock"] button,
      .stApp div.st-key-inputs-v2-landing-actions button,
      .stApp [class*="st-key-inputs-v2-landing-actions"] button {{
        background: #ffffff !important; color: #334155 !important;
        border: 1px solid #d1d5db !important; font-weight: 400 !important;
      }}
      .stApp div[data-testid="stNumberInput"],
      .stApp div[data-testid="stTextInput"],
      .stApp div[data-testid="stSelectbox"] {{
        max-width: 240px !important; width: auto !important;
      }}
      .stApp div[data-testid="stNumberInput"] input,
      .stApp div[data-testid="stTextInput"] input {{ width: 100% !important; }}
      .inputs-v2-root {{ color: {TOKENS['text']}; }}
      .inputs-v2-root .inputs-v2-kicker {{
        color: {TOKENS['accent']}; font-size: .78rem; font-weight: 700;
        letter-spacing: .08em; text-transform: uppercase; margin-bottom: .25rem;
      }}
      .inputs-v2-root .inputs-v2-subtitle {{ color: {TOKENS['muted']}; margin-top: -.6rem; }}
      .inputs-v2-root.inputs-v2-nav {{
        display: flex; gap: 1.15rem; align-items: flex-end; width: fit-content;
        color: {TOKENS['text']}; font-size: .82rem; border-bottom: 1px solid {TOKENS['border']};
        margin: .9rem 0 4.6rem; padding-bottom: .7rem;
      }}
      .inputs-v2-root.inputs-v2-nav span {{ white-space: nowrap; }}
      .inputs-v2-root.inputs-v2-nav .inputs-v2-nav-active {{
        border-bottom: 2px solid #ff4b4b; padding-bottom: .72rem; margin-bottom: -.72rem;
      }}
      .inputs-v2-root .inputs-v2-card-label {{
        color: {TOKENS['text']}; font-size: 1.05rem; font-weight: 700;
        border-bottom: 1px solid {TOKENS['border']}; padding-bottom: .55rem;
        margin: .25rem 0 .85rem;
      }}
      .inputs-v2-root .inputs-v2-section-info {{
        float: right; color: #2878c8; font-size: .72rem; font-weight: 500;
      }}
      .inputs-v2-root.inputs-v2-check-stack {{ display: grid; gap: .55rem; margin: .2rem 0 1rem; }}
      .inputs-v2-root .inputs-v2-check-card {{ position: relative; overflow: hidden; border: 1px solid rgba(49,51,63,.12); border-radius: 8px; background: rgba(66,99,235,.08); box-shadow: 0 10px 30px rgba(15,23,42,.04); }}
      .inputs-v2-root .inputs-v2-check-card::before {{ content: ""; position: absolute; inset: 0 auto 0 0; width: 6px; background: #4263eb; }}
      .inputs-v2-root .inputs-v2-check-card.status-pass {{ background: rgba(47,158,68,.08); }}
      .inputs-v2-root .inputs-v2-check-card.status-pass::before {{ background: #2f9e44; }}
      .inputs-v2-root .inputs-v2-check-main {{ display: grid; grid-template-columns: 56px minmax(230px,1.45fr) repeat(3,minmax(140px,.7fr)) 96px 24px; gap: .95rem; align-items: center; min-height: 92px; padding: .9rem 1.1rem .9rem 1.45rem; cursor:pointer; list-style:none; position:relative; z-index:1; }}
      .inputs-v2-root .inputs-v2-check-main::-webkit-details-marker {{ display:none; }}
      .inputs-v2-root .inputs-v2-check-main::marker {{ content:""; }}
      .inputs-v2-root .inputs-v2-check-icon {{ width: 56px; height: 56px; display: grid; place-items: center; border-radius: 8px; background: rgba(255,255,255,.6); border: 1px solid #b8c8ff; color: #4263eb; font-weight: 800; }}
      .inputs-v2-root .inputs-v2-check-card.status-pass .inputs-v2-check-icon {{ color: #2f9e44; border-color: #b8e0c1; }}
      .inputs-v2-root .inputs-v2-check-title {{ color: #0f172a; font-size: 1.05rem; font-weight: 800; }}
      .inputs-v2-root .inputs-v2-check-metric {{ border-left: 1px solid rgba(148,163,184,.32); padding-left: .95rem; min-width: 0; }}
      .inputs-v2-root .inputs-v2-check-metric small {{ display: block; color: #64748b; font-size: .72rem; margin-bottom: .3rem; }}
      .inputs-v2-root .inputs-v2-check-metric b {{ color: #0f172a; font-size: .9rem; }}
      .inputs-v2-root .inputs-v2-check-status {{ display: grid; place-items: center; min-width: 82px; padding: .52rem .7rem; border-radius: 999px; background: #4263eb; color: white; font-weight: 800; font-size: .76rem; }}
      .inputs-v2-root .inputs-v2-check-card.status-pass .inputs-v2-check-status {{ background: #2f9e44; }}
      .inputs-v2-root .inputs-v2-check-card.status-fail {{ background: rgba(224,49,49,.08); }}
      .inputs-v2-root .inputs-v2-check-card.status-fail::before {{ background: #e03131; }}
      .inputs-v2-root .inputs-v2-check-details {{ margin:0; }}
      .inputs-v2-root .inputs-v2-check-table-wrap {{ margin:0 1.1rem 1rem; }}
      .inputs-v2-root .inputs-v2-check-details table {{ width:100%; border-collapse:collapse; background:#fff; }}
      .inputs-v2-root .inputs-v2-check-details th, .inputs-v2-root .inputs-v2-check-details td {{ padding:.55rem .7rem; border:1px solid #e5e7eb; text-align:left; font-size:.82rem; }}
      .inputs-v2-root .inputs-v2-check-details .check-row-pass {{ background:#edf8ef; }}
      .inputs-v2-root .inputs-v2-check-details .check-row-fail {{ background:#fff0f0; }}
      .inputs-v2-root .inputs-v2-check-details .check-row-info {{ background:#eef3ff; }}
      .inputs-v2-root .inputs-v2-check-chevron {{ color: #0f172a; text-align: center; transition:transform .12s ease; }}
      .inputs-v2-root .inputs-v2-check-details[open] .inputs-v2-check-chevron {{ transform:rotate(180deg); }}
      @media (max-width: 960px) {{ .inputs-v2-check-main {{ grid-template-columns: 46px 1fr 24px; }} .inputs-v2-check-metric, .inputs-v2-check-status {{ grid-column: 2 / 3; border-left: 0; padding-left: 0; }} .inputs-v2-check-chevron {{ grid-column: 3; grid-row: 1; }} }}
      .inputs-v2-root.inputs-v2-summary-wrap {{
        margin: .35rem 0 1rem; border: 1px solid #dce3ec; border-radius: 10px;
        background: #ffffff; overflow: hidden;
      }}
      .inputs-v2-root .inputs-v2-summary-title {{
        padding: .65rem .85rem; font-weight: 700; color: {TOKENS['text']};
        border-bottom: 1px solid #dce3ec; font-size: .9rem;
      }}
      .inputs-v2-root .inputs-v2-summary {{ width: 100%; border-collapse: collapse; font-size: .78rem; }}
      .inputs-v2-root .inputs-v2-summary th, .inputs-v2-root .inputs-v2-summary td {{ text-align: left; padding: .42rem .85rem; border-bottom: 1px solid #edf1f5; }}
      .inputs-v2-root .inputs-v2-summary th {{ color: #64748b; font-weight: 600; background: #f8fafc; }}
      .inputs-v2-root .inputs-v2-summary tr:last-child td {{ border-bottom: 0; }}
      .inputs-v2-root.inputs-v2-row-label {{
        font-size: .78rem; color: {TOKENS['text']}; padding-top: .55rem;
        line-height: 1.2;
      }}
      .inputs-v2-root.inputs-v2-section-divider {{
        border-top: 1px solid {TOKENS['border']}; margin: 1.15rem 0 1.35rem;
      }}
      .inputs-v2-root .inputs-v2-diagnostic {{
        color: {TOKENS['muted']}; font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        font-size: .76rem;
      }}
      .inputs-v2-root .inputs-v2-landing {{
        background: #f4f7fa; border: 1px solid rgba(148,163,184,.28);
        border-radius: 14px; padding: 1.25rem 1.1rem; margin: 1rem 0 1.25rem; color: #475569;
      }}
      .inputs-v2-root .inputs-v2-landing-title {{ font-weight: 800; font-size: .9rem; color: #334155; margin-bottom: .7rem; }}
      .inputs-v2-root .inputs-v2-landing-label {{ margin-top: .8rem; font-weight: 600; }}
      .inputs-v2-root .inputs-v2-batch-status {{
        display: flex; align-items: center; gap: .65rem; flex-wrap: wrap;
        border: 1px solid #dce3ec; border-radius: 14px; padding: .65rem 1rem;
        margin: .9rem 0 2.5rem; color: #334155; box-shadow: 0 5px 14px rgba(15,23,42,.05);
        font-size: .78rem;
      }}
      .inputs-v2-root .inputs-v2-batch-status span {{ padding: .22rem .55rem; border: 1px solid #dce3ec; border-radius: 999px; }}
      .inputs-v2-root.inputs-v2-guide-card {{
        display: flex; align-items: center; gap: .45rem; flex-wrap: wrap;
        border: 1px solid #c7e4ce; border-left: 6px solid #2f9e44;
        border-radius: 8px; background: #eef9f0; padding: .7rem .9rem;
        margin: .75rem 0 2rem; color: #334155; font-size: .78rem;
      }}
      .inputs-v2-root .inputs-v2-guide-pass {{ background: #2f9e44; color: #fff; border-radius: 999px; padding: .2rem .55rem; font-weight: 700; }}
      .inputs-v2-root .inputs-v2-guide-preview {{ margin-left: auto; border: 1px solid #b8e0c1; border-radius: 999px; padding: .25rem .65rem; color: #166534; background: #e3f5e6; }}
      .inputs-v2-root .inputs-v2-guide-chevron {{ color: #64748b; font-size: 1.1rem; }}
      .inputs-v2-root .inputs-v2-design-guide-item {{ border-top: 1px solid rgba(49,51,63,.08); border-left: 4px solid #2563eb; border-radius: 10px; padding: .92rem .95rem; margin: .7rem 0; line-height: 1.42; background: rgba(37,99,235,.08); }}
      .inputs-v2-root .inputs-v2-design-guide-item.pass {{ background: rgba(47,158,68,.08); border-left-color: #2f9e44; }}
      .inputs-v2-root .inputs-v2-design-guide-item.warn {{ background: rgba(240,140,0,.08); border-left-color: #f08c00; }}
      .inputs-v2-root .inputs-v2-design-guide-item.fail {{ background: rgba(224,49,49,.08); border-left-color: #e03131; }}
      .inputs-v2-root .inputs-v2-design-guide-item.optimise {{ background: rgba(37,99,235,.08); border-left-color: #2563eb; }}
      .inputs-v2-root .inputs-v2-design-guide-item.info {{ background: rgba(100,116,139,.08); border-left-color: #64748b; }}
      .inputs-v2-root .inputs-v2-design-guide-head {{ display:flex; align-items:center; gap:.5rem; margin-bottom:.32rem; }}
      .inputs-v2-root .inputs-v2-design-guide-badge {{ font-size:.68rem; font-weight:800; text-transform:uppercase; letter-spacing:.06em; padding:.18rem .48rem; border-radius:999px; color:#fff; background:#2563eb; }}
      .inputs-v2-root .inputs-v2-design-guide-badge.pass {{ background:#2f9e44; }}
      .inputs-v2-root .inputs-v2-design-guide-badge.warn {{ background:#f08c00; }}
      .inputs-v2-root .inputs-v2-design-guide-badge.fail {{ background:#e03131; }}
      .inputs-v2-root .inputs-v2-design-guide-badge.optimise {{ background:#2563eb; }}
      .inputs-v2-root .inputs-v2-design-guide-badge.info {{ background:#64748b; }}
      .inputs-v2-root .inputs-v2-design-guide-title {{ font-weight:800; color:#0f172a; }}
      .inputs-v2-root .inputs-v2-design-guide-meta {{ color:#64748b; font-size:.82rem; margin-top:.28rem; }}
      .inputs-v2-root .inputs-v2-design-guide-apply {{ margin-top:.65rem; }}
      .inputs-v2-root .inputs-v2-design-guide-cta-gap {{ height: .8rem; }}
      /* Design Brain uses a native expander so the whole shell is clickable.
         Keep its closed state aligned with the Runtime card geometry instead
         of Streamlit's default plain disclosure row. */
      div[data-testid="stExpander"] {{ border: 1px solid #cbd5e1; border-radius: 10px; overflow: hidden; background: #f8fafc; margin: .7rem 0; }}
      div[data-testid="stExpander"] summary {{ min-height: 56px; padding: .85rem 1rem; font-weight: 700; color: #0f172a; }}
      div[data-testid="stExpander"] summary svg {{ display:none; }}
      div[data-testid="stExpander"] summary::before {{ content:"🧠"; display:inline-block; margin-right:.65rem; font-size:1.25rem; vertical-align:middle; }}
      div[data-testid="stExpander"] summary:hover {{ background: #eef3ff; }}
      div[data-testid="stExpander"] > div[role="region"] {{ padding: 0 .7rem .7rem; }}
      .inputs-v2-root.inputs-v2-design-guide-copy {{ border:0 !important; background:transparent !important; padding:.35rem .2rem .15rem !important; margin:0 !important; border-radius:0 !important; line-height:1.42; }}
      .inputs-v2-brain-state-fail, .inputs-v2-brain-state-pass, .inputs-v2-brain-state-optimise, .inputs-v2-brain-state-info, .inputs-v2-brain-state-warn, .inputs-v2-brain-state-empty {{ display:none !important; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-brain-state-empty) div[data-testid="stExpander"] {{ background:#ffffff; border-color:#adb5bd; border-left:5px solid #868e96; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-brain-state-empty) div[data-testid="stExpander"] summary:hover {{ background:#f8f9fa; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-brain-state-fail) div[data-testid="stExpander"] {{ background:#fff0f0; border-color:#e03131; border-left:5px solid #e03131; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-brain-state-fail) div[data-testid="stExpander"] summary:hover {{ background:#ffe3e3; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-brain-state-optimise) div[data-testid="stExpander"] {{ background:#eef3ff; border-color:#4263eb; border-left:5px solid #4263eb; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-brain-state-optimise) div[data-testid="stExpander"] summary:hover {{ background:#dbe4ff; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-brain-state-pass) div[data-testid="stExpander"] {{ background:#edf8ef; border-color:#2f9e44; border-left:5px solid #2f9e44; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-brain-state-pass) div[data-testid="stExpander"] summary:hover {{ background:#dff3e3; }}
      /* The Design Guide CTA belongs to the same bordered card and spans it. */
      div[data-testid="stButton"] > button {{ width:100%; border-radius:8px; }}
      div[data-testid="stButton"] > button:not(:disabled) {{ background:#4263eb; color:#fff; border-color:#4263eb; }}
      div[data-testid="stButton"] > button:disabled {{ background:#f1f3f5; color:#868e96; border-color:#ced4da; }}
      /* Mirror the Design Guide state on its CTA. */
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-design-guide-copy.fail) div[data-testid="stButton"] > button:not(:disabled) {{ background:#e03131; border-color:#e03131; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-design-guide-copy.pass) div[data-testid="stButton"] > button:not(:disabled) {{ background:#2f9e44; border-color:#2f9e44; }}
      div[data-testid="stVerticalBlock"]:has(.inputs-v2-design-guide-copy.optimise) div[data-testid="stButton"] > button:not(:disabled) {{ background:#4263eb; border-color:#4263eb; }}
    </style>
    """
