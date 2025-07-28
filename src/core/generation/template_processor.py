from copy import deepcopy
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, Mm, RGBColor
from docxtpl import DocxTemplate, InlineImage
from docxcompose.composer import Composer
from io import BytesIO
import logging
import os
from pathlib import Path
import re
from typing import Dict, Any, List, Optional
import traceback
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.section import WD_SECTION
from docx.oxml.shared import OxmlElement, qn
import time

# Local imports
from src.core.utils.common import safe_get
from src.core.generation.docx_formatting import (
    apply_lineage_colors,
    enforce_fixed_cell_dimensions,
    clear_cell_background,
    clear_cell_margins,
    clear_table_cell_padding,
)
from src.core.generation.unified_font_sizing import (
    get_font_size,
    get_font_size_by_marker,
    set_run_font_size,
    is_classic_type,
    get_line_spacing_by_marker
)
from src.core.generation.text_processing import (
    process_doh_image,
    format_ratio_multiline
)
from src.core.formatting.markers import wrap_with_marker, unwrap_marker, is_already_wrapped

# Performance settings
MAX_PROCESSING_TIME_PER_CHUNK = 30  # 30 seconds max per chunk
MAX_TOTAL_PROCESSING_TIME = 300     # 5 minutes max total
CHUNK_SIZE_LIMIT = 50               # Limit chunk size for performance

def get_font_scheme(template_type, base_size=12):
    schemes = {
        'default': {"base_size": base_size, "min_size": 8, "max_length": 25},
        'vertical': {"base_size": base_size, "min_size": 8, "max_length": 25},
        'mini': {"base_size": base_size - 2, "min_size": 6, "max_length": 15},
        'horizontal': {"base_size": base_size + 1, "min_size": 7, "max_length": 20},
        'double': {"base_size": base_size - 1, "min_size": 8, "max_length": 30}
    }
    return {
        field: {**schemes.get(template_type, schemes['default'])}
        for field in ["Description", "ProductBrand", "Price", "Lineage", "DOH", "Ratio_or_THC_CBD", "Ratio"]
    }

class TemplateProcessor:
    def __init__(self, template_type, font_scheme, scale_factor=1.0):
        self.template_type = template_type
        self.font_scheme = font_scheme
        self.scale_factor = scale_factor
        self.logger = logging.getLogger(__name__)
        self._template_path = self._get_template_path()
        self._expanded_template_buffer = self._expand_template_if_needed()
        
        # Set chunk size based on template type with performance limits
        if self.template_type == 'mini':
            self.chunk_size = min(20, CHUNK_SIZE_LIMIT)  # Fixed: 4x5 grid = 20 labels per page
        elif self.template_type == 'double':
            self.chunk_size = min(12, CHUNK_SIZE_LIMIT)  # Fixed: 4x3 grid = 12 labels per page
        else:
            # For standard templates (horizontal, vertical), use 3x3 grid = 9 labels per page
            self.chunk_size = min(9, CHUNK_SIZE_LIMIT)  # Fixed: 3x3 grid = 9 labels per page
        
        self.logger.info(f"Template type: {self.template_type}, Chunk size: {self.chunk_size}")
        
        # Performance tracking
        self.start_time = time.time()
        self.chunk_count = 0

    def _get_template_path(self):
        """Get the template path based on template type."""
        try:
            base_path = Path(__file__).resolve().parent / "templates"
            template_name = f"{self.template_type}.docx"
            template_path = base_path / template_name
            
            if not template_path.exists():
                self.logger.error(f"Template not found: {template_path}")
                raise FileNotFoundError(f"Template not found: {template_path}")
            
            return template_path
        except Exception as e:
            self.logger.error(f"Error getting template path: {e}")
            raise

    def _expand_template_if_needed(self, force_expand=False):
        """Expand template if needed and return buffer."""
        try:
            with open(self._template_path, 'rb') as f:
                buffer = BytesIO(f.read())
            
            # Check if template needs expansion
            doc = Document(buffer)
            text = doc.element.body.xml
            matches = re.findall(r'Label(\d+)\.', text)
            
            # Check if we have all required labels (9 for 3x3, 20 for 4x5, 12 for 4x3)
            required_labels = 9 if self.template_type not in ['mini', 'double'] else (20 if self.template_type == 'mini' else 12)
            unique_labels = set(matches)
            
            if len(unique_labels) < required_labels or force_expand:
                self.logger.info("Template needs expansion")
                if self.template_type == 'mini':
                    return self._expand_template_to_4x5_fixed_scaled()
                elif self.template_type == 'double':
                    return self._expand_template_to_4x3_fixed_double()
                else:
                    return self._expand_template_to_3x3_fixed()
            
            return buffer
        except Exception as e:
            self.logger.error(f"Error expanding template: {e}")
            raise

    def force_re_expand_template(self):
        """Force re-expansion of template."""
        self._expanded_template_buffer = self._expand_template_if_needed(force_expand=True)

    def _expand_template_to_4x5_fixed_scaled(self):
        """Expand template to 4x5 grid for mini templates."""
        from docx import Document
        from docx.shared import Pt
        from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from io import BytesIO
        from copy import deepcopy

        num_cols, num_rows = 4, 5
        col_width_twips = str(int(1.75 * 1440))  # 1.75 inches per column for equal width
        row_height_pts = Pt(2.0 * 72)  # 2.0 inches per row for equal height
        cut_line_twips = int(0.001 * 1440)

        template_path = self._get_template_path()
        doc = Document(template_path)
        if not doc.tables:
            raise RuntimeError("Template must contain at least one table.")
        old = doc.tables[0]
        src_tc = deepcopy(old.cell(0,0)._tc)
        old._element.getparent().remove(old._element)

        while doc.paragraphs and not doc.paragraphs[0].text.strip():
            doc.paragraphs[0]._element.getparent().remove(doc.paragraphs[0]._element)

        tbl = doc.add_table(rows=num_rows, cols=num_cols)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tblPr = tbl._element.find(qn('w:tblPr')) or OxmlElement('w:tblPr')
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'D3D3D3')
        tblPr.insert(0, shd)
        layout = OxmlElement('w:tblLayout')
        layout.set(qn('w:type'), 'fixed')
        tblPr.append(layout)
        tbl._element.insert(0, tblPr)
        grid = OxmlElement('w:tblGrid')
        for _ in range(num_cols):
            gc = OxmlElement('w:gridCol')
            gc.set(qn('w:w'), col_width_twips)
            grid.append(gc)
        tbl._element.insert(0, grid)
        for row in tbl.rows:
            row.height = row_height_pts
            row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
        borders = OxmlElement('w:tblBorders')
        for side in ('insideH','insideV'):
            b = OxmlElement(f"w:{side}")
            b.set(qn('w:val'), "single")
            b.set(qn('w:sz'), "4")
            b.set(qn('w:color'), "D3D3D3")
            b.set(qn('w:space'), "0")
            borders.append(b)
        tblPr.append(borders)
        cnt = 1
        for r in range(num_rows):
            for c in range(num_cols):
                cell = tbl.cell(r,c)
                cell._tc.clear_content()
                tc = deepcopy(src_tc)
                for t in tc.iter(qn('w:t')):
                    if t.text and 'Label1' in t.text:
                        t.text = t.text.replace('Label1', f'Label{cnt}')
                for el in tc.xpath('./*'):
                    cell._tc.append(deepcopy(el))
                cnt += 1
        from docx.oxml.shared import OxmlElement as OE
        tblPr2 = tbl._element.find(qn('w:tblPr'))
        spacing = OxmlElement('w:tblCellSpacing')
        spacing.set(qn('w:w'), str(cut_line_twips))
        spacing.set(qn('w:type'), 'dxa')
        tblPr2.append(spacing)
        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf

    def _expand_template_to_4x3_fixed_double(self):
        """Expand template to 4x3 grid for double templates."""
        from docx import Document
        from docx.shared import Pt
        from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from io import BytesIO
        from copy import deepcopy

        num_cols, num_rows = 4, 3
        col_width_twips = str(int(1.75 * 1440))  # 1.75 inches per column for equal width
        row_height_pts = Pt(2.5 * 72)  # 2.5 inches per row for equal height
        cut_line_twips = int(0.001 * 1440)

        template_path = self._get_template_path()
        doc = Document(template_path)
        if not doc.tables:
            raise RuntimeError("Template must contain at least one table.")
        old = doc.tables[0]
        src_tc = deepcopy(old.cell(0,0)._tc)
        old._element.getparent().remove(old._element)

        while doc.paragraphs and not doc.paragraphs[0].text.strip():
            doc.paragraphs[0]._element.getparent().remove(doc.paragraphs[0]._element)

        tbl = doc.add_table(rows=num_rows, cols=num_cols)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tblPr = tbl._element.find(qn('w:tblPr')) or OxmlElement('w:tblPr')
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'D3D3D3')
        tblPr.insert(0, shd)
        layout = OxmlElement('w:tblLayout')
        layout.set(qn('w:type'), 'fixed')
        tblPr.append(layout)
        tbl._element.insert(0, tblPr)
        grid = OxmlElement('w:tblGrid')
        for _ in range(num_cols):
            gc = OxmlElement('w:gridCol')
            gc.set(qn('w:w'), col_width_twips)
            grid.append(gc)
        tbl._element.insert(0, grid)
        for row in tbl.rows:
            row.height = row_height_pts
            row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
        borders = OxmlElement('w:tblBorders')
        for side in ('insideH','insideV'):
            b = OxmlElement(f"w:{side}")
            b.set(qn('w:val'), "single")
            b.set(qn('w:sz'), "4")
            b.set(qn('w:color'), "D3D3D3")
            b.set(qn('w:space'), "0")
            borders.append(b)
        tblPr.append(borders)
        cnt = 1
        for r in range(num_rows):
            for c in range(num_cols):
                cell = tbl.cell(r,c)
                cell._tc.clear_content()
                tc = deepcopy(src_tc)
                
                # Add ProductBrand placeholder if it doesn't exist
                cell_text = ''
                for t in tc.iter(qn('w:t')):
                    if t.text:
                        cell_text += t.text
                        if 'Label1' in t.text:
                            t.text = t.text.replace('Label1', f'Label{cnt}')
                
                # If ProductBrand placeholder is missing, add it
                if '{{Label1.ProductBrand}}' not in cell_text and 'ProductBrand' not in cell_text:
                    # Add ProductBrand placeholder after Lineage
                    # Since placeholders are split across multiple text elements, we need to find the right position
                    text_elements = list(tc.iter(qn('w:t')))
                    lineage_end_index = -1
                    
                    # Find where the Lineage placeholder ends
                    for i, t in enumerate(text_elements):
                        if t.text and 'Lineage' in t.text:
                            # Found the Lineage text element, look for the closing }}
                            for j in range(i, len(text_elements)):
                                if text_elements[j].text and '}}' in text_elements[j].text:
                                    lineage_end_index = j
                                    break
                            break
                    
                    if lineage_end_index >= 0:
                        # Insert ProductBrand placeholder after the Lineage placeholder
                        from docx.oxml import OxmlElement
                        from docx.oxml.ns import qn
                        
                        # Create a new text element for ProductBrand
                        new_text = OxmlElement('w:t')
                        new_text.text = f'\n{{{{Label{cnt}.ProductBrand}}}}'
                        
                        # Insert after the lineage end element
                        lineage_end_element = text_elements[lineage_end_index]
                        lineage_end_element.getparent().insert(
                            lineage_end_element.getparent().index(lineage_end_element) + 1, 
                            new_text
                        )
                
                for el in tc.xpath('./*'):
                    cell._tc.append(deepcopy(el))
                cnt += 1
        from docx.oxml.shared import OxmlElement as OE
        tblPr2 = tbl._element.find(qn('w:tblPr'))
        spacing = OxmlElement('w:tblCellSpacing')
        spacing.set(qn('w:w'), str(cut_line_twips))
        spacing.set(qn('w:type'), 'dxa')
        tblPr2.append(spacing)
        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf

    def _expand_template_to_3x3_fixed(self):
        """Expand template to 3x3 grid for standard templates."""
        from docx import Document
        from docx.shared import Pt
        from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from io import BytesIO
        from copy import deepcopy

        num_cols, num_rows = 3, 3
        
        # Set dimensions based on template type - use constants for consistency
        from src.core.constants import CELL_DIMENSIONS
        
        cell_dims = CELL_DIMENSIONS.get(self.template_type, {'width': 2.4, 'height': 2.4})
        col_width_twips = str(int(cell_dims['width'] * 1440))  # Use width from constants
        row_height_pts = Pt(cell_dims['height'] * 72)  # Use height from constants
        # Use minimal spacing for vertical template to ensure all 9 labels fit
        if self.template_type == 'vertical':
            cut_line_twips = int(0.0001 * 1440)  # Minimal spacing for vertical
        else:
            cut_line_twips = int(0.001 * 1440)

        template_path = self._get_template_path()
        doc = Document(template_path)
        if not doc.tables:
            raise RuntimeError("Template must contain at least one table.")
        old = doc.tables[0]
        src_tc = deepcopy(old.cell(0,0)._tc)
        old._element.getparent().remove(old._element)

        while doc.paragraphs and not doc.paragraphs[0].text.strip():
            doc.paragraphs[0]._element.getparent().remove(doc.paragraphs[0]._element)

        tbl = doc.add_table(rows=num_rows, cols=num_cols)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tblPr = tbl._element.find(qn('w:tblPr')) or OxmlElement('w:tblPr')
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'D3D3D3')
        tblPr.insert(0, shd)
        layout = OxmlElement('w:tblLayout')
        layout.set(qn('w:type'), 'fixed')
        tblPr.append(layout)
        tbl._element.insert(0, tblPr)
        grid = OxmlElement('w:tblGrid')
        for _ in range(num_cols):
            gc = OxmlElement('w:gridCol')
            gc.set(qn('w:w'), col_width_twips)
            grid.append(gc)
        tbl._element.insert(0, grid)
        for row in tbl.rows:
            row.height = row_height_pts
            row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
        borders = OxmlElement('w:tblBorders')
        for side in ('insideH','insideV'):
            b = OxmlElement(f"w:{side}")
            b.set(qn('w:val'), "single")
            b.set(qn('w:sz'), "4")
            b.set(qn('w:color'), "D3D3D3")
            b.set(qn('w:space'), "0")
            borders.append(b)
        tblPr.append(borders)
        cnt = 1
        for r in range(num_rows):
            for c in range(num_cols):
                cell = tbl.cell(r,c)
                cell._tc.clear_content()
                tc = deepcopy(src_tc)
                for t in tc.iter(qn('w:t')):
                    if t.text and 'Label1' in t.text:
                        t.text = t.text.replace('Label1', f'Label{cnt}')
                for el in tc.xpath('./*'):
                    cell._tc.append(deepcopy(el))
                cnt += 1
        from docx.oxml.shared import OxmlElement as OE
        tblPr2 = tbl._element.find(qn('w:tblPr'))
        spacing = OxmlElement('w:tblCellSpacing')
        spacing.set(qn('w:w'), str(cut_line_twips))
        spacing.set(qn('w:type'), 'dxa')
        tblPr2.append(spacing)
        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf

    def process_records(self, records):
        """Process records with performance monitoring and timeout protection."""
        try:
            self.start_time = time.time()
            self.chunk_count = 0
            
            # Debug: Log the overall order of records
            overall_order = [record.get('ProductName', 'Unknown') for record in records]
            self.logger.info(f"Processing {len(records)} records in overall order: {overall_order}")
            
            # Limit total number of records for performance
            if len(records) > 200:
                self.logger.warning(f"Limiting records from {len(records)} to 200 for performance")
                records = records[:200]
            
            documents = []
            for i in range(0, len(records), self.chunk_size):
                # Check total processing time
                if time.time() - self.start_time > MAX_TOTAL_PROCESSING_TIME:
                    self.logger.warning(f"Total processing time limit reached ({MAX_TOTAL_PROCESSING_TIME}s), stopping")
                    break
                
                chunk = records[i:i + self.chunk_size]
                self.chunk_count += 1
                
                self.logger.info(f"Processing chunk {self.chunk_count} ({len(chunk)} records)")
                result = self._process_chunk(chunk)
                if result: 
                    documents.append(result)
            
            if not documents: 
                return None
            if len(documents) == 1: 
                return documents[0]
            
            # Combine documents
            self.logger.info(f"Combining {len(documents)} documents")
            composer = Composer(documents[0])
            for doc in documents[1:]:
                composer.append(doc)
            
            final_doc_buffer = BytesIO()
            composer.save(final_doc_buffer)
            final_doc_buffer.seek(0)
            
            total_time = time.time() - self.start_time
            self.logger.info(f"Template processing completed in {total_time:.2f}s for {len(records)} records")
            
            return Document(final_doc_buffer)
        except Exception as e:
            self.logger.error(f"Error processing records: {e}")
            return None

    def _process_chunk(self, chunk):
        """Process a chunk of records with timeout protection."""
        chunk_start_time = time.time()
        
        try:
            if hasattr(self._expanded_template_buffer, 'seek'):
                self._expanded_template_buffer.seek(0)
            
            doc = DocxTemplate(self._expanded_template_buffer)
            
            # Debug: Log the order of records in this chunk
            chunk_order = [record.get('ProductName', 'Unknown') for record in chunk]
            self.logger.info(f"Processing chunk with {len(chunk)} records in order: {chunk_order}")
            
            # Build context for each record in the chunk
            context = {}
            for i, record in enumerate(chunk):
                # Set current record for brand centering logic
                self.current_record = record
                label_context = self._build_label_context(record, doc)
                context[f'Label{i+1}'] = label_context
                # Debug logging to check field values and order
                product_name = record.get('ProductName', 'Unknown')
                self.logger.debug(f"Label{i+1} -> {product_name} - ProductBrand: '{label_context.get('ProductBrand', 'NOT_FOUND')}', Price: '{label_context.get('Price', 'NOT_FOUND')}'")
            for i in range(len(chunk), self.chunk_size):
                context[f'Label{i+1}'] = {}

            # Create InlineImage objects just before rendering to avoid side effects
            for label_ctx in context.values():
                if label_ctx.get('DOH_IMG_PATH'):
                    path = label_ctx['DOH_IMG_PATH']
                    width = label_ctx['DOH_IMG_WIDTH']
                    label_ctx['DOH'] = InlineImage(doc, path, width=width)

            doc.render(context)
            
            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            rendered_doc = Document(buffer)
            
            # Check timeout before post-processing
            if time.time() - chunk_start_time > MAX_PROCESSING_TIME_PER_CHUNK:
                self.logger.warning(f"Chunk processing timeout reached ({MAX_PROCESSING_TIME_PER_CHUNK}s), skipping post-processing")
                return rendered_doc
            
            # Post-process the document to apply dynamic font sizing first
            self._post_process_and_replace_content(rendered_doc)
            
            # Check timeout before lineage colors
            if time.time() - chunk_start_time > MAX_PROCESSING_TIME_PER_CHUNK:
                self.logger.warning(f"Chunk processing timeout reached ({MAX_PROCESSING_TIME_PER_CHUNK}s), skipping lineage colors")
                return rendered_doc
            
            # Apply lineage colors last to ensure they are not overwritten
            apply_lineage_colors(rendered_doc)
            
            # Final enforcement of fixed cell dimensions to prevent any expansion
            for table in rendered_doc.tables:
                enforce_fixed_cell_dimensions(table)
            
            # CRITICAL: For horizontal, vertical, and double templates, explicitly override cell widths after DocxTemplate rendering
            if self.template_type in ['horizontal', 'vertical', 'double']:
                from src.core.constants import CELL_DIMENSIONS
                individual_cell_width = CELL_DIMENSIONS[self.template_type]['width']
                fixed_col_width = str(int(individual_cell_width * 1440))  # Use individual cell width directly
                
                for table in rendered_doc.tables:
                    # Override each cell width
                    for row in table.rows:
                        for cell in row.cells:
                            tcPr = cell._tc.get_or_add_tcPr()
                            tcW = tcPr.find(qn('w:tcW'))
                            if tcW is not None:
                                tcW.getparent().remove(tcW)
                            
                            # Create new width property with correct value
                            tcW = OxmlElement('w:tcW')
                            tcW.set(qn('w:w'), fixed_col_width)
                            tcW.set(qn('w:type'), 'dxa')
                            tcPr.append(tcW)
            
            # Ensure proper table centering and document setup
            self._ensure_proper_centering(rendered_doc)

            # FINAL ENFORCEMENT: For vertical and double templates, force appropriate line spacing for all paragraphs in any cell containing THC_CBD marker
            if self.template_type in ['vertical', 'double']:
                for table in rendered_doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            # Check for THC_CBD marker in cell text or runs
                            cell_text = cell.text.lower()
                            has_thc_cbd = 'thc_cbd' in cell_text or 'thc: cbd:' in cell_text
                            # Also check for marker remnants in runs
                            for para in cell.paragraphs:
                                for run in para.runs:
                                    if 'THC_CBD' in run.text or 'THC_CBD' in para.text:
                                        has_thc_cbd = True
                            if has_thc_cbd:
                                for para in cell.paragraphs:
                                    # Use different line spacing for different templates
                                    if self.template_type == 'vertical':
                                        line_spacing = 2.4
                                    elif self.template_type == 'double':
                                        line_spacing = 1.5
                                    else:
                                        line_spacing = 2.4  # fallback
                                    
                                    para.paragraph_format.line_spacing = line_spacing
                                    pPr = para._element.get_or_add_pPr()
                                    spacing = pPr.find(qn('w:spacing'))
                                    if spacing is None:
                                        spacing = OxmlElement('w:spacing')
                                        pPr.append(spacing)
                                    spacing.set(qn('w:line'), str(int(line_spacing * 240)))
                                    spacing.set(qn('w:lineRule'), 'auto')
            
            chunk_time = time.time() - chunk_start_time
            self.logger.debug(f"Chunk processed in {chunk_time:.2f}s")
            
            # FINAL MARKER CLEANUP: Remove any lingering *_START and *_END markers AFTER font sizing has been applied
            # This cleanup should only remove markers that weren't processed by the font sizing system
            import re
            marker_pattern = re.compile(r'\b\w+_(START|END)\b')
            prefix_pattern = re.compile(r'^(?:[A-Z0-9_]+_)+')
            # Clean in tables
            for table in rendered_doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for para in cell.paragraphs:
                            for run in para.runs:
                                # Only clean if the run still contains markers (indicating they weren't processed)
                                if marker_pattern.search(run.text):
                                    run.text = marker_pattern.sub('', run.text)
                                if prefix_pattern.search(run.text):
                                    run.text = prefix_pattern.sub('', run.text)
            # Clean in paragraphs outside tables
            for para in rendered_doc.paragraphs:
                for run in para.runs:
                    # Only clean if the run still contains markers (indicating they weren't processed)
                    if marker_pattern.search(run.text):
                        run.text = marker_pattern.sub('', run.text)
                    if prefix_pattern.search(run.text):
                        run.text = prefix_pattern.sub('', run.text)
            
            return rendered_doc
        except Exception as e:
            self.logger.error(f"Error in _process_chunk: {e}\n{traceback.format_exc()}")
            raise

    def _build_label_context(self, record, doc):
        """Ultra-optimized label context building for maximum performance."""
        # Fast dictionary copy
        label_context = dict(record)

        # Fast value cleaning - only process non-empty values
        for key, value in label_context.items():
            if value is not None:
                label_context[key] = str(value).strip()
            else:
                label_context[key] = ""

        # Define product type sets for use throughout the method
        classic_types = {"flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge", "rso/co2 tankers"}
        edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}

        # Fast Description and WeightUnits combination
        desc = label_context.get('Description', '') or ''
        weight = (label_context.get('WeightUnits', '') or '').replace('\u202F', '')
        
        # Ultra-fast string operations
        if desc.endswith('- '):
            desc = desc[:-2]
        if weight.startswith('- '):
            weight = weight[2:]
        
        # Template-specific handling
        if self.template_type == 'mini':
            label_context['DescAndWeight'] = wrap_with_marker(desc, 'DESC')
        else:
            if desc and weight:
                label_context['DescAndWeight'] = wrap_with_marker(f"{desc} -\u00A0{weight}", 'DESC')
            else:
                label_context['DescAndWeight'] = wrap_with_marker(desc or weight, 'DESC')

        # Fast DOH image processing - only if needed
        if label_context.get('DOH'):
            doh_value = label_context.get('DOH', '')
            product_type = (label_context.get('ProductType') or 
                          label_context.get('Product Type*') or 
                          record.get('ProductType') or 
                          record.get('Product Type*') or '')

            image_path = process_doh_image(doh_value, product_type)
            if image_path:
                # Fast width selection
                width_map = {'mini': 9, 'double': 9}
                image_width = Mm(width_map.get(self.template_type, 11))
                label_context['DOH'] = InlineImage(doc, image_path, width=image_width)
            else:
                label_context['DOH'] = ''
        else:
            label_context['DOH'] = ''
        
        # Fast ratio processing
        ratio_val = label_context.get('Ratio_or_THC_CBD') or label_context.get('Ratio', '')
        if ratio_val:
            cleaned_ratio = ratio_val.lstrip('- ')
            product_type = (label_context.get('ProductType', '').lower() or 
                          label_context.get('Product Type*', '').lower())
            
            # Fast product type checking with sets
            is_classic = product_type in classic_types
            is_edible = product_type in edible_types
            
            if is_classic and 'mg' in cleaned_ratio.lower():
                cleaned_ratio = format_ratio_multiline(cleaned_ratio)
            elif is_edible and 'mg' in cleaned_ratio.lower():
                cleaned_ratio = format_ratio_multiline(cleaned_ratio)
            elif is_classic:
                cleaned_ratio = self.format_classic_ratio(cleaned_ratio)
            
            label_context['Ratio_or_THC_CBD'] = cleaned_ratio
            
            # Fast marker wrapping
            content = cleaned_ratio.replace('|BR|', '\n')
            # Force line breaks for vertical and double templates
            if self.template_type in ['vertical', 'double'] and content.strip().startswith('THC:') and 'CBD:' in content:
                content = content.replace('THC: CBD:', 'THC:\nCBD:').replace('THC:  CBD:', 'THC:\nCBD:')
            
            marker = 'THC_CBD' if is_classic else 'RATIO'
            label_context['Ratio_or_THC_CBD'] = wrap_with_marker(content, marker)
        else:
            label_context['Ratio_or_THC_CBD'] = ''

        # Fast brand handling - only add brand for non-classic types
        product_type = (label_context.get('ProductType', '').lower() or 
                       label_context.get('Product Type*', '').lower())
        
        if product_type not in classic_types:
            product_brand = (record.get('ProductBrand') or 
                            record.get('Product Brand') or 
                            record.get('product_brand') or 
                            record.get('productbrand') or '')
            
            if product_brand:
                label_context['ProductBrand'] = wrap_with_marker(unwrap_marker(product_brand, 'PRODUCTBRAND_CENTER'), 'PRODUCTBRAND_CENTER')
            else:
                label_context['ProductBrand'] = ''
        else:
            # For classic types, don't include brand
            label_context['ProductBrand'] = ''

        # Fast other field processing
        if label_context.get('Price'):
            label_context['Price'] = wrap_with_marker(unwrap_marker(label_context['Price'], 'PRICE'), 'PRICE')
        
        if label_context.get('Lineage'):
            product_type = (label_context.get('ProductType', '').lower() or 
                          label_context.get('Product Type*', '').lower())
            
            if product_type in edible_types:
                lineage_value = ''
            else:
                lineage_value = label_context['Lineage']
                if self.template_type in {"horizontal", "vertical", "double"} and lineage_value and product_type in classic_types:
                    lineage_value = '\u2022  ' + lineage_value
            
            label_context['Lineage'] = wrap_with_marker(unwrap_marker(lineage_value, 'LINEAGE'), 'LINEAGE')

        # Fast wrapping for remaining fields
        if label_context.get('DescAndWeight'):
            label_context['DescAndWeight'] = wrap_with_marker(unwrap_marker(label_context['DescAndWeight'], 'DESC'), 'DESC')
        
        if 'ProductType' not in label_context:
            label_context['ProductType'] = record.get('ProductType', '')
        
        # Fast strain handling
        product_strain = record.get('ProductStrain') or record.get('Product Strain', '')
        if product_strain:
            label_context['ProductStrain'] = wrap_with_marker(unwrap_marker(product_strain, 'PRODUCTSTRAIN'), 'PRODUCTSTRAIN')
        else:
            label_context['ProductStrain'] = ''

        # Fast joint ratio handling
        if label_context.get('JointRatio'):
            val = label_context['JointRatio']
            marker = 'JOINT_RATIO'
            if is_already_wrapped(val, marker):
                val = unwrap_marker(val, marker)
            formatted_val = self.format_joint_ratio_pack(val)
            label_context['JointRatio'] = wrap_with_marker(formatted_val, marker)

        # Fast description processing
        if label_context.get('Description'):
            label_context['Description'] = self.fix_hyphen_spacing(label_context['Description'])

        # Fast line break processing
        product_type = (label_context.get('ProductType', '').lower() or 
                       label_context.get('Product Type*', '').lower())
        
        if product_type not in classic_types and label_context.get('DescAndWeight'):
            desc_weight = label_context['DescAndWeight']
            if desc_weight.endswith(' - '):
                desc_weight = desc_weight[:-3] + '\n- '
            elif desc_weight.endswith(' -'):
                desc_weight = desc_weight[:-2] + '\n- '
            desc_weight = desc_weight.replace(' - ', '\n- ')
            label_context['DescAndWeight'] = desc_weight
        
        # Fast pre-roll processing
        if product_type in {"pre-roll", "infused pre-roll"} and label_context.get('DescAndWeight'):
            desc_weight = label_context['DescAndWeight']
            desc_weight = desc_weight.replace(' - ', '\n- ')
            label_context['DescAndWeight'] = desc_weight

        # Fast weight and ratio formatting
        for key, marker in [('WeightUnits', 'WEIGHTUNITS'), ('Ratio', 'RATIO')]:
            if label_context.get(key):
                val = label_context[key]
                formatted_val = self.format_with_soft_hyphen(val)
                label_context[key] = wrap_with_marker(unwrap_marker(formatted_val, marker), marker)
        
        # Fast vendor handling
        product_vendor = record.get('Vendor') or record.get('Vendor/Supplier*', '')
        label_context['ProductVendor'] = wrap_with_marker(product_vendor, 'PRODUCTVENDOR')
        
        return label_context

    def _post_process_and_replace_content(self, doc):
        """
        Ultra-optimized post-processing for maximum performance.
        """
        # Performance optimization: Skip expensive processing for large documents
        if len(doc.tables) > 10:
            self.logger.warning(f"Skipping expensive post-processing for large document with {len(doc.tables)} tables")
            return doc
        
        # Fast mini template processing
        if self.template_type == 'mini':
            try:
                self._add_weight_units_markers(doc)
                self._add_brand_markers(doc)
                self._clear_blank_cells_in_mini_template(doc)
            except Exception as e:
                self.logger.warning(f"Mini template processing failed: {e}")

        # Fast font sizing (with timeout protection)
        try:
            self._post_process_template_specific(doc)
        except Exception as e:
            self.logger.warning(f"Font sizing failed: {e}")

        # Fast BR marker conversion - only process if needed
        try:
            br_found = False
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            if '|BR|' in paragraph.text:
                                self._convert_br_markers_to_line_breaks(paragraph)
                                br_found = True
            
            # Only process paragraphs outside tables if BR markers were found
            if br_found:
                for paragraph in doc.paragraphs:
                    if '|BR|' in paragraph.text:
                        self._convert_br_markers_to_line_breaks(paragraph)
        except Exception as e:
            self.logger.warning(f"BR marker conversion failed: {e}")
        
        # Fast ratio spacing fix
        try:
            self._fix_ratio_paragraph_spacing(doc)
        except Exception as e:
            self.logger.warning(f"Ratio spacing failed: {e}")

        # Fast Arial Bold enforcement
        try:
            from src.core.generation.docx_formatting import enforce_arial_bold_all_text
            enforce_arial_bold_all_text(doc)
        except Exception as e:
            self.logger.warning(f"Arial bold failed: {e}")

        # Fast DOH image centering
        try:
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        # Fast check for image-only cells
                        if len(cell.paragraphs) > 0 and all(len(paragraph.runs) == 1 and not paragraph.text.strip() for paragraph in cell.paragraphs):
                            for paragraph in cell.paragraphs:
                                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        # Fast inner table centering
                        for inner_table in cell.tables:
                            inner_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        except Exception as e:
            self.logger.warning(f"DOH centering failed: {e}")
            
        return doc

    def _clear_blank_cells_in_mini_template(self, doc):
        """
        Clear blank cells in mini templates when they run out of values.
        This removes empty cells that don't have any meaningful content.
        """
        try:
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        # Check if cell is essentially empty
                        cell_text = cell.text.strip()
                        
                        # Consider a cell blank if it has no text or only contains template placeholders
                        is_blank = (
                            not cell_text or 
                            cell_text == '' or
                            # Check for empty template placeholders like {{LabelX.Description}}
                            (cell_text.startswith('{{Label') and cell_text.endswith('}}') and 
                             any(field in cell_text for field in ['.Description}}', '.Price}}', '.Lineage}}', '.ProductBrand}}', '.Ratio_or_THC_CBD}}', '.DOH}}', '.ProductStrain}}']))
                        )
                        
                        if is_blank:
                            # Clear the cell content
                            cell._tc.clear_content()
                            
                            # Add a single empty paragraph to maintain cell structure
                            paragraph = cell.add_paragraph()
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            
                            # Set cell background to white/transparent to ensure it's visually clean
                            from src.core.generation.docx_formatting import clear_cell_background
                            clear_cell_background(cell)
                            
                            self.logger.debug(f"Cleared blank cell in mini template")
                            
        except Exception as e:
            self.logger.error(f"Error clearing blank cells in mini template: {e}")
            # Don't raise the exception - this is a cleanup operation that shouldn't break the main process

    def _post_process_template_specific(self, doc):
        """
        Apply template-type-specific font sizing to all markers in the document.
        Uses the original font-sizing functions based on template type.
        """
        # Define marker processing for all template types (including double)
        markers = [
            'DESC', 'PRODUCTBRAND_CENTER', 'PRICE', 'LINEAGE', 
            'THC_CBD', 'THC_CBD_LABEL', 'RATIO', 'WEIGHTUNITS', 'PRODUCTSTRAIN', 'DOH', 'PRODUCTVENDOR'
        ]
        
        # Process all markers in a single pass to avoid conflicts
        self._recursive_autosize_template_specific_multi(doc, markers)
        
        # Apply vertical template specific optimizations for minimal spacing
        if self.template_type in ['vertical', 'double']:
            self._optimize_vertical_template_spacing(doc)



    def _optimize_vertical_template_spacing(self, doc):
        """
        Apply minimal spacing optimizations specifically for vertical and double templates
        to ensure all labels fit on one page.
        """
        try:
            from docx.shared import Pt
            
            def optimize_paragraph_spacing(paragraph):
                """Set minimal spacing for all paragraphs in vertical and double templates."""
                # Set absolute minimum spacing
                paragraph.paragraph_format.space_before = Pt(0)
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.0
                
                # Set at XML level for maximum compatibility
                pPr = paragraph._element.get_or_add_pPr()
                spacing = pPr.find(qn('w:spacing'))
                if spacing is None:
                    spacing = OxmlElement('w:spacing')
                    pPr.append(spacing)
                
                spacing.set(qn('w:before'), '0')
                spacing.set(qn('w:after'), '0')
                spacing.set(qn('w:line'), '240')  # 1.0 line spacing
                spacing.set(qn('w:lineRule'), 'auto')
            
            # Process all tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            optimize_paragraph_spacing(paragraph)
            
            # Process all paragraphs outside tables
            for paragraph in doc.paragraphs:
                optimize_paragraph_spacing(paragraph)
            
            self.logger.debug("Applied vertical/double template spacing optimizations")
            
        except Exception as e:
            self.logger.error(f"Error optimizing vertical/double template spacing: {e}")
            # Don't raise the exception - this is an optimization that shouldn't break the main process

    def _recursive_autosize_template_specific(self, element, marker_name):
        """
        Recursively find and replace markers in paragraphs and tables using template-specific font sizing.
        """
        if hasattr(element, 'paragraphs'):
            for p in element.paragraphs:
                self._process_paragraph_for_marker_template_specific(p, marker_name)

        if hasattr(element, 'tables'):
            for table in element.tables:
                for row in table.rows:
                    for cell in row.cells:
                        self._recursive_autosize_template_specific(cell, marker_name)

    def _recursive_autosize_template_specific_multi(self, element, markers):
        """
        Recursively find and replace all markers in paragraphs and tables using template-specific font sizing.
        Processes all markers in a single pass to avoid conflicts.
        """
        if hasattr(element, 'paragraphs'):
            for p in element.paragraphs:
                self._process_paragraph_for_markers_template_specific(p, markers)

        if hasattr(element, 'tables'):
            for table in element.tables:
                for row in table.rows:
                    for cell in row.cells:
                        self._recursive_autosize_template_specific_multi(cell, markers)

    def _process_paragraph_for_markers_template_specific(self, paragraph, markers):
        """
        Process a single paragraph for multiple markers using template-specific font sizing.
        Handles all markers in a single pass to avoid conflicts.
        """
        full_text = "".join(run.text for run in paragraph.runs)
        
        # Check if any markers are present
        found_markers = []
        for marker_name in markers:
            start_marker = f'{marker_name}_START'
            end_marker = f'{marker_name}_END'
            if start_marker in full_text and end_marker in full_text:
                found_markers.append(marker_name)
        
        if found_markers:
            # Process all markers and build the final content
            final_content = full_text
            processed_content = {}
            
            for marker_name in found_markers:
                start_marker = f'{marker_name}_START'
                end_marker = f'{marker_name}_END'
                
                # Extract content for this marker
                start_idx = final_content.find(start_marker)
                end_idx = final_content.find(end_marker) + len(end_marker)
                
                if start_idx != -1 and end_idx != -1:
                    marker_start = final_content.find(start_marker) + len(start_marker)
                    marker_end = final_content.find(end_marker)
                    content = final_content[marker_start:marker_end]
                    
                    # Get font size for this marker
                    font_size = self._get_template_specific_font_size(content, marker_name)
                    processed_content[marker_name] = {
                        'content': content,
                        'font_size': font_size,
                        'start_pos': start_idx,
                        'end_pos': end_idx
                    }
            
            # Clear paragraph and rebuild with all processed content
            paragraph.clear()
            
            # Sort markers by position in text
            sorted_markers = sorted(processed_content.items(), key=lambda x: x[1]['start_pos'])
            
            current_pos = 0
            for marker_name, marker_data in sorted_markers:
                # Add any text before this marker
                if marker_data['start_pos'] > current_pos:
                    text_before = full_text[current_pos:marker_data['start_pos']]
                    # Preserve line breaks and whitespace, but skip if completely empty
                    if text_before or text_before.strip():
                        run = paragraph.add_run(text_before)
                        run.font.name = "Arial"
                        run.font.bold = True
                        run.font.size = Pt(12)  # Default size for non-marker text
                # Add the processed marker content (use the potentially modified content)
                display_content = marker_data.get('display_content', marker_data['content'])
                # --- BULLETPROOF: Only one run for the entire marker content, preserving line breaks ---
                run = paragraph.add_run()
                run.font.name = "Arial"
                run.font.bold = True
                run.font.size = marker_data['font_size']
                set_run_font_size(run, marker_data['font_size'])
                lines = display_content.splitlines()
                for i, line in enumerate(lines):
                    if i > 0:
                        run.add_break()
                    run.add_text(line)
                current_pos = marker_data['end_pos']
            
            # Add any remaining text
            if current_pos < len(full_text):
                text_after = full_text[current_pos:]
                # Preserve line breaks and whitespace, but skip if completely empty
                if text_after or text_after.strip():
                    run = paragraph.add_run(text_after)
                    run.font.name = "Arial"
                    run.font.bold = True
                    run.font.size = Pt(12)  # Default size for non-marker text
            
            # Convert |BR| markers to actual line breaks after marker processing
            self._convert_br_markers_to_line_breaks(paragraph)
            
            # Apply special formatting for specific markers
            for marker_name, marker_data in processed_content.items():
                # Special handling for ProductBrand markers in Double template
                if ('PRODUCTBRAND' in marker_name) and self.template_type == 'double':
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in paragraph.runs:
                        # Get product type for font sizing
                        product_type = None
                        if hasattr(self, 'current_product_type'):
                            product_type = self.current_product_type
                        elif hasattr(self, 'label_context') and 'ProductType' in self.label_context:
                            product_type = self.label_context['ProductType']
                        set_run_font_size(run, get_font_size_by_marker(marker_data['content'], marker_name, 'double', self.scale_factor, product_type))
                    continue
                if marker_name == 'DOH':
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    continue
                if marker_name == 'RATIO':
                    for run in paragraph.runs:
                        # Get product type for font sizing
                        product_type = None
                        if hasattr(self, 'current_product_type'):
                            product_type = self.current_product_type
                        elif hasattr(self, 'label_context') and 'ProductType' in self.label_context:
                            product_type = self.label_context['ProductType']
                        set_run_font_size(run, get_font_size_by_marker(marker_data['content'], 'RATIO', self.template_type, self.scale_factor, product_type))
                    continue
                if marker_name == 'LINEAGE':
                    content = marker_data['content']
                    product_type = None
                    if hasattr(self, 'current_product_type'):
                        product_type = self.current_product_type
                    elif hasattr(self, 'label_context') and 'ProductType' in self.label_context:
                        product_type = self.label_context['ProductType']
                    
                    # For double template, if this is a brand name (non-classic type), use brand font sizing
                    if self.template_type == 'double' and product_type and not is_classic_type(product_type):
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        # Use brand font sizing for the brand name content
                        for run in paragraph.runs:
                            # Calculate font size based on just the brand name (first word)
                            brand_name = content.split()[0] if content.split() else content
                            font_size = get_font_size_by_marker(brand_name, 'PRODUCTBRAND', 'double', self.scale_factor, product_type)
                            set_run_font_size(run, font_size)
                    else:
                        # Handle classic types as before
                        classic_lineages = [
                            "SATIVA", "INDICA", "HYBRID", "HYBRID/SATIVA", "HYBRID/INDICA", 
                            "CBD", "MIXED", "PARAPHERNALIA", "PARA"
                        ]
                        if content.upper() in classic_lineages and content.upper() != "PARAPHERNALIA":
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                            if self.template_type in {"horizontal", "double", "vertical"}:
                                paragraph.paragraph_format.left_indent = Inches(0.15)
                        else:
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            if self.template_type in {"horizontal", "double", "vertical"}:
                                paragraph.paragraph_format.left_indent = Inches(0.15)
                    continue
                # Always center ProductBrand and ProductBrand_Center markers
                if marker_name in ('PRODUCTBRAND', 'PRODUCTBRAND_CENTER') or 'PRODUCTBRAND' in marker_name:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in paragraph.runs:
                        # Get product type for font sizing
                        product_type = None
                        if hasattr(self, 'current_product_type'):
                            product_type = self.current_product_type
                        elif hasattr(self, 'label_context') and 'ProductType' in self.label_context:
                            product_type = self.label_context['ProductType']
                        set_run_font_size(run, get_font_size_by_marker(marker_data['content'], marker_name, self.template_type, self.scale_factor, product_type))
                    continue
                # Special handling for ProductStrain marker - always use 1pt font
                if marker_name in ('PRODUCTSTRAIN', 'STRAIN'):
                    for run in paragraph.runs:
                        # Only apply 1pt font to runs that contain strain content
                        if marker_data['content'] in run.text:
                            set_run_font_size(run, get_font_size_by_marker(marker_data['content'], 'PRODUCTSTRAIN', self.template_type, self.scale_factor))
                    continue
                # Special handling for ProductVendor marker
                if marker_name == 'PRODUCTVENDOR' or marker_name == 'VENDOR':
                    for run in paragraph.runs:
                        set_run_font_size(run, get_font_size_by_marker(marker_data['content'], marker_name, self.template_type, self.scale_factor))
                        run.font.color.rgb = RGBColor(255, 255, 255)
                    continue
            
            self.logger.debug(f"Applied multi-marker processing for: {list(processed_content.keys())}")
        try:
            pass
        except Exception as e:
            self.logger.error(f"Error processing multi-marker template: {e}")
            # Fallback: remove all markers and use default size
            for run in paragraph.runs:
                for marker_name in markers:
                    start_marker = f'{marker_name}_START'
                    end_marker = f'{marker_name}_END'
                    run.text = run.text.replace(start_marker, "").replace(end_marker, "")
                # Use appropriate default size based on template type
                if self.template_type == 'mini':
                    default_size = Pt(8 * self.scale_factor)
                elif self.template_type == 'vertical':
                    default_size = Pt(10 * self.scale_factor)
                else:  # horizontal
                    default_size = Pt(12 * self.scale_factor)
                run.font.size = default_size
        finally:
            # Always check for |BR| markers regardless of success/failure
            self._convert_br_markers_to_line_breaks(paragraph)

    def _process_paragraph_for_marker_template_specific(self, paragraph, marker_name):
        """
        Process a single paragraph for a specific marker using template-type-specific font sizing.
        """
        start_marker = f'{marker_name}_START'
        end_marker = f'{marker_name}_END'
        
        full_text = "".join(run.text for run in paragraph.runs)
        
        if start_marker in full_text and end_marker in full_text:
            try:
                # Extract content
                start_idx = full_text.find(start_marker) + len(start_marker)
                end_idx = full_text.find(end_marker)
                content = full_text[start_idx:end_idx]
                
                # For THC_CBD markers, calculate font size before any splitting to ensure consistency
                if marker_name in ['THC_CBD', 'RATIO', 'THC_CBD_LABEL'] and ('\n' in content or '|BR|' in content):
                    # Calculate font size based on the original unsplit content to ensure consistency
                    original_content = content.replace('\n', ' ').replace('|BR|', ' ')
                    font_size = self._get_template_specific_font_size(original_content, marker_name)
                    import logging
                    logging.debug(f"[FONT_DEBUG] Processing marker '{marker_name}' with original content '{original_content}' -> font_size: {font_size}")
                    
                    # Clear and recreate with single run approach
                    paragraph.clear()
                    
                    # Create a single run with the entire content
                    run = paragraph.add_run()
                    run.font.name = "Arial"
                    run.font.bold = True
                    run.font.size = font_size
                    set_run_font_size(run, font_size)
                    
                    # Add the content with line breaks as text
                    run.add_text(content)
                    
                    # Convert line breaks to actual line breaks, passing the font size
                    self._convert_br_markers_to_line_breaks(paragraph, font_size)
                else:
                    # Use template-type-specific font sizing based on original functions
                    font_size = self._get_template_specific_font_size(content, marker_name)
                    import logging
                    logging.debug(f"[FONT_DEBUG] Processing marker '{marker_name}' with content '{content}' -> font_size: {font_size}")
                    
                    # Clear paragraph and re-add content with template-optimized formatting
                    paragraph.clear()
                    run = paragraph.add_run()
                    run.font.name = "Arial"
                    run.font.bold = True
                    run.font.size = font_size
                    
                    # Apply template-specific font size setting
                    set_run_font_size(run, font_size)
                    
                    # Add the content to the run
                    run.add_text(content)
                    
                    # Convert |BR| markers to actual line breaks for other markers
                    self._convert_br_markers_to_line_breaks(paragraph, font_size)
                
                # Handle special formatting for specific markers
                if marker_name in ['PRODUCTBRAND', 'PRODUCTBRAND_CENTER']:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    # Also ensure all runs in this paragraph are properly sized
                    for run in paragraph.runs:
                        set_run_font_size(run, font_size)
                elif marker_name in ['THC_CBD', 'RATIO', 'THC_CBD_LABEL']:
                    # For vertical template, apply line spacing from unified font sizing
                    line_spacing = get_line_spacing_by_marker(marker_name)
                    if line_spacing:
                        paragraph.paragraph_format.line_spacing = line_spacing
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        # Set at XML level for maximum compatibility
                        pPr = paragraph._element.get_or_add_pPr()
                        spacing = pPr.find(qn('w:spacing'))
                        if spacing is None:
                            spacing = OxmlElement('w:spacing')
                            pPr.append(spacing)
                        spacing.set(qn('w:line'), str(int(line_spacing * 240)))
                        spacing.set(qn('w:lineRule'), 'auto')
                    # Force: For vertical template, if paragraph contains 'THC: CBD:', set 2.4 line spacing
                    if self.template_type == 'vertical' and 'THC: CBD:' in paragraph.text:
                        paragraph.paragraph_format.line_spacing = 2.4
                        pPr = paragraph._element.get_or_add_pPr()
                        spacing = pPr.find(qn('w:spacing'))
                        if spacing is None:
                            spacing = OxmlElement('w:spacing')
                            pPr.append(spacing)
                        spacing.set(qn('w:line'), str(int(2.4 * 240)))
                        spacing.set(qn('w:lineRule'), 'auto')
                        import logging
                        logging.info(f"[THC_CBD_LINE_SPACING_FORCE] Forced 2.4 line spacing for paragraph: {paragraph.text}")
                    # Line spacing for THC: CBD: content across all templates (legacy logic)
                    elif content == 'THC: CBD:':
                        if self.template_type == 'vertical':
                            paragraph.paragraph_format.line_spacing = 2.25
                            # Add left upper alignment for vertical template
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        elif self.template_type == 'horizontal':
                            paragraph.paragraph_format.line_spacing = 0.9
                        elif self.template_type == 'mini':
                            paragraph.paragraph_format.line_spacing = 0.8
                        else:  # Default for other templates (double, etc.)
                            paragraph.paragraph_format.line_spacing = 1.5
                        
                        # Set vertical alignment to top for the cell containing this paragraph
                        if paragraph._element.getparent().tag.endswith('tc'):  # Check if in table cell
                            cell = paragraph._element.getparent()
                            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                    # For all other Ratio content in horizontal template, set tight line spacing
                    elif self.template_type == 'horizontal' and marker_name in ['THC_CBD', 'RATIO', 'THC_CBD_LABEL']:
                        paragraph.paragraph_format.line_spacing = 0.9
                        # Set vertical alignment to top for the cell containing this paragraph
                        if paragraph._element.getparent().tag.endswith('tc'):  # Check if in table cell
                            cell = paragraph._element.getparent()
                            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                    # For all other THC/CBD content in other templates, set vertical alignment to top
                    elif marker_name in ['THC_CBD', 'RATIO', 'THC_CBD_LABEL']:
                        # Set vertical alignment to top for the cell containing this paragraph
                        if paragraph._element.getparent().tag.endswith('tc'):  # Check if in table cell
                            cell = paragraph._element.getparent()
                            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                
                # Center alignment for brand names
                if 'PRODUCTBRAND' in marker_name:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Center alignment for DOH (Date of Harvest)
                if marker_name == 'DOH':
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Special handling for lineage markers
                if marker_name == 'LINEAGE':
                    # Extract product type information from the content
                    if '_PRODUCT_TYPE_' in content and '_IS_CLASSIC_' in content:
                        parts = content.split('_PRODUCT_TYPE_')
                        if len(parts) == 2:
                            actual_lineage = parts[0]
                            type_info = parts[1]
                            type_parts = type_info.split('_IS_CLASSIC_')
                            if len(type_parts) == 2:
                                product_type = type_parts[0]
                                is_classic_raw = type_parts[1]
                                # Remove LINEAGE_END marker if present
                                if is_classic_raw.endswith('LINEAGE_END'):
                                    is_classic_raw = is_classic_raw[:-len('LINEAGE_END')]
                                is_classic = is_classic_raw.lower() == 'true'
                                
                                # Center if it's NOT a classic type
                                if not is_classic:
                                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                else:
                                    # For Classic Types, left-justify the text
                                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                                
                                # Update the content to only show the actual lineage (remove any markers)
                                if actual_lineage.startswith('LINEAGE_START'):
                                    actual_lineage = actual_lineage[len('LINEAGE_START'):]
                                content = actual_lineage
                        else:
                            # Fallback: use the old logic for backward compatibility
                            classic_lineages = [
                                "SATIVA", "INDICA", "HYBRID", "HYBRID/SATIVA", "HYBRID/INDICA", 
                                "CBD", "MIXED", "PARAPHERNALIA", "PARA"
                            ]
                            # Only center if the content is NOT a classic lineage (meaning it's likely a brand name)
                            if content.upper() not in classic_lineages:
                                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            else:
                                # For Classic Types, left-justify the text
                                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                
                self.logger.debug(f"Applied template-specific font sizing: {font_size.pt}pt for {marker_name} marker")

            except Exception as e:
                self.logger.error(f"Error processing template-specific marker {marker_name}: {e}")
                # Fallback: remove markers and use default size based on template type
                for run in paragraph.runs:
                    run.text = run.text.replace(start_marker, "").replace(end_marker, "")
                    # Use appropriate default size based on template type
                    if self.template_type == 'mini':
                        default_size = Pt(8 * self.scale_factor)
                    elif self.template_type == 'vertical':
                        default_size = Pt(10 * self.scale_factor)
                    else:  # horizontal
                        default_size = Pt(12 * self.scale_factor)
                    run.font.size = default_size
        elif start_marker in full_text or end_marker in full_text:
            # Log partial markers for debugging
            self.logger.debug(f"Found partial {marker_name} marker in text: '{full_text[:100]}...'")

    def _convert_br_markers_to_line_breaks(self, paragraph, font_size=None):
        """
        Convert |BR| markers and \n characters in paragraph text to actual line breaks.
        This splits the text at |BR| markers or \n characters and creates separate runs for each part.
        """
        try:
            # Get all text from the paragraph and store existing font sizes
            full_text = "".join(run.text for run in paragraph.runs)
            
            # Store existing font sizes for each run
            existing_sizes = []
            for run in paragraph.runs:
                if run.text.strip():
                    existing_sizes.append(run.font.size)
            
            # If we have existing sizes, use the first one for all runs to ensure consistency
            # Or use the passed font_size parameter if provided
            consistent_font_size = None
            if font_size is not None:
                consistent_font_size = font_size
            elif existing_sizes:
                consistent_font_size = existing_sizes[0]
            
            # Check if there are any |BR| markers or \n characters
            if '|BR|' not in full_text and '\n' not in full_text:
                return
            
            # First split by |BR| markers, then by \n characters
            if '|BR|' in full_text:
                parts = full_text.split('|BR|')
            else:
                parts = full_text.split('\n')
            
            # Clear the paragraph
            paragraph.clear()
            
            # Set tight paragraph spacing to prevent excessive gaps
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            # Only set line spacing if it's not already set (to preserve custom line spacing)
            if paragraph.paragraph_format.line_spacing is None:
                paragraph.paragraph_format.line_spacing = 1.0
            # Preserve existing line spacing if it's already set (for THC_CBD markers)
            existing_line_spacing = paragraph.paragraph_format.line_spacing
            
            # Add each part as a separate run, with line breaks between them
            size_index = 0
            for i, part in enumerate(parts):
                if part.strip():  # Only add non-empty parts
                    run = paragraph.add_run(part.strip())
                    run.font.name = "Arial"
                    run.font.bold = True
                    
                    # Use consistent font size for all runs
                    if consistent_font_size:
                        run.font.size = consistent_font_size
                    else:
                        # Use a default size only if no existing size is available
                        run.font.size = Pt(12)
                    
                    # Add a line break after this part only if the next part is not empty
                    if i < len(parts) - 1 and parts[i + 1].strip():
                        # Use add_break() with WD_BREAK.LINE to create proper line breaks within the same paragraph
                        run.add_break(WD_BREAK.LINE)
            
            # Restore the original line spacing if it was set
            if 'existing_line_spacing' in locals() and existing_line_spacing != 1.0:
                paragraph.paragraph_format.line_spacing = existing_line_spacing
                # Also set at XML level for maximum compatibility
                pPr = paragraph._element.get_or_add_pPr()
                spacing = pPr.find(qn('w:spacing'))
                if spacing is None:
                    spacing = OxmlElement('w:spacing')
                    pPr.append(spacing)
                spacing.set(qn('w:line'), str(int(existing_line_spacing * 240)))
                spacing.set(qn('w:lineRule'), 'auto')
            
            self.logger.debug(f"Converted {len(parts)-1} |BR| markers to line breaks")
            
        except Exception as e:
            self.logger.error(f"Error converting BR markers to line breaks: {e}")
            # Fallback: just remove the BR markers
            for run in paragraph.runs:
                run.text = run.text.replace('|BR|', ' ')

    def _fix_ratio_paragraph_spacing(self, doc):
        """
        Fix paragraph spacing for ratio content to prevent excessive gaps between lines.
        This ensures tight spacing for multi-line ratio content.
        """
        try:
            # Define patterns that indicate ratio content
            ratio_patterns = [
                'mg THC', 'mg CBD', 'mg CBG', 'mg CBN', 'mg CBC',
                'THC:', 'CBD:', 'CBG:', 'CBN:', 'CBC:',
                '1:1', '2:1', '3:1', '1:1:1', '2:1:1'
            ]
            
            def process_paragraph(paragraph):
                # Check if this paragraph contains ratio content
                text = paragraph.text.lower()
                if any(pattern.lower() in text for pattern in ratio_patterns):
                    # Set tight spacing for ratio content
                    paragraph.paragraph_format.space_before = Pt(0)
                    paragraph.paragraph_format.space_after = Pt(0)
                    paragraph.paragraph_format.line_spacing = 1.0
                    
                    # Also set tight spacing for any child paragraphs (in case of nested content)
                    for child_para in paragraph._element.findall('.//w:p', {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                        if hasattr(child_para, 'pPr') and child_para.pPr is not None:
                            # Set spacing properties at XML level for maximum compatibility
                            spacing = child_para.pPr.find('.//w:spacing', {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
                            if spacing is None:
                                spacing = OxmlElement('w:spacing')
                                child_para.pPr.append(spacing)
                            
                            spacing.set(qn('w:before'), '0')
                            spacing.set(qn('w:after'), '0')
                            spacing.set(qn('w:line'), '240')  # 1.0 line spacing (240 twips)
                            spacing.set(qn('w:lineRule'), 'auto')
            
            # Process all tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            process_paragraph(paragraph)
            
            # Process all paragraphs outside tables
            for paragraph in doc.paragraphs:
                process_paragraph(paragraph)
            
            self.logger.debug("Fixed paragraph spacing for ratio content")
            
        except Exception as e:
            self.logger.error(f"Error fixing ratio paragraph spacing: {e}")
            # Don't raise the exception - this is a formatting enhancement that shouldn't break the main process

    def _ensure_proper_centering(self, doc):
        """
        Ensure tables are properly centered in the document with correct margins and spacing.
        """
        try:
            # Set document margins to ensure proper centering
            for section in doc.sections:
                # Use smaller margins for vertical template to fit all 9 labels
                if self.template_type == 'vertical':
                    section.left_margin = Inches(0.25)
                    section.right_margin = Inches(0.25)
                    section.top_margin = Inches(0.25)
                    section.bottom_margin = Inches(0.25)
                else:
                    section.left_margin = Inches(0.5)
                    section.right_margin = Inches(0.5)
                    section.top_margin = Inches(0.5)
                    section.bottom_margin = Inches(0.5)
            
            # Remove any extra paragraphs that might affect centering
            paragraphs_to_remove = []
            for paragraph in doc.paragraphs:
                if not paragraph.text.strip() and not paragraph.runs:
                    paragraphs_to_remove.append(paragraph)
            
            for paragraph in paragraphs_to_remove:
                paragraph._element.getparent().remove(paragraph._element)
            
            # Ensure all tables are properly centered
            for table in doc.tables:
                # Set table alignment to center
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                
                # Ensure table properties are set correctly
                tblPr = table._element.find(qn('w:tblPr'))
                if tblPr is None:
                    tblPr = OxmlElement('w:tblPr')
                
                # Set table to fixed layout
                tblLayout = OxmlElement('w:tblLayout')
                tblLayout.set(qn('w:type'), 'fixed')
                tblPr.append(tblLayout)
                
                # Ensure table is not auto-fit
                table.autofit = False
                if hasattr(table, 'allow_autofit'):
                    table.allow_autofit = False
                

                
                # Calculate and set proper table width for perfect centering
                from src.core.constants import CELL_DIMENSIONS, GRID_LAYOUTS
                
                # Get individual cell dimensions and grid layout
                cell_dims = CELL_DIMENSIONS.get(self.template_type, {'width': 2.4, 'height': 2.4})
                grid_layout = GRID_LAYOUTS.get(self.template_type, {'rows': 3, 'cols': 3})
                
                # Calculate total table width: individual cell width * number of columns
                individual_cell_width = cell_dims['width']
                num_columns = grid_layout['cols']
                total_table_width = individual_cell_width * num_columns
                
                # Set table width to ensure proper centering
                table.width = Inches(total_table_width)
                
                # Also set the table width property in XML to ensure it's properly applied
                tblPr = table._element.find(qn('w:tblPr'))
                if tblPr is None:
                    tblPr = OxmlElement('w:tblPr')
                    table._element.insert(0, tblPr)
                
                # Set table width property
                tblW = tblPr.find(qn('w:tblW'))
                if tblW is None:
                    tblW = OxmlElement('w:tblW')
                    tblPr.append(tblW)
                tblW.set(qn('w:w'), str(int(total_table_width * 1440)))  # Convert to twips
                tblW.set(qn('w:type'), 'dxa')
                
                # Skip width setting for horizontal, mini, and vertical templates since they should already be correct from template expansion
                if self.template_type != 'horizontal' and self.template_type != 'mini' and self.template_type != 'vertical':
                    # Check if table has columns before trying to modify grid
                    if len(table.columns) > 0:
                        tblGrid = table._element.find(qn('w:tblGrid'))
                        if tblGrid is not None:
                            # Remove existing grid and recreate with proper widths
                            tblGrid.getparent().remove(tblGrid)
                        
                        # Create new grid with proper column widths
                        tblGrid = OxmlElement('w:tblGrid')
                        # Use individual cell width directly from CELL_DIMENSIONS
                        col_width = cell_dims['width']
                        
                        for _ in range(len(table.columns)):
                            gridCol = OxmlElement('w:gridCol')
                            gridCol.set(qn('w:w'), str(int(col_width * 1440)))  # Convert to twips
                            tblGrid.append(gridCol)
                        
                        # Insert the grid at the beginning of the table element
                        table._element.insert(0, tblGrid)
                    
                    # Also ensure each cell has the correct width property
                    for row in table.rows:
                        for cell in row.cells:
                            tcPr = cell._tc.get_or_add_tcPr()
                            tcW = tcPr.find(qn('w:tcW'))
                            if tcW is None:
                                tcW = OxmlElement('w:tcW')
                                tcPr.append(tcW)
                            tcW.set(qn('w:w'), str(int(col_width * 1440)))
                            tcW.set(qn('w:type'), 'dxa')
            
            self.logger.debug("Ensured proper table centering and document setup")
            
        except Exception as e:
            self.logger.error(f"Error ensuring proper centering: {e}")

    def _add_weight_units_markers(self, doc):
        """
        Add RATIO markers around weight units content for mini templates with classic types.
        This allows the post-processing to find and apply the correct font sizing.
        """
        try:
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            # Look for weight units content in individual runs
                            for run in paragraph.runs:
                                run_text = run.text
                                # Check if this run contains weight units content (ends with 'g' or 'mg', or contains specific patterns)
                                # More specific check to avoid marking brand names that contain 'g'
                                is_weight_unit = (
                                    run_text.strip().endswith('g') or 
                                    run_text.strip().endswith('mg') or
                                    re.match(r'^\d+\.?\d*\s*g$', run_text.strip()) or  # "1g", "1.5g"
                                    re.match(r'^\d+\.?\d*\s*mg$', run_text.strip()) or  # "100mg", "50.5mg"
                                    re.match(r'^\d+\.?\d*\s*g\s*x\s*\d+', run_text.strip()) or  # "1g x 2"
                                    re.match(r'^\d+\.?\d*\s*mg\s*x\s*\d+', run_text.strip())  # "100mg x 2"
                                )
                                
                                if is_weight_unit and 'RATIO_START' not in run_text:
                                    # This is likely weight units content that needs markers
                                    # Replace the run text with marked content
                                    run.text = f"RATIO_START{run_text}RATIO_END"
                                    run.font.name = "Arial"
                                    run.font.bold = True
                                    run.font.size = Pt(12)  # Default size, will be adjusted by post-processing
                                    
                                    self.logger.debug(f"Added RATIO markers around weight units: {run_text}")
            
        except Exception as e:
            self.logger.error(f"Error adding weight units markers: {e}")

    def _add_brand_markers(self, doc):
        """
        Add PRODUCTBRAND_CENTER markers around brand content for mini templates.
        This allows the post-processing to find and apply the correct font sizing.
        """
        try:
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            # Look for brand content in individual runs
                            for run in paragraph.runs:
                                run_text = run.text
                                # Check if this run contains brand content (not empty and not already marked)
                                # Only add markers to text that looks like brand names (not empty, not marked, not placeholders)
                                # IMPORTANT: Don't add brand markers if content is already wrapped in RATIO markers
                                if (run_text.strip() and 
                                    'PRODUCTBRAND_CENTER_START' not in run_text and 
                                    'RATIO_START' not in run_text and  # Don't mark content already in RATIO markers
                                    'RATIO_END' not in run_text and    # Don't mark content already in RATIO markers
                                    '{{' not in run_text and 
                                    '}}' not in run_text and
                                    len(run_text.strip()) > 0 and
                                    # Only mark content that looks like brand names (not numbers, not empty)
                                    not run_text.strip().isdigit() and
                                    not run_text.strip().startswith('$') and
                                    not run_text.strip().endswith('g') and
                                    not run_text.strip().endswith('mg')):
                                    # This is likely brand content that needs markers
                                    # Replace the run text with marked content
                                    run.text = f"PRODUCTBRAND_CENTER_START{run_text}PRODUCTBRAND_CENTER_END"
                                    run.font.name = "Arial"
                                    run.font.bold = True
                                    run.font.size = Pt(12)  # Default size, will be adjusted by post-processing
                                    
                                    self.logger.debug(f"Added PRODUCTBRAND_CENTER markers around brand: {run_text}")
            
        except Exception as e:
            self.logger.error(f"Error adding brand markers: {e}")



    def _get_template_specific_font_size(self, content, marker_name):
        """
        Get font size using the unified font sizing system.
        """
        # Use unified font sizing with appropriate complexity type
        complexity_type = 'mini' if self.template_type == 'mini' else 'standard'
        return get_font_size_by_marker(content, marker_name, self.template_type, self.scale_factor)

    def fix_hyphen_spacing(self, text):
        """Replace regular hyphens with non-breaking hyphens to prevent line breaks, 
        but add line breaks before hanging hyphens.
        Used for general text formatting to prevent unwanted line breaks at hyphens."""
        if not text:
            return text
        
        # First, normalize hyphen spacing to ensure consistent format
        text = re.sub(r'\s*-\s*', ' - ', text)
        
        # Check for hanging hyphens (hyphen at the end of a line or followed by a space and then end)
        # Pattern: space + hyphen + space + end of string, or space + hyphen + end of string
        if re.search(r' - $', text) or re.search(r' - \s*$', text):
            # Add line break before the hanging hyphen
            text = re.sub(r' - (\s*)$', r'\n- \1', text)
        
        return text

    def format_with_soft_hyphen(self, text):
        """Format text with soft hyphen + nonbreaking space + value pattern.
        Used for specific formatting where you want a soft hyphen followed by nonbreaking space."""
        if not text:
            return text
        # Replace any leading hyphens/spaces with a single soft hyphen + nonbreaking space
        text = re.sub(r'^[\s\-]+', '\u00AD\u00A0', text)
        # If it didn't start with hyphen/space, prepend
        if not text.startswith('\u00AD\u00A0'):
            text = f'\u00AD\u00A0{text}'
        return text

    def format_classic_ratio(self, text):
        """
        Format ratio for classic types. Handles various input formats and converts them to the standard display format.
        """
        if not text:
            return text
        
        # Clean the text and normalize
        text = text.strip()
        
        # Handle the default "THC:|BR|CBD:" format from excel processor
        if text == "THC:|BR|CBD:":
            return "THC: CBD:"
        
        # If the text already contains THC/CBD format, return as-is
        if 'THC:' in text and 'CBD:' in text:
            return text
        
        # If the text contains mg values, return as-is (let text_processing handle it)
        if 'mg' in text.lower():
            return text
        
        # If the text contains simple ratios (like 1:1:1), format with spaces
        if ':' in text and any(c.isdigit() for c in text):
            # Add spaces around colons for better readability
            # Handle 3-part ratios first to avoid conflicts
            text = re.sub(r'(\d+):(\d+):(\d+)', r'\1: \2: \3', text)
            # Then handle 2-part ratios
            text = re.sub(r'(\d+):(\d+)', r'\1: \2', text)
            return text
        
        # Common patterns for THC/CBD ratios
        thc_patterns = [
            r'THC[:\s]*([0-9.]+)%?',
            r'([0-9.]+)%?\s*THC',
            r'([0-9.]+)\s*THC'
        ]
        
        cbd_patterns = [
            r'CBD[:\s]*([0-9.]+)%?',
            r'([0-9.]+)%?\s*CBD',
            r'([0-9.]+)\s*CBD'
        ]
        
        thc_value = None
        cbd_value = None
        
        # Extract THC value
        for pattern in thc_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                thc_value = match.group(1)
                break
        
        # Extract CBD value
        for pattern in cbd_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                cbd_value = match.group(1)
                break
        
        # If we found both values, format them
        if thc_value and cbd_value:
            # Keep on same line without line breaks
            return f"THC: {thc_value}% CBD: {cbd_value}%"
        elif thc_value:
            return f"THC: {thc_value}%"
        elif cbd_value:
            return f"CBD: {cbd_value}%"
        else:
            # If no clear THC/CBD pattern found, return the original text
            return text

    def format_joint_ratio_pack(self, text):
        """
        Format JointRatio as: [regular space][hyphen][nonbreaking space][amount][space]x[space][count][space]Pack
        Handles both '1gx2Pack', '1g x 2 Pack', and just '1g'.
        Avoids double hyphens if already present.
        """
        if not text:
            return text
        # Remove any leading spaces/hyphens
        text = re.sub(r'^[\s\-]+', '', text)
        # Try to extract amount, count, and 'Pack'
        match = re.match(r"([0-9.]+)g\s*x?\s*([0-9]+)\s*Pack", text, re.IGNORECASE)
        if not match:
            match = re.match(r"([0-9.]+)g\s*x?\s*([0-9]+)Pack", text, re.IGNORECASE)
        if not match:
            match = re.match(r"([0-9.]+)g\s*x?\s*([0-9]+)", text, re.IGNORECASE)
        if match:
            amount = match.group(1).strip()
            count = match.group(2).strip()
            if count:
                formatted = f"{amount}g x {count} Pack"
            else:
                formatted = f"{amount}g"
        else:
            formatted = text

        # Return just the formatted value without adding a hyphen
        # The hyphen will be added by the template concatenation logic
        return formatted



__all__ = ['get_font_scheme', 'TemplateProcessor']