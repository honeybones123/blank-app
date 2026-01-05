"""
PDF Report Builder

Builds professional PDF reports from extracted content.
Uses reportlab for PDF generation.
"""

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    # Define dummy values to avoid NameError if code tries to use them
    A4 = None
    SimpleDocTemplate = None
    Table = None
    TableStyle = None
    Paragraph = None
    Spacer = None
    PageBreak = None
    Image = None
    colors = None
    inch = None
    mm = None
    getSampleStyleSheet = None
    ParagraphStyle = None


def draw_header_footer(canvas, doc, meta):
    """
    Draws header and footer on every page.
    
    Args:
        canvas: ReportLab canvas object
        doc: Document object
        meta: dict with project/app metadata
    """
    canvas.saveState()
    
    page_width, page_height = A4
    
    # --- HEADER ---
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(
        20 * mm,
        page_height - 15 * mm,
        meta.get("app_name", "StructuralBase")
    )
    
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(
        page_width - 20 * mm,
        page_height - 15 * mm,
        f"Standard: {meta.get('standard', 'AS 3600:2018')}"
    )
    
    canvas.drawString(
        20 * mm,
        page_height - 20 * mm,
        f"Project: {meta.get('project', 'Untitled Project')}"
    )
    
    canvas.drawRightString(
        page_width - 20 * mm,
        page_height - 20 * mm,
        f"Element: {meta.get('element', 'RC Beam')}"
    )
    
    # Header line
    canvas.setLineWidth(0.5)
    canvas.line(
        20 * mm,
        page_height - 23 * mm,
        page_width - 20 * mm,
        page_height - 23 * mm,
    )
    
    # --- FOOTER ---
    canvas.setFont("Helvetica", 8)
    
    page_num_text = f"Page {doc.page}"
    canvas.drawRightString(
        page_width - 20 * mm,
        15 * mm,
        page_num_text
    )
    
    from datetime import datetime
    date_str = datetime.now().strftime("%d %b %Y")
    canvas.drawString(
        20 * mm,
        15 * mm,
        f"Generated: {date_str}"
    )
    
    canvas.setFont("Helvetica-Oblique", 7)
    canvas.drawCentredString(
        page_width / 2,
        10 * mm,
        meta.get(
            "disclaimer",
            "This report is computer generated and must be reviewed by a qualified engineer."
        )
    )
    
    canvas.restoreState()


def _parse_step_string(step_str):
    """
    Parse a step string into structured components.
    
    Expected format:
    "Title — AS 3600:2018 Cl. X.X\nEquation 1\nEquation 2"
    
    Returns:
        dict with keys: title, clause, equations, notes
    """
    if not step_str or not isinstance(step_str, str):
        return {"title": "", "clause": "", "equations": [], "notes": []}
    
    lines = step_str.strip().split('\n')
    if not lines:
        return {"title": "", "clause": "", "equations": [], "notes": []}
    
    # First line contains title and clause
    first_line = lines[0]
    
    # Split on " — " to separate title and clause
    if " — " in first_line:
        parts = first_line.split(" — ", 1)
        title = parts[0].strip()
        clause = parts[1].strip() if len(parts) > 1 else ""
    else:
        # No separator, treat entire first line as title
        title = first_line.strip()
        clause = ""
    
    # Remaining lines are equations
    equations = [line.strip() for line in lines[1:] if line.strip()]
    
    return {
        "title": title,
        "clause": clause,
        "equations": equations,
        "notes": [],
    }


# Status style mapping for color-coding check boxes
# Color palette matching the app (soft pastel backgrounds + darker text)
PASS_BG = colors.HexColor("#d5f5d5")  # Light green background (matches inputs_page.py)
PASS_TXT = colors.HexColor("#155724")  # Dark green text
FAIL_BG = colors.HexColor("#f8d0d0")   # Light red background (matches inputs_page.py)
FAIL_TXT = colors.HexColor("#721c24")  # Dark red text
WARN_BG = colors.HexColor("#fff4c2")   # Light amber background (from inputs_page.py)
WARN_TXT = colors.HexColor("#856404")  # Dark amber text
HEADER_BG = colors.HexColor("#e0e0e0")  # Light grey header background

STATUS_STYLES = {
    "pass": {
        "accent": colors.HexColor("#28a745"),  # green border
        "fill": PASS_BG,                        # light green background (matches app)
        "text": "PASS",
        "text_color": PASS_TXT,                 # dark green text (matches app)
    },
    "fail": {
        "accent": colors.HexColor("#dc3545"),  # red border
        "fill": FAIL_BG,                        # light red background (matches app)
        "text": "FAIL",
        "text_color": FAIL_TXT,                 # dark red text (matches app)
    },
    "warn": {
        "accent": colors.HexColor("#ffc107"),  # amber
        "fill": colors.HexColor("#fff3cd"),    # light amber
        "text": "WARN",
        "text_color": colors.HexColor("#856404"),  # dark amber
    },
    "info": {
        "accent": colors.HexColor("#1f77b4"),  # blue
        "fill": colors.HexColor("#d1ecf1"),     # light blue
        "text": "INFO",
        "text_color": colors.HexColor("#0c5460"),  # dark blue
    },
    None: {
        "accent": colors.grey,
        "fill": colors.white,
        "text": "",
        "text_color": colors.black,
    },
}


def _render_box_with_optional_diagram(story, styles, box, available_width):
    """
    Render a calc box with optional right-side diagram.
    Includes color-coding based on status (PASS/FAIL/WARN/INFO).
    
    Args:
        story: List to append Flowable objects to
        styles: ReportLab styles dict
        box: Box dict with id, title, status, result, clause, derivation, and optional diagram
        available_width: Available width for the box (in points)
    
    Returns:
        Flowable (Table) containing the box
    """
    import os
    from reportlab.platypus import Image
    from reportlab.lib.units import mm
    
    box_id = box.get("id", "")
    box_title = box.get("title", "")
    status = box.get("status", None)
    status_text = box.get("status_text", "")  # Get status_text if available
    result = box.get("result", "")
    clause = box.get("clause", "")
    derivation = box.get("derivation", [])
    diagram = box.get("diagram", None)
    
    # Get status style (default to None if status is invalid)
    status_style = STATUS_STYLES.get(status, STATUS_STYLES[None])
    accent_color = status_style["accent"]
    fill_color = status_style["fill"]
    status_label = status_text or status_style["text"]
    status_text_color = status_style["text_color"]
    
    # Only use colored fill for pass/fail/warn (not info or None)
    use_fill = status in ("pass", "fail", "warn")
    main_bg_color = fill_color if use_fill else colors.white
    
    # Build left content (calc box text) - build this first to estimate height
    left_flowables = []
    title_text = f"{box_id} {box_title}" if box_id else box_title
    
    # Add status chip if status is pass/fail/warn (small, bold, colored)
    title_with_status = f"<b>{title_text}</b>"
    if status_label and status in ("pass", "fail", "warn"):
        # Convert ReportLab Color to hex string for HTML
        def color_to_hex(color):
            """Convert ReportLab Color to hex string."""
            # Try hexval() method first (for HexColor objects)
            if hasattr(color, 'hexval'):
                try:
                    hex_str = color.hexval()
                    # Convert "0x155724" to "#155724"
                    if hex_str.startswith("0x"):
                        return "#" + hex_str[2:]
                    return hex_str
                except:
                    pass
            # Try rgb() method
            if hasattr(color, 'rgb'):
                try:
                    r, g, b = color.rgb()
                    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
                except:
                    pass
            # Fallback: try direct RGB attributes
            try:
                if hasattr(color, 'red') and hasattr(color, 'green') and hasattr(color, 'blue'):
                    r, g, b = color.red, color.green, color.blue
                    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            except:
                pass
            return "#000000"  # Black fallback
        
        hex_color = color_to_hex(status_text_color)
        # Add status chip inline (colored, bold)
        status_chip = f' <font color="{hex_color}"><b>[{status_label}]</b></font>'
        title_with_status = f"<b>{title_text}</b>{status_chip}"
    
    left_flowables.append(Paragraph(title_with_status, styles["StepTitle"]))
    
    if result:
        left_flowables.append(Paragraph(f"Result: {result}", styles["Normal"]))
    
    if clause:
        left_flowables.append(Paragraph(f"<i>{clause}</i>", styles["StepClause"]))
    
    for deriv in derivation:
        label = deriv.get("label", "")
        eq = deriv.get("eq", "")
        sub = deriv.get("sub", "")
        
        if label:
            left_flowables.append(Paragraph(f"<b>{label}:</b>", styles["Normal"]))
        if eq:
            safe_eq = (str(eq)
                      .replace("&", "&amp;")
                      .replace("<", "&lt;")
                      .replace(">", "&gt;"))
            left_flowables.append(Paragraph(f"  {safe_eq}", styles["StepEq"]))
        if sub:
            safe_sub = (str(sub)
                       .replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;"))
            left_flowables.append(Paragraph(f"  = {safe_sub}", styles["StepEq"]))
    
    # Account for accent bar width first
    accent_width = 6  # 6 points wide
    main_content_width = available_width - accent_width
    
    # Compute available widths (assume diagram exists for now, will adjust if not)
    # Increased default width from 55mm to 67mm for larger diagrams
    diagram_w_mm = diagram.get("w_mm", 67.0) if (diagram and isinstance(diagram, dict)) else 0.0
    
    # For special boxes (1.1, 3.2), account for extra right margin in width calculation
    extra_right_margin = diagram.get("extra_right_margin", False) if isinstance(diagram, dict) else False
    extra_margin_pts = 4 * mm if extra_right_margin else 0  # Additional 4mm for special boxes
    
    right_w = diagram_w_mm * mm if diagram_w_mm > 0 else 0.0
    gutter_w = 10  # Gutter width in points
    left_w = main_content_width - right_w - gutter_w - (8 * mm if right_w > 0 else 0) - extra_margin_pts  # Account for gutter + spacing + extra margin
    
    # If no diagram, use full width for left
    if not diagram or not isinstance(diagram, dict) or not diagram.get("path"):
        left_w = main_content_width
        right_w = 0.0
    
    # Estimate left content height by wrapping it
    left_tbl_temp = Table([[item] for item in left_flowables], colWidths=[left_w])
    left_tbl_temp.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (0, -1), 12),  # Extra left padding for border
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.grey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    # Wrap to estimate height (use large available height to get full content height)
    try:
        _, left_h = left_tbl_temp.wrap(left_w, 10000)
    except Exception:
        # Fallback if wrap fails
        left_h = mm * 50  # Default estimate
    
    # Build right content (diagram if available)
    right_content = []
    right_width = 0.0
    
    if diagram and isinstance(diagram, dict):
        diagram_path = diagram.get("path", "")
        diagram_caption = diagram.get("caption", "")
        diagram_w_mm = diagram.get("w_mm", 67.0)  # Increased from 55mm, but kept at 67mm to fit margins
        right_w = diagram_w_mm * mm
        
        if diagram_path and os.path.exists(diagram_path):
            try:
                # Verify file is actually an image by trying to get its dimensions
                try:
                    from PIL import Image as PILImage
                    pil_img = PILImage.open(diagram_path)
                    pil_img.verify()  # Verify it's a valid image
                    pil_img.close()
                    # Reopen to get dimensions (verify() closes the file)
                    pil_img = PILImage.open(diagram_path)
                    img_width, img_height = pil_img.size
                    pil_img.close()
                    
                    if img_width > 0 and img_height > 0:
                        # Determine target image max height from left content height
                        # Increased from 0.95 to 1.05 to allow diagrams to be slightly taller
                        target_h = left_h * 1.05  # Diagram can be slightly taller than box
                        
                        # Clamp to sane range (increased min/max for larger diagrams)
                        min_h = 55 * mm  # Increased from 45mm to 55mm
                        max_h = 110 * mm  # Increased from 95mm to 110mm
                        target_h = max(min_h, min(target_h, max_h))
                        
                        # Calculate scale to fit within right_w and target_h constraints
                        scale_w = right_w / img_width if img_width > 0 else 1.0
                        scale_h = target_h / img_height if img_height > 0 else 1.0
                        scale = min(scale_w, scale_h)  # Use smaller scale to fit both constraints
                        
                        # Calculate final dimensions
                        final_width = img_width * scale
                        final_height = img_height * scale
                        
                        # Create Image object with explicit width and height (fitted to constraints)
                        img = Image(diagram_path, width=final_width, height=final_height)
                        
                        # Force initialization by accessing dimensions
                        try:
                            _ = img.imageWidth
                            _ = img.imageHeight
                            # Verify dimensions are valid
                            if (hasattr(img, 'imageWidth') and img.imageWidth is not None and img.imageWidth > 0 and
                                hasattr(img, 'imageHeight') and img.imageHeight is not None and img.imageHeight > 0):
                                right_content.append(img)
                                
                                if diagram_caption:
                                    caption_style = ParagraphStyle(
                                        'DiagramCaption',
                                        parent=styles["Normal"],
                                        fontSize=7,
                                        textColor=colors.grey,
                                        alignment=TA_CENTER,
                                        spaceBefore=2,
                                        spaceAfter=0,
                                    )
                                    right_content.append(Paragraph(f"<i>{diagram_caption}</i>", caption_style))
                                
                                right_width = right_w  # Use right column width
                            else:
                                # Image dimensions invalid after creation, skip it
                                right_content = []
                                right_width = 0.0
                        except (AttributeError, TypeError, ValueError) as init_err:
                            # Image initialization failed, skip it
                            right_content = []
                            right_width = 0.0
                    else:
                        # Invalid image dimensions, skip it
                        right_content = []
                        right_width = 0.0
                except ImportError:
                    # PIL not available, try without verification
                    # Try to get image dimensions using ReportLab's ImageReader
                    try:
                        from reportlab.lib.utils import ImageReader
                        reader = ImageReader(diagram_path)
                        img_width_pts, img_height_pts = reader.getSize()
                        
                        if img_width_pts > 0 and img_height_pts > 0:
                            # Determine target image max height from left content height
                            # Increased from 0.95 to 1.05 to allow diagrams to be slightly taller
                            target_h = left_h * 1.05  # Diagram can be slightly taller than box
                            
                            # Clamp to sane range (increased min/max for larger diagrams)
                            min_h = 55 * mm  # Increased from 45mm to 55mm
                            max_h = 110 * mm  # Increased from 95mm to 110mm
                            target_h = max(min_h, min(target_h, max_h))
                            
                            # Calculate scale to fit within right_w and target_h constraints
                            scale_w = right_w / img_width_pts if img_width_pts > 0 else 1.0
                            scale_h = target_h / img_height_pts if img_height_pts > 0 else 1.0
                            scale = min(scale_w, scale_h)  # Use smaller scale to fit both constraints
                            
                            # Calculate final dimensions
                            final_width = img_width_pts * scale
                            final_height = img_height_pts * scale
                            
                            # Create Image with explicit dimensions (fitted to constraints)
                            img = Image(diagram_path, width=final_width, height=final_height)
                            right_content.append(img)
                            
                            if diagram_caption:
                                caption_style = ParagraphStyle(
                                    'DiagramCaption',
                                    parent=styles["Normal"],
                                    fontSize=7,
                                    textColor=colors.grey,
                                    alignment=TA_CENTER,
                                    spaceBefore=2,
                                    spaceAfter=0,
                                )
                                right_content.append(Paragraph(f"<i>{diagram_caption}</i>", caption_style))
                            
                            right_width = right_w  # Use right column width
                        else:
                            # Invalid dimensions, skip it
                            right_content = []
                            right_width = 0.0
                    except Exception as reader_err:
                        # ImageReader failed, skip diagram
                        right_content = []
                        right_width = 0.0
                except Exception as img_err:
                    # Image validation failed, skip it
                    right_content = []
                    right_width = 0.0
            except Exception as e:
                # If image fails to load, just skip it
                right_content = []
                right_width = 0.0
    
    # Recalculate left_w now that we know right_width (may have changed)
    gutter_w = 10  # Gutter width in points
    if right_width > 0:
        left_w = main_content_width - right_width - gutter_w - (8 * mm)  # Account for gutter + spacing
    else:
        left_w = main_content_width
    
    # Build left table with proper styling (reuse the temp table we created for height estimation)
    # Update its column width in case it changed
    left_table = Table([[item] for item in left_flowables], colWidths=[left_w])
    left_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.grey),
        ('BACKGROUND', (0, 0), (-1, -1), main_bg_color),  # Use colored fill if status is pass/fail/warn
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    # Build wrapper table
    if right_width > 0 and right_content:
        # Three-column layout: left content + gutter + right diagram
        gutter_w = 10  # Gutter width in points (spacing between calc box and diagram)
        
        right_table = Table([[item] for item in right_content], colWidths=[right_width])
        
        # Check if this is a special box (1.1 or 3.2) that needs extra right margin
        extra_right_margin = diagram.get("extra_right_margin", False) if isinstance(diagram, dict) else False
        right_padding = 12 if extra_right_margin else 8  # Extra padding for boxes 1.1 and 3.2
        
        right_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 2),  # Small padding
            ('RIGHTPADDING', (0, 0), (-1, -1), right_padding),  # Extra padding for special boxes
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        # Gutter cell (empty spacer)
        gutter_cell = Table([[""]], colWidths=[gutter_w])
        gutter_cell.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        row_data = [[left_table, gutter_cell, right_table]]
        col_widths = [left_w, gutter_w, right_width]
    else:
        # Single column layout (no diagram)
        row_data = [[left_table]]
        col_widths = [left_w]
    
    # Create accent bar cell (thin vertical bar on the left)
    accent_cell = Table([[""]], colWidths=[accent_width])
    accent_cell.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('BACKGROUND', (0, 0), (-1, -1), accent_color),  # Colored accent bar
    ]))
    
    # Build main content table (already has correct widths)
    if right_width > 0 and right_content:
        # Three-column layout: left content + gutter + right diagram
        main_row_data = [[left_table, gutter_cell, right_table]]
        main_col_widths = [left_w, gutter_w, right_width]
    else:
        # Single column layout (no diagram)
        main_row_data = [[left_table]]
        main_col_widths = [main_content_width]
    
    main_content_table = Table(main_row_data, colWidths=main_col_widths)
    main_content_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    # Create final wrapper with accent bar + main content
    wrapper = Table([[accent_cell, main_content_table]], colWidths=[accent_width, main_content_width])
    wrapper_style = TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ])
    wrapper.setStyle(wrapper_style)
    
    return wrapper


def _section_heading(title: str, subtitle: str | None, styles) -> list:
    """
    Create a professional section heading block.
    
    Args:
        title: Main section title (e.g., "ULS Checks")
        subtitle: Optional subtitle (e.g., "Ultimate Limit State")
        styles: ReportLab styles dict
    
    Returns:
        List of Flowable objects (title, subtitle if provided, divider, spacer)
    """
    flowables = []
    
    # Main title (18-22pt, bold)
    title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles.get("Heading1", styles["Heading2"]),
        fontSize=20,
        fontName='Helvetica-Bold',
        spaceAfter=4,
    )
    flowables.append(Paragraph(f"<b>{title}</b>", title_style))
    
    # Optional subtitle (10-11pt grey)
    if subtitle:
        subtitle_style = ParagraphStyle(
            'SectionSubtitle',
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.grey,
            spaceAfter=8,
        )
        flowables.append(Paragraph(f"<i>{subtitle}</i>", subtitle_style))
    
    # Thin divider line (HR)
    page_width, _ = A4
    margin = 20 * mm
    line_width = page_width - 2 * margin
    divider = Table([[""]], colWidths=[line_width], rowHeights=[1])
    divider.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1, colors.grey),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    flowables.append(divider)
    
    # Small vertical spacing after
    flowables.append(Spacer(1, 12))
    
    return flowables


def _render_tabs_and_boxes(story, styles, module_title, summary, tabs=None, groups=None):
    """
    Render tabs and calc boxes structure (preferred format).
    
    Supports both legacy format (tabs) and unified format (groups).
    
    Args:
        story: List to append Paragraph/Spacer objects to
        styles: ReportLab styles dict
        module_title: Module title (e.g., "Bending")
        summary: List of tuples [("Demand", "..."), ...]
        tabs: List of tab dicts (legacy format), each with "tab_title" and "boxes"
        groups: List of group dicts (unified format), each with "group_id", "group_title", "group_subtitle", "tabs"
    """
    # Module title
    story.append(Paragraph(f"<b>{module_title}</b>", styles["Heading2"]))
    story.append(Spacer(1, 4))
    
    # Summary table
    if summary:
        summary_data = [["", ""]]
        outcome_row_idx = None
        
        # Create a bold style for labels
        label_bold_style = ParagraphStyle(
            'LabelBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
        )
        
        for idx, (label, value) in enumerate(summary):
            # Use Paragraph for bold labels instead of raw HTML strings
            label_para = Paragraph(f"<b>{label}:</b>", label_bold_style)
            summary_data.append([label_para, value])
            if label.lower() == "outcome":
                outcome_row_idx = idx + 1  # +1 because header row is at index 0
        
        summary_table = Table(summary_data, colWidths=[2*inch, 3*inch])
        
        # Base table style
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        # Color outcome cell if it's PASS/FAIL
        if outcome_row_idx is not None:
            outcome_value = summary_data[outcome_row_idx][1] if outcome_row_idx < len(summary_data) else ""
            outcome_upper = outcome_value.upper()
            
            if "PASS" in outcome_upper:
                # Green background + white text for PASS
                table_style.extend([
                    ('BACKGROUND', (1, outcome_row_idx), (1, outcome_row_idx), STATUS_STYLES["pass"]["fill"]),
                    ('TEXTCOLOR', (1, outcome_row_idx), (1, outcome_row_idx), STATUS_STYLES["pass"]["text_color"]),
                    ('ALIGN', (1, outcome_row_idx), (1, outcome_row_idx), 'CENTER'),
                    ('FONTNAME', (1, outcome_row_idx), (1, outcome_row_idx), 'Helvetica-Bold'),
                ])
            elif "FAIL" in outcome_upper:
                # Red background + white text for FAIL
                table_style.extend([
                    ('BACKGROUND', (1, outcome_row_idx), (1, outcome_row_idx), STATUS_STYLES["fail"]["fill"]),
                    ('TEXTCOLOR', (1, outcome_row_idx), (1, outcome_row_idx), STATUS_STYLES["fail"]["text_color"]),
                    ('ALIGN', (1, outcome_row_idx), (1, outcome_row_idx), 'CENTER'),
                    ('FONTNAME', (1, outcome_row_idx), (1, outcome_row_idx), 'Helvetica-Bold'),
                ])
        
        summary_table.setStyle(TableStyle(table_style))
        story.append(summary_table)
        story.append(Spacer(1, 8))
    
    # Calculate available width (A4 width - margins)
    page_width, page_height = A4
    left_margin = 20 * mm
    right_margin = 25 * mm  # Increased from 20mm to 25mm for diagram safety
    available_width = page_width - left_margin - right_margin
    
    # Track if we've started rendering checks (to avoid page break on first section)
    already_started_checks = len(story) > 0
    
    # Unified format: render groups
    if groups:
        for group_idx, group in enumerate(groups):
            group_title = group.get("group_title", "")
            group_subtitle = group.get("group_subtitle", "")
            group_tabs = group.get("tabs", [])
            
            # Insert page break before each major group (ULS, SLS, Minimum)
            # But not if it's the very first content
            if group_title in ("ULS Checks", "SLS Checks", "Minimum Requirements"):
                if already_started_checks or group_idx > 0:
                    story.append(PageBreak())
                already_started_checks = True
            
            # Add professional section heading
            heading_flowables = _section_heading(group_title, group_subtitle, styles)
            story.extend(heading_flowables)
            
            # Render all tabs in this group
            for tab in group_tabs:
                boxes = tab.get("boxes", [])
                
                # Render each calc box
                for box in boxes:
                    box_flowable = _render_box_with_optional_diagram(story, styles, box, available_width)
                    story.append(box_flowable)
                    story.append(Spacer(1, 6))
            
            # Spacer between groups
            story.append(Spacer(1, 8))
    
    # Legacy format: render tabs directly
    elif tabs:
        for tab_idx, tab in enumerate(tabs):
            tab_title = tab.get("tab_title", "Tab")
            boxes = tab.get("boxes", [])
            
            # Map tab titles to section headings with subtitles
            section_headings = {
                "ULS Checks": ("ULS Checks", "Ultimate Limit State"),
                "SLS Checks": ("SLS Checks", "Serviceability Limit State"),
                "Minimum strength checks": ("Minimum Requirements", "Code minimums and detailing checks"),
                "Minimum Requirements": ("Minimum Requirements", "Code minimums and detailing checks"),
            }
            
            # Get section heading info
            section_info = section_headings.get(tab_title, (tab_title, None))
            section_title, section_subtitle = section_info
            
            # Insert page break before each major section (ULS, SLS, Minimum)
            # But not if it's the very first content
            if tab_title in ("ULS Checks", "SLS Checks", "Minimum strength checks", "Minimum Requirements"):
                if already_started_checks or tab_idx > 0:
                    story.append(PageBreak())
                already_started_checks = True
            
            # Add professional section heading
            heading_flowables = _section_heading(section_title, section_subtitle, styles)
            story.extend(heading_flowables)
            
            # Render each calc box
            for box in boxes:
                box_flowable = _render_box_with_optional_diagram(story, styles, box, available_width)
                story.append(box_flowable)
                story.append(Spacer(1, 6))
            
            # Spacer between tabs
            story.append(Spacer(1, 8))


def _render_steps(story, styles, steps):
    """
    Render calculation steps in a structured format.
    
    Args:
        story: List to append Paragraph/Spacer objects to
        styles: Style sheet
        steps: List of step strings or step dicts
    """
    if not steps:
        story.append(Paragraph("Checks:", styles["Heading3"]))
        story.append(Paragraph("Checks not available for this module yet. Run the check module(s) or use 'Run all checks' before exporting.", styles["Normal"]))
        story.append(Spacer(1, 6))
        return
    
    story.append(Paragraph("Checks:", styles["Heading3"]))
    story.append(Spacer(1, 4))
    
    for i, step in enumerate(steps, start=1):
        # Handle both dict and string formats
        if isinstance(step, dict):
            title = step.get("title", f"Check {i}")
            clause = step.get("clause", "")
            equations = step.get("equations", []) or []
            notes = step.get("notes", []) or []
        else:
            # Parse string format
            parsed = _parse_step_string(str(step))
            title = parsed["title"] or f"Check {i}"
            clause = parsed["clause"]
            equations = parsed["equations"]
            notes = parsed["notes"]
        
        # Check title
        story.append(Paragraph(f"Check {i} — {title}", styles["StepTitle"]))
        
        # Clause line
        if clause:
            story.append(Paragraph(clause, styles["StepClause"]))
        
        # Equations: each on its own line, monospace
        for eq in equations:
            # Escape HTML-sensitive characters
            safe = (str(eq)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))
            story.append(Paragraph(safe, styles["StepEq"]))
        
        # Notes (optional)
        for n in notes:
            safe_n = (str(n)
                      .replace("&", "&amp;")
                      .replace("<", "&lt;")
                      .replace(">", "&gt;"))
            story.append(Paragraph(f"• {safe_n}", styles["StepNote"]))
        
        # Spacer between steps
        story.append(Spacer(1, 6))


def build_pdf_report(summary_rows, inputs_sections, check_sections, temp_figures=None):
    """
    Build PDF report from extracted content.
    
    Args:
        summary_rows: List of dicts with Check, Demand, Capacity, Utilisation, Status
        inputs_sections: Dict with geometry, materials, reinforcement, actions
        check_sections: List of dicts with check details (title, summary, steps, figures)
        temp_figures: List to append temp figure file paths (optional)
    
    Returns:
        bytes: PDF file as bytes
    
    Raises:
        ImportError: If reportlab is not installed
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError(
            "reportlab is not installed. Please install it with: pip install reportlab"
        )
    
    # Re-import to ensure names are in scope (in case of any import issues)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch, mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError as e:
        raise ImportError(
            f"Failed to import reportlab components: {e}. "
            "Please ensure reportlab is properly installed: pip install reportlab"
        ) from e
    
    import io
    import os
    from datetime import datetime
    import streamlit as st
    
    # Build metadata
    meta = {
        "app_name": "StructuralBase",
        "project": st.session_state.get("project_name", "Untitled Project"),
        "element": "Reinforced Concrete Beam",
        "standard": "AS 3600:2018",
        "version": "v0.9.0",
        "disclaimer": "This report is computer generated and must be reviewed by a qualified engineer.",
    }
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=30 * mm,
        bottomMargin=25 * mm,
    )
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=30,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=12,
    )
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=8,
        spaceBefore=12,
    )
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        leftIndent=0.2*inch,
    )
    
    # Step-specific styles
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
    
    styles.add(ParagraphStyle(
        name="StepNote",
        parent=styles["Normal"],
        fontSize=8.5,
        textColor=colors.black,
        leftIndent=8,
        spaceAfter=2,
    ))
    
    # Cover / Title Page
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("Beam Design Report", title_style))
    story.append(Spacer(1, 0.4*inch))
    
    # Metadata block (Project, Element, Standard, Units)
    meta_data = [
        ["Project:", meta.get("project", "Untitled Project")],
        ["Element:", meta.get("element", "Reinforced Concrete Beam")],
        ["Standard:", meta.get("standard", "AS 3600:2018")],
        ["Prepared by:", st.session_state.get("user_name", "Engineer")],
        ["Date:", datetime.now().strftime("%d %b %Y")],
        ["Units:", "kN, mm, MPa"],
    ]
    meta_table = Table(meta_data, colWidths=[2.0*inch, 3.5*inch])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Summary Table (on cover page)
    if summary_rows:
        story.append(Paragraph("Summary", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        # Detect if we have Demand/Capacity columns or just Utilisation
        has_demand_capacity = len(summary_rows) > 0 and "Demand" in summary_rows[0] and "Capacity" in summary_rows[0]
        
        # Calculate available width (page width minus margins)
        page_width, page_height = A4
        left_margin = 20 * mm
        right_margin = 20 * mm
        available_width = page_width - left_margin - right_margin
        
        # Create table cell styles
        header_style = ParagraphStyle(
            'SummaryHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
        )
        cell_style = ParagraphStyle(
            'SummaryCell',
            parent=styles['Normal'],
            fontSize=9,
        )
        cell_center_style = ParagraphStyle(
            'SummaryCellCenter',
            parent=cell_style,
            alignment=TA_CENTER,
        )
        cell_right_style = ParagraphStyle(
            'SummaryCellRight',
            parent=cell_style,
            alignment=TA_RIGHT,
        )
        
        if has_demand_capacity:
            # 5-column table: Check, Demand, Capacity, Utilisation, Outcome
            # Proportional column widths: 28%, 20%, 20%, 12%, 20% (totals 100%)
            data = []
            # Header row with Paragraph objects
            data.append([
                Paragraph("<b>Check</b>", header_style),
                Paragraph("<b>Demand</b>", header_style),
                Paragraph("<b>Capacity</b>", header_style),
                Paragraph("<b>Util.</b>", header_style),
                Paragraph("<b>Outcome</b>", header_style),
            ])
            
            # Data rows with Paragraph objects (so text wraps)
            for row in summary_rows:
                status = row.get("Status", "")  # Data key is "Status", but header is "Outcome"
                data.append([
                    Paragraph(row.get("Check", ""), cell_style),
                    Paragraph(row.get("Demand", ""), cell_right_style),
                    Paragraph(row.get("Capacity", ""), cell_right_style),
                    Paragraph(row.get("Utilisation", ""), cell_right_style),
                    Paragraph(f"<b>{status}</b>" if status else "", cell_center_style),
                ])
            
            # Proportional column widths based on available width
            col_widths = [
                0.28 * available_width,  # Check: 28%
                0.20 * available_width,  # Demand: 20%
                0.20 * available_width,  # Capacity: 20%
                0.12 * available_width,  # Utilisation: 12%
                0.20 * available_width,  # Outcome: 20%
            ]
        else:
            # 3-column table: Check, Utilisation, Status (legacy fallback)
            data = []
            data.append([
                Paragraph("<b>Check</b>", header_style),
                Paragraph("<b>Utilisation</b>", header_style),
                Paragraph("<b>Outcome</b>", header_style),
            ])
            for row in summary_rows:
                status = row.get("Status", "")
                data.append([
                    Paragraph(row.get("Check", ""), cell_style),
                    Paragraph(row.get("Utilisation", ""), cell_right_style),
                    Paragraph(f"<b>{status}</b>" if status else "", cell_center_style),
                ])
            
            # Proportional column widths for 3-column table
            col_widths = [
                0.50 * available_width,  # Check: 50%
                0.25 * available_width,  # Utilisation: 25%
                0.25 * available_width,  # Outcome: 25%
            ]
        
        table = Table(data, colWidths=col_widths, hAlign="LEFT")
        
        # Table style with PASS/FAIL coloring (using app color palette)
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (1, 1), (-1, -1), 4),  # Data rows
            ('BOTTOMPADDING', (1, 1), (-1, -1), 4),
        ]
        
        if has_demand_capacity:
            # Alignment: Check=LEFT, Demand/Capacity/Utilisation=RIGHT, Outcome=CENTER
            table_style.append(('ALIGN', (0, 0), (0, -1), 'LEFT'))  # Check column
            table_style.append(('ALIGN', (1, 0), (3, -1), 'RIGHT'))  # Demand, Capacity, Utilisation
            table_style.append(('ALIGN', (4, 0), (4, -1), 'CENTER'))  # Outcome
        else:
            # Alignment: Check=LEFT, Utilisation=RIGHT, Outcome=CENTER
            table_style.append(('ALIGN', (0, 0), (0, -1), 'LEFT'))
            table_style.append(('ALIGN', (1, 0), (1, -1), 'RIGHT'))
            table_style.append(('ALIGN', (2, 0), (2, -1), 'CENTER'))
        
        # Apply PASS/FAIL background colors and text colors to data rows (using app color palette)
        for i, row in enumerate(summary_rows, start=1):
            status = row.get("Status", "")
            if status == "PASS":
                table_style.append(('BACKGROUND', (0, i), (-1, i), PASS_BG))
                table_style.append(('TEXTCOLOR', (0, i), (-1, i), PASS_TXT))
            elif status == "FAIL":
                table_style.append(('BACKGROUND', (0, i), (-1, i), FAIL_BG))
                table_style.append(('TEXTCOLOR', (0, i), (-1, i), FAIL_TXT))
            else:
                # Default background for other statuses
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.white))
                table_style.append(('TEXTCOLOR', (0, i), (-1, i), colors.black))
        
        table.setStyle(TableStyle(table_style))
        
        story.append(table)
        story.append(Spacer(1, 0.3*inch))
    
    # Notes / Assumptions / Disclaimer block
    notes_style = ParagraphStyle(
        'NotesStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        leftIndent=0.1*inch,
        rightIndent=0.1*inch,
        spaceBefore=0.2*inch,
        spaceAfter=0.1*inch,
    )
    story.append(Paragraph("<b>Notes:</b>", ParagraphStyle('NotesTitle', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')))
    story.append(Paragraph(
        "This report is computer generated and must be reviewed by a qualified engineer. "
        "Design assumptions and simplifications are as per AS 3600:2018.",
        notes_style
    ))
    story.append(Paragraph(
        meta.get("disclaimer", "This report is computer generated and must be reviewed by a qualified engineer."),
        notes_style
    ))
    
    story.append(PageBreak())
    
    # Inputs Section
    if inputs_sections:
        story.append(Paragraph("Inputs", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        # Geometry table
        geom = inputs_sections.get("geometry", {})
        if geom:
            geom_table_data = []
            if "b" in geom:
                geom_table_data.append(["Width (b)", f"{geom.get('b', 'N/A'):.0f} mm"])
            if "D" in geom:
                geom_table_data.append(["Depth (D)", f"{geom.get('D', 'N/A'):.0f} mm"])
            if "L" in geom:
                geom_table_data.append(["Length (L)", f"{geom.get('L', 'N/A'):.0f} mm"])
            
            if geom_table_data:
                geom_table = Table(geom_table_data, colWidths=[2.5*inch, 3*inch])
                geom_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(Paragraph("<b>Geometry</b>", subheading_style))
                story.append(geom_table)
                story.append(Spacer(1, 0.15*inch))
        
        # Materials table
        mat = inputs_sections.get("materials", {})
        if mat:
            mat_table_data = []
            if "fc" in mat:
                mat_table_data.append(["Concrete strength (f'c)", f"{mat.get('fc', 'N/A'):.1f} MPa"])
            if "fsy" in mat:
                mat_table_data.append(["Steel yield strength (fsy)", f"{mat.get('fsy', 'N/A'):.0f} MPa"])
            if "Ec" in mat:
                mat_table_data.append(["Concrete modulus (Ec)", f"{mat.get('Ec', 'N/A'):.0f} MPa"])
            if "Es" in mat:
                mat_table_data.append(["Steel modulus (Es)", f"{mat.get('Es', 'N/A'):.0f} MPa"])
            
            if mat_table_data:
                mat_table = Table(mat_table_data, colWidths=[2.5*inch, 3*inch])
                mat_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(Paragraph("<b>Materials</b>", subheading_style))
                story.append(mat_table)
                story.append(Spacer(1, 0.15*inch))
        
        # Reinforcement table
        reo = inputs_sections.get("reinforcement", {})
        if reo:
            reo_table_data = []
            if "Ast_bot" in reo:
                reo_table_data.append(["Bottom reinforcement (Ast,bot)", f"{reo.get('Ast_bot', 'N/A'):.0f} mm²"])
            if "Ast_top" in reo:
                reo_table_data.append(["Top reinforcement (Ast,top)", f"{reo.get('Ast_top', 'N/A'):.0f} mm²"])
            if "cover_bot" in reo:
                reo_table_data.append(["Bottom cover", f"{reo.get('cover_bot', 'N/A'):.0f} mm"])
            if "cover_top" in reo:
                reo_table_data.append(["Top cover", f"{reo.get('cover_top', 'N/A'):.0f} mm"])
            
            if reo_table_data:
                reo_table = Table(reo_table_data, colWidths=[2.5*inch, 3*inch])
                reo_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(Paragraph("<b>Reinforcement</b>", subheading_style))
                story.append(reo_table)
                story.append(Spacer(1, 0.15*inch))
        
        # Actions (if needed, can add as table too)
        actions = inputs_sections.get("actions", {})
        if actions and (actions.get("Mu_star") or actions.get("Vu_star")):
            actions_table_data = []
            if "Mu_star" in actions and actions.get("Mu_star"):
                actions_table_data.append(["Bending moment (Mu*)", f"{actions.get('Mu_star', 'N/A'):.2f} kNm"])
            if "Vu_star" in actions and actions.get("Vu_star"):
                actions_table_data.append(["Shear force (Vu*)", f"{actions.get('Vu_star', 'N/A'):.2f} kN"])
            
            if actions_table_data:
                actions_table = Table(actions_table_data, colWidths=[2.5*inch, 3*inch])
                actions_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(Paragraph("<b>Design Actions</b>", subheading_style))
                story.append(actions_table)
                story.append(Spacer(1, 0.15*inch))
        
        # Figures section (section/reinforcement layout)
        story.append(Paragraph("<b>Figures</b>", subheading_style))
        story.append(Spacer(1, 0.1*inch))
        
        # Try to generate and export section/reinforcement figure
        try:
            from inputs_page import make_summary_cross_section_figure
            import tempfile
            
            fig = make_summary_cross_section_figure()
            if fig and hasattr(fig, 'write_image'):
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                    fig_path = tmp_file.name
                    if temp_figures is not None:
                        temp_figures.append(fig_path)
                    # Export Plotly figure to PNG
                    try:
                        fig.write_image(fig_path, width=600, height=400, scale=2)
                        if os.path.exists(fig_path):
                            img = Image(fig_path, width=5*inch, height=3.33*inch)
                            story.append(img)
                            story.append(Paragraph("Cross-section and reinforcement layout", ParagraphStyle(
                                'FigCaption',
                                parent=styles['Normal'],
                                fontSize=8,
                                textColor=colors.grey,
                                alignment=TA_CENTER,
                                spaceBefore=2,
                                spaceAfter=0.1*inch,
                            )))
                    except Exception:
                        # Skip if export fails (kaleido might not be available)
                        pass
        except Exception:
            # Skip if figure generation fails
            pass
        
        story.append(PageBreak())
    
    # Design Checks Sections
    if check_sections:
        story.append(Paragraph("Design Checks", heading_style))
        story.append(Spacer(1, 0.1*inch))
        
        for check_idx, check in enumerate(check_sections):
            # Add PageBreak before Shear section (but not before the first check)
            check_title = check.get("title", "").lower()
            if "shear" in check_title and check_idx > 0:
                story.append(PageBreak())
            
            # Check if this section has groups (unified), tabs (legacy), or steps (legacy fallback)
            groups = check.get("groups")
            tabs = check.get("tabs", [])
            steps = check.get("steps", [])
            
            if groups:
                # Use unified groups format (preferred)
                module_title = check.get("title", "Check")
                summary = check.get("summary", [])
                _render_tabs_and_boxes(story, styles, module_title, summary, tabs=None, groups=groups)
            elif tabs:
                # Use legacy tabs format
                module_title = check.get("title", "Check")
                summary = check.get("summary", [])
                _render_tabs_and_boxes(story, styles, module_title, summary, tabs=tabs, groups=None)
            else:
                # Legacy: render steps
                story.append(Paragraph(f"<b>{check.get('title', 'Check')}</b>", subheading_style))
                
                # Summary (2-line format)
                summary = check.get("summary", [])
                if isinstance(summary, list):
                    # Format as list of tuples: [("Label", "Value"), ...]
                    summary_text = ", ".join([f"{label}: {value}" for label, value in summary])
                elif isinstance(summary, dict):
                    # Format as dict
                    summary_text = (
                        f"Demand: {summary.get('demand', 'N/A')}, "
                        f"Capacity: {summary.get('capacity', 'N/A')}, "
                        f"Utilisation: {summary.get('utilisation', 'N/A')}, "
                        f"Outcome: {summary.get('status', 'N/A')}"
                    )
                else:
                    summary_text = str(summary)
                
                story.append(Paragraph(summary_text, styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
                
                # Steps
                _render_steps(story, styles, steps)
            
            # Figures (rendered for both tabs and steps)
            figures = check.get("figures", [])
            if figures:
                story.append(Spacer(1, 0.1*inch))
                story.append(Paragraph("<b>Figures:</b>", styles['Normal']))
                for fig_path in figures:
                    if fig_path and os.path.exists(fig_path):
                        try:
                            img = Image(fig_path, width=5*inch, height=3*inch)
                            story.append(img)
                            story.append(Spacer(1, 0.1*inch))
                        except Exception:
                            # Skip figure if it can't be loaded
                            pass
            
            story.append(Spacer(1, 0.2*inch))
    
    # Build PDF with header/footer on every page
    doc.build(
        story,
        onFirstPage=lambda c, d: draw_header_footer(c, d, meta),
        onLaterPages=lambda c, d: draw_header_footer(c, d, meta),
    )
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
