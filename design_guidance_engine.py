"""Compatibility wrapper for the Design Guide brain.

The implementation now lives in ``design_brain.engine``. Keep this module so
existing imports, including legacy helper imports used by old diagnostics,
continue to resolve unchanged.
"""

from design_brain import engine as _engine

globals().update(
    {
        name: getattr(_engine, name)
        for name in dir(_engine)
        if not name.startswith("__")
    }
)

__all__ = [name for name in globals() if not name.startswith("__")]
