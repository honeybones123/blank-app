"""Contracts for Inputs-page calculation/explainer view models.

This module documents existing display behavior only. It must not contain
engineering formulas, solver logic, Streamlit rendering, or Design Guide policy.
"""

CALCULATION_EXPLAINER_CARD_ORDER: tuple[str, ...] = (
    "bending",
    "shear",
    "crack",
    "deflection",
)

CALCULATION_EXPLAINER_CARD_TITLES: dict[str, str] = {
    "bending": "Bending — ULS",
    "shear": "Shear — ULS",
    "crack": "Crack control — SLS",
    "deflection": "Deflection — SLS",
}

CALCULATION_EXPLAINER_ROUTE_PAGES: dict[str, str] = {
    "bending": "bending",
    "shear": "shear",
    "crack": "crack",
    "deflection": "deflection",
}

CALCULATION_EXPLAINER_ROW_FIELDS: tuple[str, ...] = (
    "uid",
    "title",
    "calculated",
    "value",
    "capacity",
    "requirement",
    "limit",
    "action",
    "util",
    "status",
    "route_page",
    "tab",
    "is_informational",
)

DISPLAY_HASH_FIELDS: tuple[str, ...] = (
    "check_id",
    "title",
    "status",
    "route_page",
    "rows",
)

OWNERSHIP_RULES: tuple[str, ...] = (
    "consume_authoritative_rows_only",
    "do_not_recalculate_engineering_truth",
    "do_not_import_streamlit",
    "do_not_render_html",
    "do_not_route_apply",
    "preserve_existing_visible_row_text",
)
