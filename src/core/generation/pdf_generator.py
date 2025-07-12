#!/usr/bin/env python3
"""
PDF generator that creates labels with the same formatting as DOCX output.
This module replicates the DOCX template processing for PDF generation.
"""

import logging
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import math
from typing import Dict, Any, List
from copy import deepcopy

# Local imports
from src.core.utils.common import safe_get, calculate_text_complexity
from src.core.generation.unified_font_sizing import get_font_size
from src.core.formatting.markers import unwrap_marker, FIELD_MARKERS

logger = logging.getLogger(__name__)

def unwrap_any_marker(text):
    """Remove any marker wrappers from text."""
    if not isinstance(text, str):
        return text
    
    # Try to unwrap with each known marker
    for marker in FIELD_MARKERS.keys():
        try:
            unwrapped = unwrap_marker(text, marker)
            if unwrapped != text:  # If unwrapping happened
                return unwrapped
        except:
            continue
    
    return text

# Color mapping for lineage (matching DOCX colors)
LINEAGE_COLORS = {
    'SATIVA': HexColor('#ED4123'),
    'INDICA': HexColor('#9900FF'),
    'HYBRID': HexColor('#009900'),
    'HYBRID_INDICA': HexColor('#9900FF'),
    'HYBRID_SATIVA': HexColor('#ED4123'),
    'CBD': HexColor('#F1C232'),
    'MIXED': HexColor('#0021F5'),
    'PARA': HexColor('#FFC0CB')
}

class PDFGenerator:
    """Generates PDF labels with the same formatting as DOCX output."""
    
    def __init__(self, template_type: str, scale_factor: float = 1.0):
        self.template_type = template_type
        self.scale_factor = scale_factor
        self.logger = logging.getLogger(__name__)
        
        # Page size and margins
        self.page_width, self.page_height = letter
        self.margin = 0.5 * inch
        
        # Cell dimensions based on template type
        self.cell_dimensions = self._get_cell_dimensions()
        
        # Styles
        self.styles = self._create_styles()
    
    def _get_cell_dimensions(self) -> Dict[str, float]:
        """Get cell dimensions based on template type."""
        if self.template_type == 'mini':
            # 4x5 grid for mini template
            cols, rows = 4, 5
            cell_width = (self.page_width - 2 * self.margin) / cols
            cell_height = (self.page_height - 2 * self.margin) / rows
        else:
            # 3x3 grid for horizontal/vertical templates
            cols, rows = 3, 3
            cell_width = (self.page_width - 2 * self.margin) / cols
            cell_height = (self.page_height - 2 * self.margin) / rows
        
        return {
            'width': cell_width,
            'height': cell_height,
            'cols': cols,
            'rows': rows
        }
    
    def _create_styles(self) -> Dict[str, ParagraphStyle]:
        """Create paragraph styles for different field types."""
        styles = getSampleStyleSheet()
        
        # Base style
        base_style = ParagraphStyle(
            'Base',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            spaceAfter=0,
            spaceBefore=0,
            leading=12
        )
        
        # Field-specific styles
        field_styles = {
            'description': ParagraphStyle(
                'Description',
                parent=base_style,
                fontSize=12,
                alignment=TA_CENTER
            ),
            'brand': ParagraphStyle(
                'Brand',
                parent=base_style,
                fontSize=14,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            ),
            'price': ParagraphStyle(
                'Price',
                parent=base_style,
                fontSize=16,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            ),
            'lineage': ParagraphStyle(
                'Lineage',
                parent=base_style,
                fontSize=10,
                alignment=TA_CENTER
            ),
            'ratio': ParagraphStyle(
                'Ratio',
                parent=base_style,
                fontSize=10,
                alignment=TA_CENTER
            ),
            'thc_cbd': ParagraphStyle(
                'THC_CBD',
                parent=base_style,
                fontSize=10,
                alignment=TA_CENTER
            ),
            'strain': ParagraphStyle(
                'Strain',
                parent=base_style,
                fontSize=11,
                alignment=TA_CENTER
            ),
            'weight': ParagraphStyle(
                'Weight',
                parent=base_style,
                fontSize=10,
                alignment=TA_CENTER
            ),
            'doh': ParagraphStyle(
                'DOH',
                parent=base_style,
                fontSize=10,
                alignment=TA_CENTER
            )
        }
        
        return field_styles
    
    def _get_field_style(self, field_type: str, text: str) -> ParagraphStyle:
        """Get appropriate style for a field with dynamic font sizing."""
        base_style = self.styles.get(field_type, self.styles['description'])
        
        # Calculate font size using the same logic as DOCX
        font_size_pt = get_font_size(text, field_type, self.template_type, self.scale_factor)
        
        # Create a copy of the style with the calculated font size
        style = ParagraphStyle(
            f'{field_type}_dynamic',
            parent=base_style,
            fontSize=font_size_pt.pt
        )
        
        return style
    
    def _create_label_content(self, record: Dict[str, Any]) -> List[Paragraph]:
        """Create the content for a single label."""
        content = []
        
        # Process each field type - using the actual field names from get_selected_records
        field_mappings = {
            'description': record.get('Description', ''),
            'brand': record.get('ProductBrand', ''),
            'price': record.get('Price', ''),
            'lineage': record.get('Lineage', ''),
            'ratio': record.get('Ratio_or_THC_CBD', ''),
            'thc_cbd': record.get('Ratio_or_THC_CBD', ''),  # Use same field as ratio
            'strain': record.get('ProductStrain', ''),
            'weight': record.get('WeightUnits', ''),
            'doh': record.get('DOH', '')
        }
        
        for field_type, value in field_mappings.items():
            if value:
                # Remove marker wrappers if present
                clean_text = unwrap_any_marker(str(value))
                if clean_text.strip():
                    style = self._get_field_style(field_type, clean_text)
                    content.append(Paragraph(clean_text, style))
                    content.append(Spacer(1, 2))
        
        # Add weight information to description if available
        weight = field_mappings.get('weight', '')
        if weight and field_mappings.get('description'):
            desc_text = field_mappings['description']
            if weight not in desc_text:
                combined_text = f"{desc_text} - {weight}"
                style = self._get_field_style('description', combined_text)
                # Replace the description paragraph
                if content:
                    content[0] = Paragraph(combined_text, style)
        
        return content
    
    def _get_lineage_color(self, record: Dict[str, Any]) -> HexColor:
        """Get lineage color for a record."""
        lineage = str(record.get('Lineage', '')).upper()
        
        # Remove marker wrappers if present
        lineage = unwrap_any_marker(lineage)
        
        # Map lineage to color
        for key, color in LINEAGE_COLORS.items():
            if key in lineage:
                return color
        
        return LINEAGE_COLORS.get('MIXED', HexColor('#0021F5'))
    
    def _create_label_cell(self, record: Dict[str, Any]) -> Table:
        """Create a single label cell."""
        content = self._create_label_content(record)
        
        # Create table with single cell
        cell_data = [[content]]
        table = Table(cell_data, colWidths=[self.cell_dimensions['width']], 
                     rowHeights=[self.cell_dimensions['height']])
        
        # Apply styling
        lineage_color = self._get_lineage_color(record)
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, -1), lineage_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        
        return table
    
    def generate_pdf(self, records: List[Dict[str, Any]]) -> BytesIO:
        """Generate PDF with labels."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                              leftMargin=self.margin, rightMargin=self.margin,
                              topMargin=self.margin, bottomMargin=self.margin)
        
        # Group records into pages
        labels_per_page = self.cell_dimensions['cols'] * self.cell_dimensions['rows']
        pages = [records[i:i + labels_per_page] for i in range(0, len(records), labels_per_page)]
        
        story = []
        
        for page_records in pages:
            # Create grid for this page
            grid_data = []
            for row in range(self.cell_dimensions['rows']):
                grid_row = []
                for col in range(self.cell_dimensions['cols']):
                    idx = row * self.cell_dimensions['cols'] + col
                    if idx < len(page_records):
                        # Create label cell
                        label_cell = self._create_label_cell(page_records[idx])
                        grid_row.append(label_cell)
                    else:
                        # Empty cell
                        grid_row.append('')
                grid_data.append(grid_row)
            
            # Create page table
            page_table = Table(grid_data, 
                             colWidths=[self.cell_dimensions['width']] * self.cell_dimensions['cols'],
                             rowHeights=[self.cell_dimensions['height']] * self.cell_dimensions['rows'])
            
            # Apply page styling with exact row heights
            page_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                # Ensure exact row heights are enforced
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white] * self.cell_dimensions['rows']),
            ]))
            
            # Final enforcement: ensure table uses exact dimensions
            page_table._argW = [self.cell_dimensions['width']] * self.cell_dimensions['cols']
            page_table._argH = [self.cell_dimensions['height']] * self.cell_dimensions['rows']
            
            story.append(page_table)
            story.append(Spacer(1, 20))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer

def generate_pdf_labels(records: List[Dict[str, Any]], template_type: str = 'horizontal', 
                       scale_factor: float = 1.0) -> BytesIO:
    """Convenience function to generate PDF labels."""
    generator = PDFGenerator(template_type, scale_factor)
    return generator.generate_pdf(records) 