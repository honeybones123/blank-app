"""Import stage UI."""

from __future__ import annotations


def render_import_panel(st):
    return st.file_uploader(
        "SPACEGASS Excel or CSV",
        type=["xlsx", "xls", "csv"],
        key="batch_design_spacegass_upload",
        help="Imports final member design actions only; analysis model data is not imported.",
    )
