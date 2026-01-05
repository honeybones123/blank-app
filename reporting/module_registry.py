"""
Module Registry - Single source of truth for all design modules

This module defines the registry of all design modules and their report schemas.
Each module must provide:
- ensure_run(): Compute results without UI
- get_schema(): Return unified report schema
"""

import streamlit as st
from typing import Dict, List, Any, Callable, Optional


def ensure_bending_run(session_state: dict, results: dict) -> None:
    """Ensure bending results are computed (ULS + SLS + Min)."""
    try:
        from bending_page import compute_bending_results
        compute_bending_results(publish=True)
    except Exception as e:
        results["bending_error"] = str(e)


def get_bending_schema(session_state: dict, results: dict) -> Optional[Dict[str, Any]]:
    """Get bending report schema."""
    bending_report = results.get("bending_report")
    if not isinstance(bending_report, dict):
        return None
    
    # Convert bending_report format to unified schema
    module_title = bending_report.get("module_title", "Bending (ULS)")
    tabs = bending_report.get("tabs", [])
    
    # Group tabs into ULS/SLS/Min
    groups = []
    
    # Find ULS tab
    uls_tab = next((t for t in tabs if t.get("tab_title") == "ULS Checks"), None)
    if uls_tab:
        groups.append({
            "group_id": "uls",
            "group_title": "ULS Checks",
            "group_subtitle": "Ultimate Limit State",
            "tabs": [uls_tab],
        })
    
    # Find SLS tab
    sls_tab = next((t for t in tabs if t.get("tab_title") == "SLS Checks"), None)
    if sls_tab:
        groups.append({
            "group_id": "sls",
            "group_title": "SLS Checks",
            "group_subtitle": "Serviceability Limit State",
            "tabs": [sls_tab],
        })
    
    # Find Minimum tab
    min_tab = next((t for t in tabs if "Minimum" in t.get("tab_title", "")), None)
    if min_tab:
        groups.append({
            "group_id": "min",
            "group_title": "Minimum Requirements",
            "group_subtitle": "Code minimums and detailing checks",
            "tabs": [min_tab],
        })
    
    if not groups:
        return None
    
    return {
        "module_id": "bending",
        "title": "Bending",
        "standard": "AS 3600:2018",
        "element": "Reinforced Concrete Beam",
        "groups": groups,
        "summary": bending_report.get("summary", []),
    }


def ensure_shear_run(session_state: dict, results: dict) -> None:
    """Ensure shear results are computed."""
    try:
        from shear_page import compute_shear_results
        compute_shear_results(publish=True)
    except Exception as e:
        results["shear_error"] = str(e)


def get_shear_schema(session_state: dict, results: dict) -> Optional[Dict[str, Any]]:
    """Get shear report schema (ULS only typically)."""
    shear_report = results.get("shear_report")
    if isinstance(shear_report, dict) and shear_report.get("tabs"):
        # Convert to unified schema
        tabs = shear_report.get("tabs", [])
        groups = [{
            "group_id": "uls",
            "group_title": "ULS Checks",
            "group_subtitle": "Ultimate Limit State",
            "tabs": tabs,
        }]
        return {
            "module_id": "shear",
            "title": "Shear",
            "standard": "AS 3600:2018",
            "element": "Reinforced Concrete Beam",
            "groups": groups,
            "summary": shear_report.get("summary", []),
        }
    return None


def ensure_crack_run(session_state: dict, results: dict) -> None:
    """Ensure crack control results are computed."""
    try:
        from crack_core import compute_crack_results
        compute_crack_results(publish=True)
    except Exception as e:
        results["crack_error"] = str(e)


def get_crack_schema(session_state: dict, results: dict) -> Optional[Dict[str, Any]]:
    """Get crack control report schema (SLS)."""
    crack_report = results.get("crack_report")
    if isinstance(crack_report, dict) and crack_report.get("tabs"):
        tabs = crack_report.get("tabs", [])
        groups = [{
            "group_id": "sls",
            "group_title": "SLS Checks",
            "group_subtitle": "Serviceability Limit State",
            "tabs": tabs,
        }]
        return {
            "module_id": "crack",
            "title": "Crack Control",
            "standard": "AS 3600:2018",
            "element": "Reinforced Concrete Beam",
            "groups": groups,
            "summary": crack_report.get("summary", []),
        }
    return None


def ensure_deflection_run(session_state: dict, results: dict) -> None:
    """Ensure deflection results are computed."""
    try:
        from deflection_core import compute_deflection_results
        compute_deflection_results(publish=True)
    except Exception:
        pass  # Deflection may not always be available


def get_deflection_schema(session_state: dict, results: dict) -> Optional[Dict[str, Any]]:
    """Get deflection report schema (SLS)."""
    deflection_report = results.get("deflection_report")
    if isinstance(deflection_report, dict) and deflection_report.get("tabs"):
        tabs = deflection_report.get("tabs", [])
        groups = [{
            "group_id": "sls",
            "group_title": "SLS Checks",
            "group_subtitle": "Serviceability Limit State",
            "tabs": tabs,
        }]
        return {
            "module_id": "deflection",
            "title": "Deflection",
            "standard": "AS 3600:2018",
            "element": "Reinforced Concrete Beam",
            "groups": groups,
            "summary": deflection_report.get("summary", []),
        }
    return None


def ensure_creep_run(session_state: dict, results: dict) -> None:
    """Ensure creep results are computed."""
    try:
        from creep import compute_creep_results
        compute_creep_results(publish=True)
    except Exception:
        pass


def get_creep_schema(session_state: dict, results: dict) -> Optional[Dict[str, Any]]:
    """Get creep report schema (SLS/time-dependent)."""
    # TODO: Implement when creep_report is available
    return None


def ensure_shrinkage_run(session_state: dict, results: dict) -> None:
    """Ensure shrinkage results are computed."""
    try:
        from shrinkage import compute_shrinkage_results
        compute_shrinkage_results(publish=True)
    except Exception:
        pass


def get_shrinkage_schema(session_state: dict, results: dict) -> Optional[Dict[str, Any]]:
    """Get shrinkage report schema (SLS/time-dependent)."""
    # TODO: Implement when shrinkage_report is available
    return None


# Module Registry - ordered list of all modules
MODULE_REGISTRY = [
    {
        "module_id": "bending",
        "title": "Bending",
        "ensure_run": ensure_bending_run,
        "get_schema": get_bending_schema,
    },
    {
        "module_id": "shear",
        "title": "Shear",
        "ensure_run": ensure_shear_run,
        "get_schema": get_shear_schema,
    },
    {
        "module_id": "crack",
        "title": "Crack Control",
        "ensure_run": ensure_crack_run,
        "get_schema": get_crack_schema,
    },
    {
        "module_id": "deflection",
        "title": "Deflection",
        "ensure_run": ensure_deflection_run,
        "get_schema": get_deflection_schema,
    },
    {
        "module_id": "creep",
        "title": "Creep",
        "ensure_run": ensure_creep_run,
        "get_schema": get_creep_schema,
    },
    {
        "module_id": "shrinkage",
        "title": "Shrinkage",
        "ensure_run": ensure_shrinkage_run,
        "get_schema": get_shrinkage_schema,
    },
]


def run_all_modules(force: bool = True, include_sls: bool = True, include_min: bool = True):
    """
    Run all modules in the registry.
    
    Args:
        force: If True, run even if inputs haven't changed
        include_sls: Include SLS calculations
        include_min: Include minimum requirements checks
    """
    if "results" not in st.session_state:
        st.session_state["results"] = {}
    results = st.session_state["results"]
    
    for module in MODULE_REGISTRY:
        try:
            module["ensure_run"](st.session_state, results)
        except Exception as e:
            results[f"{module['module_id']}_error"] = str(e)


def get_all_module_schemas() -> List[Dict[str, Any]]:
    """
    Get report schemas for all modules that have them.
    
    Returns:
        List of module schema dicts (only modules that return a schema)
    """
    if "results" not in st.session_state:
        st.session_state["results"] = {}
    results = st.session_state["results"]
    
    schemas = []
    for module in MODULE_REGISTRY:
        try:
            schema = module["get_schema"](st.session_state, results)
            if schema:
                schemas.append(schema)
        except Exception as e:
            # Skip modules that don't have schemas yet
            pass
    
    return schemas

