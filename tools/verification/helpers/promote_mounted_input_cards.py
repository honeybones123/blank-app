from __future__ import annotations

from pathlib import Path

# Promotion helper: re-triggered 2026-08-18 after prototype verification.
PATH = Path("engineering_page_sections/compact_check_inputs/renderer.py")
text = PATH.read_text(encoding="utf-8")

old_import = "from .contract import CheckInputPanelConfig\n"
new_import = (
    "from .contract import CheckInputPanelConfig\n"
    "from ..mounted_card_shell import mounted_card_region\n"
)
if new_import not in text:
    if text.count(old_import) != 1:
        raise SystemExit("FAIL: compact input contract import anchor changed")
    text = text.replace(old_import, new_import, 1)

old_block = '''            expander = st_module.expander(
                    label,
                    expanded=False,
                    key=(
                        f"compact_check_inputs_{config.page_slug}_"
                        f"{category.category_id}"
                    ),
                    type="compact",
                    on_change=(
                        "ignore" if config.mount_closed_bodies else "rerun"
                    ),
                )
            regions.append(
                _MountedExpander(expander)
                if config.mount_closed_bodies
                else expander
            )
'''
new_block = '''            card_key = (
                f"compact_check_inputs_{config.page_slug}_"
                f"{category.category_id}"
            )
            if config.mount_closed_bodies:
                regions.append(
                    mounted_card_region(
                        st_module,
                        label=label,
                        key=card_key,
                        initially_open=False,
                    )
                )
                continue

            # Heavy/lazy panels retain Streamlit's expander path so closed
            # bodies are not constructed during cold page rendering.
            regions.append(
                st_module.expander(
                    label,
                    expanded=False,
                    key=card_key,
                    type="compact",
                    on_change="rerun",
                )
            )
'''
if new_block not in text:
    if text.count(old_block) != 1:
        raise SystemExit("FAIL: compact input expander block changed")
    text = text.replace(old_block, new_block, 1)

css_marker = "/* Mounted-card presentation parity. */"
if css_marker not in text:
    insertion = r'''
/* Mounted-card presentation parity. */
[class*="st-key-compact_check_inputs_"][class*="__body"]
  div[data-baseweb="input"],
[class*="st-key-compact_check_inputs_"][class*="__body"]
  div[data-baseweb="base-input"],
[class*="st-key-compact_check_inputs_"][class*="__body"]
  div[data-baseweb="select"] > div,
[class*="st-key-compact_check_inputs_"][class*="__body"]
  div[data-testid="stNumberInput"] > div,
[class*="st-key-compact_check_inputs_"][class*="__body"]
  div[data-testid="stTextInput"] > div,
[class*="st-key-compact_check_inputs_"][class*="__body"] textarea,
[class*="st-key-compact_check_inputs_"][class*="__body"] input {
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
}
[class*="st-key-compact_check_inputs_"][class*="__body"]
  div[data-baseweb="input"] > input,
[class*="st-key-compact_check_inputs_"][class*="__body"]
  div[data-baseweb="base-input"] > input,
[class*="st-key-compact_check_inputs_"][class*="__body"]
  div[data-baseweb="select"] * {
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
}
[class*="st-key-compact_check_inputs_"][class*="__body"]
  > div[data-testid="stVerticalBlock"] {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 1rem;
  row-gap: .45rem;
}
[class*="st-key-compact_check_inputs_"][class*="__body"]
  > div[data-testid="stVerticalBlock"] > :has(.section-title),
[class*="st-key-compact_check_inputs_"][class*="__body"]
  > div[data-testid="stVerticalBlock"] > [class*="st-key-compact_check_inputs_full_span_"] {
  grid-column: 1 / -1;
}
[class*="st-key-compact_check_inputs_"][class*="_design_actions"][class*="__shell"]
  div[data-testid="stButton"] > button::before {
  background-image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMTAyMzRhIiBzdHJva2Utd2lkdGg9IjEuOCIgc3Ryb2tlLWxpbmVjY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTE2IDV2MjFNNSA4aDIyTTQgOWw0IDlIMmwyLTlabTI0IDAgNCA5aC02bDItOVpNNyA4bC0zIDFtMjEtMSAzIDFNMTAgMjdIMTIiLz48L3N2Zz4=");
}
[class*="st-key-compact_check_inputs_"][class*="_section_material"][class*="__shell"]
  div[data-testid="stButton"] > button::before {
  background-image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMTAyMzRhIiBzdHJva2Utd2lkdGg9IjEuOCI+PHJlY3QgeD0iNSIgeT0iNSIgd2lkdGg9IjIyIiBoZWlnaHQ9IjIyIiByeD0iMSIvPjxyZWN0IHg9IjkiIHk9IjkiIHdpZHRoPSIxNCIgaGVpZ2h0PSIxNCIvPjxjaXJjbGUgY3g9IjExIiBjeT0iMTEiIHI9IjEuNCIgZmlsbD0iIzEwMjM0YSIvPjxjaXJjbGUgY3g9IjIxIiBjeT0iMTEiIHI9IjEuNCIgZmlsbD0iIzEwMjM0YSIvPjxjaXJjbGUgY3g9IjExIiBjeT0iMjEiIHI9IjEuNCIgZmlsbD0iIzEwMjM0YSIvPjxjaXJjbGUgY3g9IjIxIiBjeT0iMjEiIHI9IjEuNCIgZmlsbD0iIzEwMjM0YSIvPjwvc3ZnPg==");
}
[class*="st-key-compact_check_inputs_"][class*="_reinforcement"][class*="__shell"]
  div[data-testid="stButton"] > button::before {
  background-image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMTAyMzRhIiBzdHJva2Utd2lkdGg9IjEuNiIgc3Ryb2tlLWxpbmVjY2FwPSJyb3VuZCI+PHBhdGggZD0iTTggNXYyMk0xNiA1djIyTTI0IDV2MjJNNyA4aDIyTTUgMTZoMjJNNSAyNGgyMiIvPjwvc3ZnPg==");
}
:is(
  [class*="st-key-compact_check_inputs_"][class*="_design_actions"][class*="__shell"],
  [class*="st-key-compact_check_inputs_"][class*="_section_material"][class*="__shell"],
  [class*="st-key-compact_check_inputs_"][class*="_reinforcement"][class*="__shell"]
) div[data-testid="stButton"] > button::before {
  content: "";
  flex: 0 0 42px;
  width: 42px;
  height: 42px;
  margin-right: 12px;
  border-radius: 8px;
  background-color: #E3E8ED;
  background-position: center;
  background-repeat: no-repeat;
  background-size: 27px 27px;
}
'''
    anchor = "@media (max-width: 700px) {"
    if text.count(anchor) != 1:
        raise SystemExit("FAIL: compact input mobile CSS anchor changed")
    text = text.replace(anchor, insertion + "\n" + anchor, 1)

mobile_old = '''  [class*="st-key-compact_check_inputs_"] div[data-testid="stExpanderDetails"]
    > div[data-testid="stVerticalBlock"] { grid-template-columns: minmax(0, 1fr); }
'''
mobile_new = mobile_old + '''  [class*="st-key-compact_check_inputs_"][class*="__body"]
    > div[data-testid="stVerticalBlock"] { grid-template-columns: minmax(0, 1fr); }
'''
if mobile_new not in text:
    if text.count(mobile_old) != 1:
        raise SystemExit("FAIL: compact input mobile grid anchor changed")
    text = text.replace(mobile_old, mobile_new, 1)

PATH.write_text(text, encoding="utf-8")
print("PASS: mounted input-card path promoted fail-closed")
