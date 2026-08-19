# UI presentation ownership contract

The rendered application is a locked product contract. Architecture changes
must preserve visible content, dimensions, ordering, interaction behaviour and
engineering publications unless a separate product change explicitly approves
the difference.

## Rendering owners

| Concern | Sole owner | Consumers may provide |
| --- | --- | --- |
| Application title and navigation | `app.py` shared shell | Active page identity |
| Result-page title fallback | `widgets_helpers.render_result_page_title` | Title text |
| Major section title | `widgets_helpers.render_section_title` | Section text |
| Major section divider | `widgets_helpers.page_divider` | Placement only |
| Calculation-card shell and state colour | Canonical helpers in `widgets_helpers.py` | Title, status and calculation content |
| Shared geometry tokens | `ui.design_tokens` | Nothing; values are presentation authority |
| Engineering values | Authoritative calculation/publication layer | Structured immutable result data |
| Page composition | Individual page runtime | Section ordering and authoritative data binding |

## Non-negotiable boundaries

- The shared shell is the only normal owner of the active page heading.
- Page modules must not impose application-shell width rules.
- Calculation modules must not change global CSS or page geometry.
- Presentation code must not recompute, correct or reinterpret engineering values.
- Widget keys and publication ownership are engineering state contracts, not styling details.
- Native/stable tabs are browser presentation state only and must not trigger a
  server rerun merely to change the visible panel.
- Generated Streamlit class names are not stable selectors. New presentation
  hooks must use deliberate `sb-*`, `app-*` or `data-sb-*` markers.

## Refactor verification gate

Each incremental refactor must pass:

1. Existing numerical and publication regression tests.
2. Architecture ownership tests.
3. Desktop and narrow-layout geometry checks for page width, headings, section
   gaps and card dimensions.
4. Collapsed/open, loading and rerender interaction checks.
5. A cold-page benchmark comparison when mounted components or chart payloads
   change.

A performance optimization fails the gate if it changes engineering output or
visible UI, even when it makes the page faster.
