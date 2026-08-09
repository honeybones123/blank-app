"""Authoritative AS 3600 metadata owned by the engineering checks."""

from __future__ import annotations


AS3600_2018_CHECKS: dict[str, dict[str, str]] = {
    "bending_capacity": {"standard": "AS 3600", "edition": "2018", "clause": "8.1.3", "title": "Flexural capacity"},
    "bending_ductility": {"standard": "AS 3600", "edition": "2018", "clause": "8.1.5", "title": "Ductility and neutral-axis limit"},
    "minimum_flexural_strength": {"standard": "AS 3600", "edition": "2018", "clause": "8.1.6.1", "title": "Minimum flexural strength"},
    "shear_strength": {"standard": "AS 3600", "edition": "2018", "clause": "8.2.3.1", "title": "Overall design shear strength"},
    "shear_web_crushing": {"standard": "AS 3600", "edition": "2018", "clause": "8.2.3.3", "title": "Maximum shear strength and web crushing"},
    "concrete_shear_capacity": {"standard": "AS 3600", "edition": "2018", "clause": "8.2.4.1", "title": "Concrete shear contribution"},
    "transverse_reinforcement_required": {"standard": "AS 3600", "edition": "2018", "clause": "8.2.1.6", "title": "Transverse reinforcement requirement"},
    "minimum_shear_reinforcement": {"standard": "AS 3600", "edition": "2018", "clause": "8.2.1.7", "title": "Minimum shear reinforcement"},
    "shear_reinforcement_capacity": {"standard": "AS 3600", "edition": "2018", "clause": "8.2.5.2", "title": "Shear reinforcement contribution"},
    "short_term_deflection": {"standard": "AS 3600", "edition": "2018", "clause": "8.5.3.1", "title": "Short-term deflection"},
    "long_term_deflection": {"standard": "AS 3600", "edition": "2018", "clause": "8.5.3.2", "title": "Additional long-term deflection"},
    "span_depth_check": {"standard": "AS 3600", "edition": "2018", "clause": "8.5.4", "title": "Span-to-depth check"},
    "general_crack_control": {"standard": "AS 3600", "edition": "2018", "clause": "8.6.1", "title": "General crack-control detailing"},
    "crack_table_method": {"standard": "AS 3600", "edition": "2018", "clause": "8.6.2.2", "title": "Crack-control table method"},
    "direct_crack_width": {"standard": "AS 3600", "edition": "2018", "clause": "8.6.2.3", "title": "Direct crack-width calculation"},
    "durability_cover": {"standard": "AS 3600", "edition": "2018", "clause": "4.10.3", "title": "Durability concrete cover"},
}


def check_metadata(*check_ids: str) -> dict[str, dict[str, str]]:
    """Return copied metadata so calculation results own their payload."""
    return {check_id: dict(AS3600_2018_CHECKS[check_id]) for check_id in check_ids}

