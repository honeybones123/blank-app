"""Deflection input-display section ownership."""

from __future__ import annotations

from deflection_support import deflection_has_service_load_for_calc


def bind_runtime(namespace: dict) -> None:
    globals().update(
        {
            key: value
            for key, value in namespace.items()
            if not key.startswith("__")
        }
    )


def _seed_from_param(name: str, fallback: float) -> float:
    try:
        value = get_param(name)
    except TypeError:
        value = None
    try:
        if value is None:
            return float(fallback)
        value = float(value)
        return float(fallback) if math.isnan(value) else value
    except Exception:
        return float(fallback)


def _render_readonly_value(
    label: str,
    value,
    unit: str,
    help_text: str | None = None,
):
    col1, col2 = st.columns([1, 2])
    with col1:
        label_with_hover(label, help_text)
    with col2:
        if value is None:
            display_value = "—"
            color_style = "color: #999;"
        else:
            if isinstance(value, float):
                if unit in ("mm", "mm²"):
                    display_value = f"{value:.0f} {unit}"
                elif unit == "MPa":
                    display_value = f"{value:.2f} {unit}"
                else:
                    display_value = f"{value:.1f} {unit}"
            else:
                display_value = f"{value} {unit}" if unit else str(value)
            color_style = ""
        st.markdown(
            f"""
<div class="readonly-param" style="padding: 0.5rem 0.75rem; margin: 0;">
  <div class="readonly-param-value" style="font-size: 1rem; margin: 0; {color_style}">{display_value}</div>
</div>
""",
            unsafe_allow_html=True,
        )
