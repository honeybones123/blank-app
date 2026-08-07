"""
Figure Export Utilities

Functions to export matplotlib and plotly figures to PNG files for PDF reports.
"""

import os
import tempfile
import uuid
import inspect
import streamlit as st


def call_with_supported_kwargs(fn, **kwargs):
    """
    Call a function with only the keyword arguments it accepts.
    
    This makes diagram function calls signature-safe by filtering out
    unsupported parameters (e.g., b_mm vs b, d_mm vs d).
    
    Args:
        fn: Function to call
        **kwargs: Keyword arguments to filter
    
    Returns:
        Result of calling fn with filtered kwargs
    
    Raises:
        ValueError: If required parameters are missing and function has no **kwargs
    """
    try:
        sig = inspect.signature(fn)
        accepted = set(sig.parameters.keys())
        
        # Check if function accepts **kwargs
        has_var_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in sig.parameters.values()
        )
        
        # Filter kwargs to only accepted parameters
        filtered = {k: v for k, v in kwargs.items() if k in accepted}
        
        # Check required parameters
        required = {
            name for name, param in sig.parameters.items()
            if param.default == inspect.Parameter.empty
            and param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        }
        
        missing = required - set(filtered.keys())
        if missing and not has_var_kwargs:
            raise ValueError(
                f"Diagram function {fn.__name__} requires params: {', '.join(missing)}. "
                f"Provided: {', '.join(kwargs.keys())}"
            )
        
        return fn(**filtered)
    except Exception as e:
        raise ValueError(f"Error calling {fn.__name__}: {e}")


def export_box_diagram_png(fig_or_callable, key: str, caption: str = "", w_mm: float = 55.0, h_mm: float = 28.0) -> dict:
    """
    Export a figure to PNG for PDF reporting.
    
    Args:
        fig_or_callable: Either a matplotlib figure, plotly figure, or a callable that returns a figure
        key: Unique identifier for this diagram (used for temp file naming)
        caption: Optional caption text
        w_mm: Target width in mm (default 55mm)
        h_mm: Target height in mm (default 28mm)
    
    Returns:
        dict with "path" (absolute path), "caption" (str), "w_mm" (float), "h_mm" (float)
        Returns None if export fails
    """
    try:
        # Create temp directory if it doesn't exist
        temp_dir = tempfile.gettempdir()
        
        # Sanitize key for filename (replace dots and spaces with underscores)
        sanitized_key = key.replace(".", "_").replace(" ", "_").replace("/", "_")
        
        # Generate unique filename with UUID to avoid collisions
        unique_suffix = str(uuid.uuid4())[:8]
        filename = f"report_diagram_{sanitized_key}_{unique_suffix}.png"
        filepath = os.path.join(temp_dir, filename)
        
        # If callable, call it to get the figure
        if callable(fig_or_callable) and not hasattr(fig_or_callable, "savefig") and not hasattr(fig_or_callable, "write_image"):
            # If it's a callable that takes no args, call it directly
            # Otherwise, it might be a lambda that captures variables, so call it
            try:
                sig = inspect.signature(fig_or_callable)
                if len(sig.parameters) == 0:
                    fig = fig_or_callable()
                else:
                    # Callable with parameters - call it directly (it should be a closure)
                    fig = fig_or_callable()
            except Exception:
                # Fallback: try calling with no args
                fig = fig_or_callable()
        else:
            fig = fig_or_callable
        
        # Export matplotlib figure
        if hasattr(fig, "savefig"):
            import matplotlib.pyplot as plt
            fig.savefig(filepath, dpi=150, bbox_inches="tight", format="png")
            plt.close(fig)
            return {
                "path": filepath,
                "caption": caption,
                "w_mm": w_mm,
                "h_mm": h_mm,
            }
        
        # Plotly/Kaleido export is deliberately not attempted here.  The
        # synchronous ``write_image`` call can hang indefinitely when the
        # Kaleido subprocess is unavailable or mismatched with the active
        # Plotly version.  That used to leave the Streamlit PDF button stuck
        # on "Generating PDF report..." forever.  The report builder treats a
        # missing diagram as a normal, recoverable condition and still emits
        # the complete calculations/results report.
        elif hasattr(fig, "write_image"):
            return None
        
        else:
            st.warning(f"Unknown figure type for {key}")
            return None
            
    except Exception as e:
        st.warning(f"Failed to export diagram {key}: {e}")
        return None


def cleanup_exported_figures(fig_dicts: list):
    """
    Clean up temporary PNG files after PDF generation.
    
    Args:
        fig_dicts: List of diagram dicts (each with "path" key)
    """
    for fig_dict in fig_dicts:
        if isinstance(fig_dict, dict):
            path = fig_dict.get("path")
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
