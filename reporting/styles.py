"""
Report Styling - Standardized styles and table builders for PDF reports

Centralizes all styling rules and table builders for consistency.
"""

from typing import List, Dict, Any

try:
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import mm, inch
    from reportlab.lib.pagesizes import A4
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    colors = None
    getSampleStyleSheet = None
    ParagraphStyle = None
    TA_CENTER = None
    TA_LEFT = None
    TA_RIGHT = None
    Table = None
    TableStyle = None
    Paragraph = None
    Spacer = None
    mm = None
    inch = None
    A4 = None


# Status color mapping
STATUS_COLORS = {
    "PASS": {
        "bg": colors.HexColor("#28a745") if REPORTLAB_AVAILABLE else None,  # green
        "text": colors.white if REPORTLAB_AVAILABLE else None,
    },
    "FAIL": {
        "bg": colors.HexColor("#dc3545") if REPORTLAB_AVAILABLE else None,  # red
        "text": colors.white if REPORTLAB_AVAILABLE else None,
    },
    "WARN": {
        "bg": colors.HexColor("#ffc107") if REPORTLAB_AVAILABLE else None,  # amber
        "text": colors.black if REPORTLAB_AVAILABLE else None,
    },
}


def get_base_styles():
    """Get base style sheet with custom styles added."""
    if not REPORTLAB_AVAILABLE:
        return {}
    
    styles = getSampleStyleSheet()
    
    # Heading styles
    styles.add(ParagraphStyle(
        name="Heading1",
        parent=styles["Heading1"],
        fontSize=20,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1f77b4"),
        spaceAfter=12,
    ))
    
    styles.add(ParagraphStyle(
        name="Heading2",
        parent=styles["Heading2"],
        fontSize=16,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1f77b4"),
        spaceAfter=8,
    ))
    
    styles.add(ParagraphStyle(
        name="Heading3",
        parent=styles["Heading3"],
        fontSize=14,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#333333"),
        spaceAfter=6,
    ))
    
    # Step styles (for calculation steps)
    styles.add(ParagraphStyle(
        name="StepTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        spaceBefore=6,
        spaceAfter=2,
    ))
    
    styles.add(ParagraphStyle(
        name="StepClause",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        textColor=colors.grey,
        spaceAfter=4,
    ))
    
    styles.add(ParagraphStyle(
        name="StepEq",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=10,
        spaceAfter=1,
    ))
    
    return styles


def status_style(status: str):
    """Get table cell styling for a status value."""
    if not REPORTLAB_AVAILABLE:
        return []
    
    status_upper = status.upper() if status else ""
    
    if "PASS" in status_upper:
        return [
            ("BACKGROUND", (0, 0), (-1, -1), STATUS_COLORS["PASS"]["bg"]),
            ("TEXTCOLOR", (0, 0), (-1, -1), STATUS_COLORS["PASS"]["text"]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ]
    elif "FAIL" in status_upper:
        return [
            ("BACKGROUND", (0, 0), (-1, -1), STATUS_COLORS["FAIL"]["bg"]),
            ("TEXTCOLOR", (0, 0), (-1, -1), STATUS_COLORS["FAIL"]["text"]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ]
    elif "WARN" in status_upper:
        return [
            ("BACKGROUND", (0, 0), (-1, -1), STATUS_COLORS["WARN"]["bg"]),
            ("TEXTCOLOR", (0, 0), (-1, -1), STATUS_COLORS["WARN"]["text"]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ]
    else:
        return [
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]


def build_summary_table(checks: List, styles) -> Table:
    """Build cover page summary table with all checks."""
    if not REPORTLAB_AVAILABLE:
        return None
    
    data = [["Check", "Demand", "Capacity", "Utilisation", "Status"]]
    
    for check in checks:
        demand_str = f"{check.demand_value:.2f} {check.demand_units}" if check.demand_value is not None else "—"
        capacity_str = f"{check.capacity_value:.2f} {check.capacity_units}" if check.capacity_value is not None else "—"
        util_str = f"{check.utilisation:.2f}" if check.utilisation is not None else "—"
        
        data.append([
            check.title,
            demand_str,
            capacity_str,
            util_str,
            check.status,
        ])
    
    col_widths = [110*mm, 110*mm, 110*mm, 80*mm, 60*mm]
    table = Table(data, colWidths=col_widths)
    
    # Base table style
    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),  # Check column
        ("ALIGN", (1, 0), (3, -1), "RIGHT"),  # Demand, Capacity, Utilisation
        ("ALIGN", (4, 0), (4, -1), "CENTER"),  # Status
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    
    # Apply status colors to data rows
    for i, check in enumerate(checks, start=1):
        status_styles = status_style(check.status)
        for style_tuple in status_styles:
            if len(style_tuple) == 4:  # (command, start, stop, value)
                cmd, start, stop, value = style_tuple
                # Adjust coordinates: status column is index 4
                table_style.append((cmd, (4, i), (4, i), value))
    
    table.setStyle(TableStyle(table_style))
    return table


def build_key_value_table(data: Dict[str, Any], title: str, styles) -> List:
    """Build a key-value table for inputs section."""
    if not REPORTLAB_AVAILABLE:
        return []
    
    flowables = []
    
    # Section heading
    flowables.append(Paragraph(f"<b>{title}</b>", styles["Heading3"]))
    flowables.append(Spacer(1, 4))
    
    # Build table data
    table_data = []
    for key, value in data.items():
        # Format key nicely (replace underscores, capitalize)
        label = key.replace("_", " ").title()
        
        # Format value
        if isinstance(value, float):
            if value == int(value):
                value_str = str(int(value))
            else:
                value_str = f"{value:.2f}"
        else:
            value_str = str(value) if value is not None else "—"
        
        table_data.append([label, value_str])
    
    if table_data:
        table = Table(table_data, colWidths=[2.5*inch, 3*inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8f9fa")),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        flowables.append(table)
        flowables.append(Spacer(1, 8))
    
    return flowables


def build_two_line_summary_table(check: "CheckResult", styles) -> Table:
    """Build 2-line summary table for a check (Outcome, Utilisation, Capacity vs Demand)."""
    if not REPORTLAB_AVAILABLE:
        return None
    
    data = [
        ["Outcome", check.status],
        ["Utilisation", f"{check.utilisation:.2f}" if check.utilisation is not None else "—"],
        [f"{check.capacity_label}", f"{check.capacity_value:.2f} {check.capacity_units}" if check.capacity_value is not None else "—"],
        [f"{check.demand_label}", f"{check.demand_value:.2f} {check.demand_units}" if check.demand_value is not None else "—"],
    ]
    
    table = Table(data, colWidths=[2*inch, 3*inch])
    
    # Base style
    table_style = [
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    
    # Apply status color to Outcome cell (row 0, column 1)
    status_styles = status_style(check.status)
    for style_tuple in status_styles:
        if len(style_tuple) == 4:
            cmd, start, stop, value = style_tuple
            table_style.append((cmd, (1, 0), (1, 0), value))
    
    table.setStyle(TableStyle(table_style))
    return table

