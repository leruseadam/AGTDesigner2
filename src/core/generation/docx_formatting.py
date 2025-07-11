from docx.shared import Pt, Inches, RGBColor
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
import logging

logger = logging.getLogger(__name__)

# Define colors for lineage
COLORS = {
    'SATIVA': 'ED4123',
    'INDICA': '9900FF',
    'HYBRID': '009900',
    'HYBRID_INDICA': '9900FF',
    'HYBRID_SATIVA': 'ED4123',
    'CBD': 'F1C232',
    'MIXED': '0021F5',
    'PARA': 'FFC0CB'
}

def apply_lineage_colors(doc, cell_record_map=None):
    """Apply lineage colors to all cells based on keywords in cell text, Product Strain marker/value, or record lineage if provided."""
    try:
        for t_idx, table in enumerate(doc.tables):
            for i, row in enumerate(table.rows):
                for j, cell in enumerate(row.cells):
                    text = cell.text.upper()
                    color_hex = None

                    # If mapping is provided, use record's lineage
                    record = None
                    lineage = ''
                    if cell_record_map and (i, j) in cell_record_map:
                        record = cell_record_map[(i, j)]
                        lineage = str(record.get('Lineage', '')).upper()
                        # Remove marker wrappers if present
                        for marker in ["LINEAGE_START", "LINEAGE_END"]:
                            lineage = lineage.replace(marker, "")
                        lineage = lineage.strip()
                        # Map lineage to color
                        if "PARAPHERNALIA" in lineage:
                            color_hex = COLORS['PARA']
                        elif "HYBRID/INDICA" in lineage or "HYBRID INDICA" in lineage:
                            color_hex = COLORS['HYBRID_INDICA']
                        elif "HYBRID/SATIVA" in lineage or "HYBRID SATIVA" in lineage:
                            color_hex = COLORS['HYBRID_SATIVA']
                        elif "SATIVA" in lineage:
                            color_hex = COLORS['SATIVA']
                        elif "INDICA" in lineage:
                            color_hex = COLORS['INDICA']
                        elif "HYBRID" in lineage:
                            color_hex = COLORS['HYBRID']
                        elif "CBD" in lineage or "CBD_BLEND" in lineage:
                            color_hex = COLORS['CBD']
                        elif "MIXED" in lineage:
                            color_hex = COLORS['MIXED']
                        # --- NEW: If no lineage but ProductStrain is present, infer lineage from ProductStrain ---
                        if not color_hex and record.get('ProductStrain', ''):
                            product_strain = str(record.get('ProductStrain', '')).upper()
                            if "SATIVA" in product_strain:
                                color_hex = COLORS['SATIVA']
                            elif "INDICA" in product_strain:
                                color_hex = COLORS['INDICA']
                            elif "HYBRID/INDICA" in product_strain or "HYBRID INDICA" in product_strain:
                                color_hex = COLORS['HYBRID_INDICA']
                            elif "HYBRID/SATIVA" in product_strain or "HYBRID SATIVA" in product_strain:
                                color_hex = COLORS['HYBRID_SATIVA']
                            elif "HYBRID" in product_strain:
                                color_hex = COLORS['HYBRID']
                            elif "CBD" in product_strain:
                                color_hex = COLORS['CBD']
                            elif "MIXED" in product_strain:
                                color_hex = COLORS['MIXED']
                            elif "PARA" in product_strain or "PARAPHERNALIA" in product_strain:
                                color_hex = COLORS['PARA']
                    # Fallback to old logic if not found
                    if not color_hex:
                        # Remove marker wrappers for robust matching
                        for marker in ["LINEAGE_START", "LINEAGE_END"]:
                            text = text.replace(marker, "")
                        text = text.strip()
                        # Try to extract Product Strain marker/value if present
                        product_strain = None
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                if "PRODUCTSTRAIN_START" in run.text and "PRODUCTSTRAIN_END" in run.text:
                                    # Extract value between markers
                                    start = run.text.find("PRODUCTSTRAIN_START") + len("PRODUCTSTRAIN_START")
                                    end = run.text.find("PRODUCTSTRAIN_END")
                                    product_strain = run.text[start:end].strip().upper()
                                elif "PRODUCTSTRAIN_START" in run.text:
                                    # Multi-run marker, try to reconstruct
                                    collecting = False
                                    value = ""
                                    for r in paragraph.runs:
                                        if "PRODUCTSTRAIN_START" in r.text:
                                            collecting = True
                                            value += r.text.split("PRODUCTSTRAIN_START")[-1]
                                        elif "PRODUCTSTRAIN_END" in r.text:
                                            value += r.text.split("PRODUCTSTRAIN_END")[0]
                                            collecting = False
                                            break
                                        elif collecting:
                                            value += r.text
                                    if value:
                                        product_strain = value.strip().upper()
                        # If we found a Product Strain, try to infer lineage from it
                        if product_strain:
                            if "SATIVA" in product_strain:
                                color_hex = COLORS['SATIVA']
                            elif "INDICA" in product_strain:
                                color_hex = COLORS['INDICA']
                            elif "HYBRID/INDICA" in product_strain or "HYBRID INDICA" in product_strain:
                                color_hex = COLORS['HYBRID_INDICA']
                            elif "HYBRID/SATIVA" in product_strain or "HYBRID SATIVA" in product_strain:
                                color_hex = COLORS['HYBRID_SATIVA']
                            elif "HYBRID" in product_strain:
                                color_hex = COLORS['HYBRID']
                            elif "CBD" in product_strain:
                                color_hex = COLORS['CBD']
                            elif "MIXED" in product_strain:
                                color_hex = COLORS['MIXED']
                            elif "PARA" in product_strain or "PARAPHERNALIA" in product_strain:
                                color_hex = COLORS['PARA']
                        # Fallback to old logic if not found
                        if not color_hex:
                            if "_PRODUCT_TYPE_" in text:
                                lineage_part = text.split("_PRODUCT_TYPE_")[0]
                                text = lineage_part
                            if "PARAPHERNALIA" in text:
                                color_hex = COLORS['PARA']
                            elif "HYBRID/INDICA" in text or "HYBRID INDICA" in text:
                                color_hex = COLORS['HYBRID_INDICA']
                            elif "HYBRID/SATIVA" in text or "HYBRID SATIVA" in text:
                                color_hex = COLORS['HYBRID_SATIVA']
                            elif "SATIVA" in text:
                                color_hex = COLORS['SATIVA']
                            elif "INDICA" in text:
                                color_hex = COLORS['INDICA']
                            elif "HYBRID" in text:
                                color_hex = COLORS['HYBRID']
                            elif "CBD" in text or "CBD_BLEND" in text:
                                color_hex = COLORS['CBD']
                            elif "MIXED" in text:
                                color_hex = COLORS['MIXED']
                    if color_hex:
                        # Set cell background color
                        tc = cell._tc
                        tcPr = tc.get_or_add_tcPr()
                        for old_shd in tcPr.findall(qn('w:shd')):
                            tcPr.remove(old_shd)
                        shd = OxmlElement('w:shd')
                        shd.set(qn('w:fill'), color_hex)
                        shd.set(qn('w:val'), 'clear')
                        shd.set(qn('w:color'), 'auto')
                        tcPr.append(shd)
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                run.font.color.rgb = RGBColor(255, 255, 255)
                                run.font.bold = True
                                run.font.name = "Arial"
        logger.debug("Applied lineage colors to document")
        return doc
    except Exception as e:
        logger.error(f"Error applying lineage colors: {str(e)}")
        raise

def fix_table_row_heights(doc, template_type):
    """Fix table row heights based on template type."""
    try:
        row_height = {
            'horizontal': 2.25,
            'vertical': 3.3,
            'mini': 1.75,
            'inventory': 2.0
        }.get(template_type, 2.4)
        for table in doc.tables:
            for row in table.rows:
                row.height = Inches(row_height)
                row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
        logger.debug(f"Fixed table row heights for template type: {template_type}")
        return doc
    except Exception as e:
        logger.error(f"Error fixing table row heights: {str(e)}")
        raise

def safe_fix_paragraph_spacing(doc):
    """
    Safely adjust paragraph spacing in document without affecting cell colors.
    """
    try:
        for paragraph in doc.paragraphs:
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.0
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.space_before = Pt(0)
                        paragraph.paragraph_format.space_after = Pt(0)
                        paragraph.paragraph_format.line_spacing = 1.0
        logger.debug("Successfully fixed paragraph spacing")
    except Exception as e:
        logger.error(f"Error in safe_fix_paragraph_spacing: {str(e)}")
        raise

def apply_conditional_formatting(doc, conditions=None):
    """
    Apply conditional formatting to document elements based on specified conditions.
    """
    try:
        if not conditions:
            conditions = {
                'PRICE_START': {
                    'bold': True,
                    'color': RGBColor(0, 0, 0),
                    'size': Pt(12)
                },
                'LINEAGE_START': {
                    'bold': True,
                    'color': RGBColor(255, 255, 255),
                    'size': Pt(11)
                }
            }
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            for marker, formatting in conditions.items():
                                if marker in run.text:
                                    if formatting.get('bold') is not None:
                                        run.font.bold = formatting['bold']
                                    if formatting.get('color') is not None:
                                        run.font.color.rgb = formatting['color']
                                    if formatting.get('size') is not None:
                                        run.font.size = formatting['size']
        logger.debug("Applied conditional formatting to document")
        return doc
    except Exception as e:
        logger.error(f"Error applying conditional formatting: {str(e)}")
        raise

def set_cell_background(cell, color_hex):
    """Set cell background color with white text."""
    try:
        color_hex = color_hex.upper().strip('#')
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        for element in tcPr.findall(qn('w:shd')):
            tcPr.remove(element)
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), color_hex)
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:themeFill'), '0')
        tcPr.append(shd)
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.bold = True
                run.font.name = "Arial"
        return
    except Exception as e:
        logger.error(f"Error in set_cell_background: {str(e)}")
        raise

def clear_cell_margins(cell):
    """Remove cell margins."""
    try:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for side in ['top', 'right', 'bottom', 'left']:
            margin = OxmlElement(f'w:{side}')
            margin.set(qn('w:w'), '0')
            margin.set(qn('w:type'), 'dxa')
            tcMar.append(margin)
        for element in tcPr.findall(qn('w:tcMar')):
            tcPr.remove(element)
        tcPr.append(tcMar)
    except Exception as e:
        logger.error(f"Error in clear_cell_margins: {str(e)}")
        raise

def clear_table_cell_padding(cell):
    """Clear padding from a table cell."""
    try:
        if not cell or not hasattr(cell, '_tc'):
            return
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for side in ['top', 'left', 'bottom', 'right']:
            margin = OxmlElement(f'w:{side}')
            margin.set(qn('w:w'), '0')
            margin.set(qn('w:type'), 'dxa')
            tcMar.append(margin)
        for old_mar in tcPr.findall(qn('w:tcMar')):
            tcPr.remove(old_mar)
        tcPr.append(tcMar)
        logger.debug(f"Cleared padding for cell")
    except Exception as e:
        logger.error(f"Error in clear_table_cell_padding: {str(e)}")
        raise

def enforce_ratio_formatting(doc):
    """Enforce Arial Bold and consistent font size for ratio-related content."""
    from docx.shared import Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    
    ratio_patterns = [
        'THC:', 'CBD:', 
        '100mg', '500mg',
        '1:1:1', '1:1',
        'CBC/CBG',
        'RATIO_START',
        'THC_CBD_START'
    ]

    def process_paragraph(paragraph):
        if any(pattern in paragraph.text for pattern in ratio_patterns):
            # Store text content
            text = paragraph.text
            
            # Clear paragraph
            paragraph.clear()
            
            # Add new run with proper formatting
            run = paragraph.add_run(text)
            run.font.name = "Arial"
            run.font.bold = True
            
            # Set font properties at XML level
            rPr = run._element.get_or_add_rPr()
            
            # Force Arial font
            rFonts = OxmlElement('w:rFonts')
            rFonts.set(qn('w:ascii'), 'Arial')
            rFonts.set(qn('w:hAnsi'), 'Arial')
            rFonts.set(qn('w:eastAsia'), 'Arial')
            rFonts.set(qn('w:cs'), 'Arial')
            rPr.append(rFonts)
            
            # Force bold
            b = OxmlElement('w:b')
            b.set(qn('w:val'), '1')
            rPr.append(b)
            
            # Set font size (18pt)
            sz = OxmlElement('w:sz')
            sz.set(qn('w:val'), str(int(18 * 2)))  # Word uses half-points
            rPr.append(sz)
            
            # Set at Python level too
            run.font.size = Pt(18)

    # Process all tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    process_paragraph(paragraph)

    # Process all paragraphs outside tables
    for paragraph in doc.paragraphs:
        process_paragraph(paragraph)

    return doc

def enforce_arial_bold_all_text(doc):
    """Enforce Arial Bold font for all text in the document."""
    from docx.shared import Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    def process_run(run):
        """Apply Arial Bold formatting to a single run."""
        # Set font properties at Python level
        run.font.name = "Arial"
        run.font.bold = True
        
        # Force Arial at XML level for maximum compatibility
        rPr = run._element.get_or_add_rPr()
        
        # Set font family
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:ascii'), 'Arial')
        rFonts.set(qn('w:hAnsi'), 'Arial')
        rFonts.set(qn('w:eastAsia'), 'Arial')
        rFonts.set(qn('w:cs'), 'Arial')
        rPr.append(rFonts)
        
        # Force bold
        b = OxmlElement('w:b')
        b.set(qn('w:val'), '1')
        rPr.append(b)

    # Process all tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        process_run(run)

    # Process all paragraphs outside tables
    for paragraph in doc.paragraphs:
        for run in paragraph.runs:
            process_run(run)

    return doc

def cleanup_all_price_markers(doc):
    """Remove all price markers while preserving formatting."""
    price_patterns = [
        'PRICE_START',
        'PRICE_END',
        '{{PRICE}}',
        '{{/PRICE}}'
    ]
    
    def process_paragraph(paragraph):
        # Store original text and check if it contains price markers
        text = paragraph.text
        if not any(pattern in text for pattern in price_patterns):
            return
        
        # Remove all price markers
        for pattern in price_patterns:
            text = text.replace(pattern, '')
        
        # Clear paragraph and add cleaned text
        paragraph.clear()
        if text.strip():
            run = paragraph.add_run(text.strip())
            # Apply price formatting
            run.font.name = 'Arial'
            run.font.bold = True
            run.font.size = Pt(14)  # Standard price font size

    # Process all tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    process_paragraph(paragraph)

    # Process all paragraphs outside tables
    for paragraph in doc.paragraphs:
        process_paragraph(paragraph)

    return doc

def remove_extra_spacing(doc):
    """Remove extra spacing between paragraphs and set consistent line spacing."""
    from docx.shared import Pt
    
    def process_paragraph(paragraph):
        # Store text content
        if not paragraph.text.strip():
            return
            
        text = paragraph.text
        
        # Clear and reset paragraph
        paragraph.clear()
        run = paragraph.add_run(text)
        
        # Set consistent font
        run.font.name = "Arial"
        run.font.bold = True
        
        # Set paragraph spacing to minimum to prevent cell expansion
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1.0
        
        # Special handling for ratio content
        if any(marker in text for marker in ['THC:', 'CBD:', 'RATIO_START', 'THC_CBD_START']):
            paragraph.paragraph_format.line_spacing = 1.75

    # Process all tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    process_paragraph(paragraph)

    # Process all paragraphs outside tables
    for paragraph in doc.paragraphs:
        process_paragraph(paragraph)

    return doc

def apply_type_formatting(doc, product_type, template_type='vertical'):
    """Apply specific formatting based on product type."""
    def process_paragraph(paragraph):
        # Skip empty paragraphs
        if not paragraph.text.strip():
            return
            
        # Apply type-specific formatting
        if product_type.lower() == 'paraphernalia':
            # Make paraphernalia text smaller and less prominent
            for run in paragraph.runs:
                if run.font.size:
                    current_size = run.font.size.pt
                    run.font.size = Pt(max(6, current_size * 0.8))  # Reduce size by 20%
                run.font.color.rgb = RGBColor(128, 128, 128)  # Gray color
        elif product_type.lower() in ['concentrate', 'wax', 'shatter', 'rosin']:
            # Make concentrate text bold and prominent
            for run in paragraph.runs:
                run.font.bold = True
                if run.font.size:
                    current_size = run.font.size.pt
                    run.font.size = Pt(min(24, current_size * 1.1))  # Increase size by 10%

    # Process all tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    process_paragraph(paragraph)

    # Process all paragraphs outside tables
    for paragraph in doc.paragraphs:
        process_paragraph(paragraph)

    return doc

def create_3x3_grid(doc, template_type='vertical'):
    """Create a 3x3 grid table for label layout."""
    try:
        # Remove existing tables
        for table in doc.tables:
            table._element.getparent().remove(table._element)
        
        # Remove default paragraph if it exists
        if doc.paragraphs:
            p = doc.paragraphs[0]
            p._element.getparent().remove(p._element)
        
        # Create new table
        table = doc.add_table(rows=3, cols=3)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # Set table properties
        tblPr = table._element.find(qn('w:tblPr'))
        if tblPr is None:
            tblPr = OxmlElement('w:tblPr')
        tblLayout = OxmlElement('w:tblLayout')
        tblLayout.set(qn('w:type'), 'fixed')
        tblPr.append(tblLayout)
        table._element.insert(0, tblPr)
        
        # Set column widths
        col_width = Inches(3.3 / 3)  # 3.5 inches divided by 3 columns
        tblGrid = OxmlElement('w:tblGrid')
        for _ in range(3):
            gridCol = OxmlElement('w:gridCol')
            gridCol.set(qn('w:w'), str(int(col_width.inches * 1440)))  # Convert to twips
            tblGrid.append(gridCol)
        table._element.insert(0, tblGrid)
        
        # Set row heights
        row_height = Inches(2.25)  
        for row in table.rows:
            row.height = row_height
            row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
        
        # Enforce fixed cell dimensions to prevent any growth
        enforce_fixed_cell_dimensions(table)
        
        logger.debug("Created 3x3 grid table")
        return table
    except Exception as e:
        logger.error(f"Error creating 3x3 grid: {str(e)}")
        raise

def disable_autofit(table):
    """Disable autofit for a table."""
    try:
        tblPr = table._element.find(qn('w:tblPr'))
        if tblPr is None:
            tblPr = OxmlElement('w:tblPr')
        tblLayout = OxmlElement('w:tblLayout')
        tblLayout.set(qn('w:type'), 'fixed')
        tblPr.append(tblLayout)
        table._element.insert(0, tblPr)
        logger.debug("Disabled autofit for table")
    except Exception as e:
        logger.error(f"Error disabling autofit: {str(e)}")
        raise

def enforce_fixed_cell_dimensions(table):
    """Enforce fixed cell dimensions to prevent any cell growth with text."""
    try:
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
        
        # Disable autofit
        disable_autofit(table)
        
        # Set table properties to prevent any auto-sizing
        tblPr = table._element.find(qn('w:tblPr'))
        if tblPr is None:
            tblPr = OxmlElement('w:tblPr')
        
        # Ensure fixed layout
        tblLayout = OxmlElement('w:tblLayout')
        tblLayout.set(qn('w:type'), 'fixed')
        tblPr.append(tblLayout)
        
        # Set table to not auto-fit
        table.autofit = False
        if hasattr(table, 'allow_autofit'):
            table.allow_autofit = False
        
        # Process each cell to enforce fixed dimensions
        for row in table.rows:
            # Set exact row height rule
            row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
            
            for cell in row.cells:
                # Set cell vertical alignment to top to prevent content from expanding cell
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                
                # Clear any cell margins that might allow expansion
                clear_cell_margins(cell)
                
                # Process paragraphs in the cell to prevent text overflow
                for paragraph in cell.paragraphs:
                    # Set paragraph spacing to minimum
                    paragraph.paragraph_format.space_before = Pt(0)
                    paragraph.paragraph_format.space_after = Pt(0)
                    paragraph.paragraph_format.line_spacing = 1.0
                    
                    # Ensure text doesn't wrap beyond cell boundaries
                    for run in paragraph.runs:
                        # Set font properties to prevent text expansion
                        if not run.font.size:
                            run.font.size = Pt(12)  # Set default size if none
        
        logger.debug("Enforced fixed cell dimensions for table")
        return table
    except Exception as e:
        logger.error(f"Error enforcing fixed cell dimensions: {str(e)}")
        raise

def fix_table(doc, num_rows=3, num_cols=3, cell_width=Inches(3.3/3), cell_height=Inches(2.25)):
    # Remove all existing tables
    for table in doc.tables:
        table._element.getparent().remove(table._element)
    
    # Remove default paragraph if it exists
    if doc.paragraphs:
        p = doc.paragraphs[0]
        p._element.getparent().remove(p._element)
    
    # Create new table
    table = doc.add_table(rows=num_rows, cols=num_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Set table properties
    tblPr = table._element.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
    tblLayout = OxmlElement('w:tblLayout')
    tblLayout.set(qn('w:type'), 'fixed')
    tblPr.append(tblLayout)
    table._element.insert(0, tblPr)
    
    # Set column widths
    tblGrid = OxmlElement('w:tblGrid')
    for _ in range(num_cols):
        gridCol = OxmlElement('w:gridCol')
        gridCol.set(qn('w:w'), str(int(cell_width.inches * 1440)))
        tblGrid.append(gridCol)
    table._element.insert(0, tblGrid)
    
    # Set row heights
    for row in table.rows:
        row.height = cell_height
        row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    
    # Enforce fixed cell dimensions to prevent any growth
    enforce_fixed_cell_dimensions(table)
    
    return table

def rebuild_3x3_grid(doc, cell_width=Inches(3.3/3), cell_height=Inches(2.25)):
    # Remove all existing tables
    for table in doc.tables:
        table._element.getparent().remove(table._element)
    
    # Remove default paragraph if it exists
    if doc.paragraphs:
        p = doc.paragraphs[0]
        p._element.getparent().remove(p._element)
    
    # Create new 3x3 table
    table = doc.add_table(rows=3, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Set table properties
    tblPr = table._element.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
    tblLayout = OxmlElement('w:tblLayout')
    tblLayout.set(qn('w:type'), 'fixed')
    tblPr.append(tblLayout)
    table._element.insert(0, tblPr)
    
    # Set column widths
    tblGrid = OxmlElement('w:tblGrid')
    for _ in range(3):
        gridCol = OxmlElement('w:gridCol')
        gridCol.set(qn('w:w'), str(int(cell_width.inches * 1440)))
        tblGrid.append(gridCol)
    table._element.insert(0, tblGrid)
    
    # Set row heights
    for row in table.rows:
        row.height = cell_height
        row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    
    # Enforce fixed cell dimensions to prevent any growth
    enforce_fixed_cell_dimensions(table)
    
    return table 