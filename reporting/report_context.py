"""
Report Context - Single source of truth for PDF report generation

Defines the data structures and context object that carries all report data.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Callable, Optional


@dataclass
class CheckResult:
    """Result data for a single design check."""
    key: str                    # "bending_uls", "shear_uls", "crack_sls"
    title: str                  # "Flexural capacity (ULS)", "Shear capacity (ULS)"
    group: str                  # "ULS" / "SLS" / "MIN"
    status: str                 # "PASS" / "FAIL" / "WARN" / "N/A"
    utilisation: float          # 0.72 (or None if not applicable)
    demand_label: str           # "Mu*"
    demand_value: float         # 500.0
    demand_units: str           # "kNm"
    capacity_label: str         # "phiMu"
    capacity_value: float       # 650.0
    capacity_units: str         # "kNm"
    steps: List[Dict[str, str]] = field(default_factory=list)  # [{"title": "...", "body": "..."}]
    figures: List[str] = field(default_factory=list)  # figure_ids


@dataclass
class ReportContext:
    """Complete context for PDF report generation."""
    meta: Dict[str, Any]  # project, member, author, date, code, units, disclaimer, assumptions
    inputs: Dict[str, Dict[str, Any]]  # {"geometry": {...}, "materials": {...}, "reinforcement": {...}}
    checks: List[CheckResult]
    figure_exporters: Dict[str, Callable[[], Optional[str]]] = field(default_factory=dict)  # figure_id -> returns image path or None

