"""
PDF Report Integration for Streamlit Beam Design App

This module provides the render_pdf_button() function that integrates
with the app's session state to generate professional PDF reports.
"""

import streamlit as st
import tempfile
import os
from pathlib import Path

from reporting.report_content import (
    extract_summary_rows,
    extract_inputs_sections,
    extract_check_sections,
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


def render_pdf_button():
    """
    Render a PDF export button in the Design Actions section.
    
    This function:
    - Reads from session state (read-only)
    - Checks if results are available
    - Generates PDF report
    - Shows download button
    - Cleans up temp files
    """
    # Generate PDF button
    if st.button("📄 Generate PDF Report", type="primary"):
        # 1) Run all checks FIRST (and show spinner so user knows it's working)
        with st.spinner("Running all checks..."):
            try:
                from design_runner import run_all_design_checks
                run_all_design_checks(force=True)
            except Exception as run_err:
                st.error(f"Could not run all checks before export: {run_err}")
                return
        
        # 2) HARD VERIFY reports exist (otherwise the PDF will be empty anyway)
        results = st.session_state.get("results", {})
        
        # Check for implemented reports (only bending is fully implemented with report tree)
        required_reports = ["bending_report"]
        missing = [k for k in required_reports if not results.get(k)]
        
        if missing:
            st.error(
                "PDF export blocked: reports were not generated for: "
                + ", ".join(missing)
                + ".\n\nThis means the runner did not publish *_report into results."
            )
            st.write("DEBUG: available *_report keys:", [k for k in results.keys() if k.endswith("_report")])
            st.write("DEBUG: available *_steps keys (legacy):", [k for k in results.keys() if k.endswith("_steps")])
            return
        
        # Warn if other modules haven't been migrated yet (but don't block)
        optional_reports = ["shear_report", "crack_report", "deflection_report"]
        missing_optional = [k for k in optional_reports if not results.get(k)]
        if missing_optional:
            # Check if legacy steps exist as fallback
            legacy_fallback = {}
            for report_key in missing_optional:
                module_name = report_key.replace("_report", "")
                steps_key = f"{module_name}_steps"
                if results.get(steps_key):
                    legacy_fallback[report_key] = steps_key
            
            if legacy_fallback:
                st.info(
                    f"Note: {', '.join(legacy_fallback.keys())} not yet migrated to report tree format. "
                    f"Using legacy {', '.join(legacy_fallback.values())} format for PDF."
                )
        
        # 3) Export diagrams and attach to report structure
        try:
            from reporting.fig_export import export_box_diagram_png
            export_report_diagrams(results)
        except Exception as export_err:
            st.warning(f"Could not export diagrams: {export_err}. PDF will be generated without diagrams.")
        
        # 4) Now build the PDF
        with st.spinner("Generating PDF report..."):
            try:
                # Check if reportlab is available and import build_pdf_report
                try:
                    from reporting.report_builder import build_pdf_report
                except ImportError as import_err:
                    st.error(
                        "PDF generation requires reportlab. Please install it with: "
                        "`pip install reportlab`"
                    )
                    st.code("pip install reportlab", language="bash")
                    return
                
                # Extract report content from session state
                summary_rows = extract_summary_rows()
                inputs_sections = extract_inputs_sections()
                
                # Prepare figure paths dict (currently empty, can be populated with exported figures)
                fig_paths = {
                    "bending": [],
                    "shear": [],
                    "crack": [],
                    "deflection": [],
                    "section": None,
                }
                
                # Extract check sections with figure paths
                check_sections = extract_check_sections(fig_paths=fig_paths)
                
                # Build PDF
                temp_figures = []  # List to track temp figure files
                
                # Collect all figure paths for cleanup
                for check in check_sections:
                    figs = check.get("figures", [])
                    if isinstance(figs, list):
                        temp_figures.extend([f for f in figs if f])
                    elif figs:
                        temp_figures.append(figs)
                
                pdf_bytes = build_pdf_report(
                    summary_rows=summary_rows,
                    inputs_sections=inputs_sections,
                    check_sections=check_sections,
                    temp_figures=temp_figures,
                )
                
                # Show download button
                st.download_button(
                    label="📥 Download PDF Report",
                    data=pdf_bytes,
                    file_name="beam_design_report.pdf",
                    mime="application/pdf",
                )
                
                st.success("PDF report generated successfully!")
                
            except ImportError as e:
                st.error(f"Missing dependency: {str(e)}")
                st.info("Please install reportlab: `pip install reportlab`")
            except Exception as e:
                st.error(f"Error generating PDF: {str(e)}")
                st.exception(e)
            finally:
                # Cleanup temp figure files
                for fig_path in temp_figures:
                    try:
                        if os.path.exists(fig_path):
                            os.remove(fig_path)
                    except Exception:
                        pass  # Ignore cleanup errors

