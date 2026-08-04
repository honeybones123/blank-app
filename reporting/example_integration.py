"""
PDF Report Integration for Streamlit Beam Design App

This module provides the render_pdf_button() function that integrates
with the app's session state to generate professional PDF reports.
"""

import streamlit as st
import os

from report_helpers import (
    build_active_beam_report_data_from_state,
    build_active_beam_report_pdf,
)
# Note: build_pdf_report is imported lazily inside render_pdf_button() to avoid import errors


def export_report_diagrams(results: dict):
    """
    Export diagrams for all boxes in report structure and attach them to boxes.
    
    Uses the module registry to iterate through all modules and their groups/tabs/boxes.
    Supports both unified format (groups) and legacy format (tabs).
    
    Args:
        results: Results dict from st.session_state["results"]
    """
    from reporting.fig_export import export_box_diagram_png
    
    # Try to use module registry (unified format)
    try:
        from reporting.module_registry import get_all_module_schemas
        module_schemas = get_all_module_schemas()
        
        for schema in module_schemas:
            module_id = schema.get("module_id")
            groups = schema.get("groups", [])
            
            # Iterate through groups (ULS/SLS/Min)
            for group in groups:
                group_tabs = group.get("tabs", [])
                
                # Iterate through tabs in this group
                for tab in group_tabs:
                    boxes = tab.get("boxes", [])
                    
                    # Iterate through boxes
                    for box_idx, box in enumerate(boxes):
                        if not isinstance(box, dict):
                            continue
                        
                        # Check if box has a diagram callable
                        diagram = box.get("diagram")
                        if callable(diagram):
                            # Create unique key: sanitize box id
                            box_id = box.get("id", f"box_{box_idx}")
                            group_id = group.get("group_id", "unknown")
                            tab_id = tab.get("tab_id", f"tab_{box_idx}")
                            
                            # Sanitize for filename
                            sanitized_box_id = str(box_id).replace(".", "_").replace(" ", "_")
                            sanitized_group = str(group_id).replace(" ", "_").lower()
                            sanitized_tab = str(tab_id).replace(" ", "_").lower()
                            
                            # Create unique key per box
                            unique_key = f"{module_id}_{sanitized_group}_{sanitized_tab}_{sanitized_box_id}"
                            
                            # Special handling for boxes 1.1 and 3.2 - make them 20% bigger and add extra right margin
                            # Box 1.1: Stress-block parameters (ULS)
                            # Box 3.2: Neutral axis depth (SLS)
                            is_special_box = (box_id == "1.1" or box_id == "3.2")
                            
                            if is_special_box:
                                # 20% bigger: 67mm * 1.2 = ~80mm
                                w_mm = 80.0
                                h_mm = 33.6  # Also increase height proportionally (28 * 1.2)
                            else:
                                # Default sizes
                                w_mm = 67.0  # Updated default (was 55.0)
                                h_mm = 28.0
                            
                            # Export the diagram with size constraints
                            diagram_dict = export_box_diagram_png(
                                fig_or_callable=diagram,
                                key=unique_key,
                                caption="",  # Can be customized per box if needed
                                w_mm=w_mm,
                                h_mm=h_mm,
                            )
                            
                            # Replace callable with exported dict (create new dict to avoid sharing)
                            if diagram_dict:
                                box["diagram"] = {
                                    "path": diagram_dict["path"],
                                    "caption": diagram_dict.get("caption", ""),
                                    "w_mm": diagram_dict.get("w_mm", w_mm),
                                    "h_mm": diagram_dict.get("h_mm", h_mm),
                                    # Add flag for special boxes to apply extra right margin
                                    "extra_right_margin": is_special_box,
                                }
                            else:
                                box["diagram"] = None  # Remove callable if export failed
        return  # Successfully used module registry
    except ImportError:
        pass  # Fall through to legacy format
    
    # Fallback: Legacy format (direct report keys)
    report_keys = ["bending_report", "shear_report", "crack_report", "deflection_report"]
    
    for report_key in report_keys:
        report = results.get(report_key)
        if not isinstance(report, dict):
            continue
        
        tabs = report.get("tabs", [])
        if not isinstance(tabs, list):
            continue
        
        for tab_idx, tab in enumerate(tabs):
            boxes = tab.get("boxes", [])
            if not isinstance(boxes, list):
                continue
            
            for box_idx, box in enumerate(boxes):
                if not isinstance(box, dict):
                    continue
                
                # Check if box has a diagram callable
                diagram = box.get("diagram")
                if callable(diagram):
                    # Create unique key: sanitize box id and include tab index
                    box_id = box.get("id", f"box_{box_idx}")
                    tab_title = tab.get("tab_title", f"tab_{tab_idx}")
                    # Sanitize for filename
                    sanitized_box_id = str(box_id).replace(".", "_").replace(" ", "_")
                    sanitized_tab = str(tab_title).replace(" ", "_").lower()
                    
                    # Create unique key per box
                    unique_key = f"{report_key}_{sanitized_tab}_{sanitized_box_id}"
                    
                    # Special handling for boxes 1.1 and 3.2 - make them 20% bigger and add extra right margin
                    # Box 1.1: Stress-block parameters (ULS)
                    # Box 3.2: Neutral axis depth (SLS)
                    is_special_box = (box_id == "1.1" or box_id == "3.2")
                    
                    if is_special_box:
                        # 20% bigger: 67mm * 1.2 = ~80mm
                        w_mm = 80.0
                        h_mm = 33.6  # Also increase height proportionally (28 * 1.2)
                    else:
                        # Default sizes
                        w_mm = 67.0  # Updated default (was 55.0)
                        h_mm = 28.0
                    
                    # Export the diagram with size constraints
                    diagram_dict = export_box_diagram_png(
                        fig_or_callable=diagram,
                        key=unique_key,
                        caption="",  # Can be customized per box if needed
                        w_mm=w_mm,
                        h_mm=h_mm,
                    )
                    
                    # Replace callable with exported dict (create new dict to avoid sharing)
                    if diagram_dict:
                        box["diagram"] = {
                            "path": diagram_dict["path"],
                            "caption": diagram_dict.get("caption", ""),
                            "w_mm": diagram_dict.get("w_mm", w_mm),
                            "h_mm": diagram_dict.get("h_mm", h_mm),
                            # Add flag for special boxes to apply extra right margin
                            "extra_right_margin": is_special_box,
                        }
                    else:
                        box["diagram"] = None  # Remove callable if export failed


def _get_results():
    """
    Read-only function to discover results from session state.
    
    Tries common result keys without modifying session state.
    Returns empty dict if no results found.
    """
    # Try common result dictionary keys
    result_keys = [
        "results",
        "beam_results",
        "design_results",
    ]
    
    for key in result_keys:
        if key in st.session_state:
            results = st.session_state.get(key)
            if isinstance(results, dict):
                return results
    
    # If no results dict found, return empty dict
    # The report will use get_param() directly from session state
    return {}


def render_pdf_button(
    button_type: str = "primary",
    detail_level: str = "standard",
    *,
    section_figure_factory=None,
    beam_figure_factory=None,
):
    """
    Render a PDF export button in the Design Actions section.
    
    This function:
    - Reads from session state (read-only)
    - Checks if results are available
    - Generates PDF report
    - Shows download button
    - Cleans up temp files
    """
    detail_level_key = "detailed" if str(detail_level).strip().lower() == "detailed" else "standard"

    # PDF export button
    if st.button("📄 PDF Report", type=button_type, use_container_width=True):
        # Flush proxy widget keys (e.g. inputs_*) into shared keys before running checks / exporting
        try:
            from state_and_helpers import save_proxies_to_active_set, recalc_derived_values, update_results
            save_proxies_to_active_set()
            recalc_derived_values()
            update_results()
        except Exception:
            # Don't block PDF if one helper isn't available; checks will still run
            pass

        # 1) Run all checks FIRST (and show spinner so user knows it's working)
        with st.spinner("Running all checks..."):
            try:
                from design_runner import run_all_design_checks
                run_all_design_checks(force=True)
            except Exception as run_err:
                st.error(f"Could not run all checks before export: {run_err}")
                return
        
        # 2) Build the new active-beam report PDF directly from the Stage 5 report structure.
        with st.spinner("Generating PDF report..."):
            try:
                report_data = build_active_beam_report_data_from_state(report_mode=detail_level_key)
                pdf_bytes = build_active_beam_report_pdf(
                    report_data,
                    section_figure_factory=section_figure_factory,
                    beam_figure_factory=beam_figure_factory,
                )
                suffix = "STANDARD" if detail_level_key == "standard" else "DETAILED"
                beam_name = str((report_data.get("beam_info") or {}).get("display_name") or "Beam").replace(" ", "_")
                revision = str((report_data.get("metadata") or {}).get("revision_label") or "Rev_1").replace(" ", "_")
                filename = f"{beam_name}_Beam_Design_Report_{suffix}_{revision}.pdf"
                
                # Show download button
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                )
                
                st.success("PDF report generated successfully!")
                
            except ImportError as e:
                st.error(f"Missing dependency: {str(e)}")
                st.info("Please install reportlab: `pip install reportlab`")
            except Exception as e:
                st.error(f"Error generating PDF: {str(e)}")
                st.exception(e)
