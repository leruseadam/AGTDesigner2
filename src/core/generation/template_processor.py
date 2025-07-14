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
from typing import Dict, Any
import traceback
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Local imports
from src.core.utils.common import safe_get
from src.core.generation.docx_formatting import (
    apply_lineage_colors,
    enforce_fixed_cell_dimensions,
)
from src.core.generation.font_sizing import (
    get_thresholded_font_size,
    get_thresholded_font_size_ratio,
    get_thresholded_font_size_thc_cbd,
    get_thresholded_font_size_brand,
    get_thresholded_font_size_price,
    get_thresholded_font_size_lineage,
    get_thresholded_font_size_description,
    get_thresholded_font_size_strain,
    set_run_font_size
)
from src.core.generation.text_processing import (
    process_doh_image
)
from src.core.formatting.markers import wrap_with_marker, unwrap_marker, is_already_wrapped

def get_font_scheme(template_type, base_size=12):
    schemes = {
        'default': {"base_size": base_size, "min_size": 16, "max_length": 70},
        'vertical': {"base_size": base_size - 1, "min_size": 8, "max_length": 25},
        'mini': {"base_size": base_size - 2, "min_size": 7, "max_length": 20},
        'horizontal': {"base_size": base_size + 1, "min_size": 7, "max_length": 20}
    }
    return {
        field: {**schemes.get(template_type, schemes['default'])}
        for field in ["Description", "ProductBrand", "Price", "Lineage", "DOH", "Ratio_or_THC_CBD", "Ratio"]
    }

def force_table_widths(table, table_width_in, col_widths_in):
    """Force table, column, and cell widths to exact values and disable autofit."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches
    # Remove style
    table.style = None
    # Disable autofit
    table.autofit = False
    if hasattr(table, 'allow_autofit'):
        table.allow_autofit = False
    # Set preferred width
    table.preferred_width = Inches(table_width_in)
    tblPr = table._element.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        table._element.insert(0, tblPr)
    # Remove all <w:tblW> and add a new one
    for old_tblW in tblPr.findall(qn('w:tblW')):
        tblPr.remove(old_tblW)
    tblW = OxmlElement('w:tblW')
    tblW.set(qn('w:w'), str(int(table_width_in * 1440)))
    tblW.set(qn('w:type'), 'dxa')
    tblPr.append(tblW)
    # Remove all <w:tblGrid> and add a new one
    for old_tblGrid in table._element.findall(qn('w:tblGrid')):
        table._element.remove(old_tblGrid)
    tblGrid = OxmlElement('w:tblGrid')
    for col_width in col_widths_in:
        gridCol = OxmlElement('w:gridCol')
        gridCol.set(qn('w:w'), str(int(col_width * 1440)))
        tblGrid.append(gridCol)
    table._element.insert(0, tblGrid)
    # Set every cell width and disable cell autofit
    for row in table.rows:
        for cell in row.cells:
            cell.width = Inches(col_widths_in[0])
            tcPr = cell._tc.get_or_add_tcPr()
            # Remove all <w:tcW> and add a new one
            for old_tcW in tcPr.findall(qn('w:tcW')):
                tcPr.remove(old_tcW)
            tcW = OxmlElement('w:tcW')
            tcW.set(qn('w:w'), str(int(col_widths_in[0] * 1440)))
            tcW.set(qn('w:type'), 'dxa')
            tcPr.append(tcW)

class TemplateProcessor:
    def __init__(self, template_type, font_scheme, scale_factor=1.0):
        self.template_type = template_type
        self.font_scheme = font_scheme
        self.scale_factor = scale_factor
        self.logger = logging.getLogger(__name__)
        
        # DEBUG: Log the template type being passed
        print(f"DEBUG: TemplateProcessor.__init__ - template_type: '{template_type}'")
        
        self._template_path = self._get_template_path()
        self._expanded_template_buffer = self._expand_template_if_needed()
        
        # Set chunk size based on template type
        if self.template_type == 'mini':
            self.chunk_size = 20  # Fixed: 4x5 grid = 20 labels per page
        elif self.template_type == 'double':
            self.chunk_size = 12  # Fixed: 4x3 grid = 12 labels per page
        else:
            # Determine chunk size from expanded template
            doc = Document(self._expanded_template_buffer)
            text = doc.element.body.xml
            matches = re.findall(r'\{\{Label(\d+)\.', text)
            self.chunk_size = max(int(m) for m in matches) if matches else 1
        
        self.logger.info(f"Template type: {self.template_type}, Chunk size: {self.chunk_size}")

    def _get_template_path(self):
        """Get the template path based on template type."""
        try:
            import os
            # Try multiple path resolution strategies for cross-platform compatibility
            possible_paths = []
            
            # Strategy 1: Relative to current file
            base_path = Path(__file__).resolve().parent / "templates"
            template_name = f"{self.template_type}.docx"
            template_path = base_path / template_name
            possible_paths.append(template_path)
            
            # Strategy 2: Relative to current working directory
            cwd_path = Path.cwd() / "src" / "core" / "generation" / "templates" / template_name
            possible_paths.append(cwd_path)
            
            # Strategy 3: Absolute path from project root (for PythonAnywhere)
            if os.environ.get('PYTHONANYWHERE_SITE') or os.environ.get('PYTHONANYWHERE'):
                # PythonAnywhere specific path
                pa_path = Path("/home/adamcordova/AGTDesigner/src/core/generation/templates") / template_name
                possible_paths.append(pa_path)
            
            # Strategy 4: Try with different case variations
            case_variations = [
                f"{self.template_type}.docx",
                f"{self.template_type.capitalize()}.docx",
                f"{self.template_type.upper()}.docx"
            ]
            
            for case_name in case_variations:
                case_path = base_path / case_name
                possible_paths.append(case_path)
            
            # Debug: print all possible paths
            print(f"DEBUG: Looking for template '{template_name}' in possible paths:")
            for i, path in enumerate(possible_paths):
                print(f"DEBUG: Path {i+1}: {path} (exists: {path.exists()})")
            
            # Try each possible path
            for template_path in possible_paths:
                if template_path.exists():
                    print(f"DEBUG: Found template at: {template_path}")
                    return str(template_path)
            
            # If no path works, raise error with all attempted paths
            attempted_paths = "\n".join([str(p) for p in possible_paths])
            raise FileNotFoundError(f"Template file not found: {template_name}\nAttempted paths:\n{attempted_paths}")
            
        except Exception as e:
            self.logger.error(f"Error getting template path: {str(e)}")
            raise

    def _expand_template_if_needed(self):
        try:
            if self.template_type == 'double':
                # Use scratch-built template for double to guarantee exact dimensions
                return self._create_double_template_from_scratch()
            
            doc = Document(self._template_path)
            text = doc.element.body.xml
            matches = re.findall(r'\{\{Label(\d+)\.', text)
            max_label = max(int(m) for m in matches) if matches else 0
            if max_label >= 9:
                with open(self._template_path, 'rb') as f:
                    return BytesIO(f.read())
            
            if self.template_type == 'mini':
                return self._expand_template_to_4x5_fixed_scaled()
            else:
                return self._expand_template_to_3x3_fixed()
        except Exception as e:
            self.logger.error(f"Error expanding template: {e}")
            with open(self._template_path, 'rb') as f:
                return BytesIO(f.read())

    def _expand_template_to_3x3_fixed(self):
        try:
            from src.core.constants import CELL_DIMENSIONS
            doc = Document(self._template_path)
            if not doc.tables: raise ValueError("Template must contain at least one table.")
            old_table = doc.tables[0]
            source_cell_xml = deepcopy(old_table.cell(0, 0)._tc)
            old_table._element.getparent().remove(old_table._element)
            while doc.paragraphs and not doc.paragraphs[0].text.strip():
                doc.paragraphs[0]._element.getparent().remove(doc.paragraphs[0]._element)
            # Guarantee 4x3 for double template, 3x3 for others
            if self.template_type == 'double':
                num_cols = 4
                num_rows = 3
                cell_width = 1.75   # ENFORCE 1.75"
                cell_height = CELL_DIMENSIONS['double']['height']
            elif self.template_type == 'vertical':
                num_cols = 3
                num_rows = 3
                cell_width = CELL_DIMENSIONS['vertical']['width']
                cell_height = CELL_DIMENSIONS['vertical']['height']
            else:
                num_cols = 3
                num_rows = 3
                cell_width = CELL_DIMENSIONS['horizontal']['width']
                cell_height = CELL_DIMENSIONS['horizontal']['height']
            new_table = doc.add_table(rows=num_rows, cols=num_cols)
            new_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            tblPr = new_table._element.find(qn('w:tblPr'))
            if tblPr is None:
                tblPr = OxmlElement('w:tblPr')
            tblLayout = OxmlElement('w:tblLayout')
            tblLayout.set(qn('w:type'), 'fixed')
            tblPr.append(tblLayout)
            new_table._element.insert(0, tblPr)
            # Set table grid with exact column widths
            if self.template_type == 'double':
                fixed_col_width = str(int(1.75 * 1440))
            else:
                fixed_col_width = str(int(cell_width * 1440))
            tblGrid = OxmlElement('w:tblGrid')
            for _ in range(num_cols):
                gridCol = OxmlElement('w:gridCol')
                gridCol.set(qn('w:w'), fixed_col_width)
                tblGrid.append(gridCol)
            new_table._element.insert(0, tblGrid)
            label_num = 1
            for i in range(num_rows):
                for j in range(num_cols):
                    cell = new_table.cell(i, j)
                    cell._tc.clear_content()
                    new_tc = deepcopy(source_cell_xml)
                    for text_el in new_tc.iter():
                        if text_el.tag == qn('w:t') and text_el.text and "Label1" in text_el.text:
                            text_el.text = text_el.text.replace("Label1", f"Label{label_num}")
                    cell._tc.extend(new_tc.xpath("./*"))
                    # ENFORCE 1.7" width for double template
                    if self.template_type == 'double':
                        cell.width = Inches(1.75)
                    else:
                        cell.width = Inches(cell_width)
                    label_num += 1
                row = new_table.rows[i]
                row.height = Inches(cell_height)
                row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
            # After creating the new_table, force every cell's width to 1.7 inches for double template
            if self.template_type == 'double':
                for row in new_table.rows:
                    for cell in row.cells:
                        cell.width = Inches(1.75)
                # Set tblCellSpacing to 0 to minimize gutter
                tblPr = new_table._element.find(qn('w:tblPr'))
                if tblPr is None:
                    tblPr = OxmlElement('w:tblPr')
                spacing = OxmlElement('w:tblCellSpacing')
                spacing.set(qn('w:w'), '0')
                spacing.set(qn('w:type'), 'dxa')
                tblPr.append(spacing)
                new_table._element.insert(0, tblPr)
            # Enforce fixed cell dimensions to prevent any growth
            enforce_fixed_cell_dimensions(new_table, self.template_type)
            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            return buffer
        except Exception as e:
            self.logger.error(f"Error expanding template to 3x3 or 4x3 fixed: {e}\n{traceback.format_exc()}")
            # Fallback to original template
            with open(self._template_path, 'rb') as f:
                return BytesIO(f.read())

    def _expand_template_to_4x5_fixed_scaled(self):
        try:
            self.logger.info("Expanding 'mini' template to a 4x5 grid (4 columns across, 5 rows down).")
            doc = Document(self._template_path)
            if not doc.tables:
                raise ValueError("Mini template must contain at least one table to use as a base.")
            
            source_cell_xml = deepcopy(doc.tables[0].cell(0, 0)._tc)
            
            # --- PATCH: Do NOT auto-insert Lineage field ---
            # source_cell_text = doc.tables[0].cell(0, 0).text
            # if '{{Label1.Lineage}}' not in source_cell_text:
            #     self.logger.info("Lineage field not found in mini template, adding it automatically")
            #     source_cell = doc.tables[0].cell(0, 0)
            #     if source_cell.text.strip():
            #         source_cell.text = f"{source_cell.text}\n{{{{Label1.Lineage}}}}"
            #     else:
            #         source_cell.text = "{{Label1.Lineage}}"
            #     source_cell_xml = deepcopy(source_cell._tc)
            
            # Remove the old table
            old_table = doc.tables[0]
            old_table._element.getparent().remove(old_table._element)
            
            # Remove leading empty paragraphs if any
            while doc.paragraphs and not doc.paragraphs[0].text.strip():
                p = doc.paragraphs[0]
                p._element.getparent().remove(p._element)

            # Create a new 5x4 table (5 rows, 4 columns) - 4 across, 5 down
            rows, cols = 5, 4
            new_table = doc.add_table(rows=rows, cols=cols)
            new_table.alignment = WD_TABLE_ALIGNMENT.CENTER

            # Set table to fixed layout
            tblPr = new_table._element.find(qn('w:tblPr'))
            if tblPr is None:
                tblPr = OxmlElement('w:tblPr')
            tblLayout = OxmlElement('w:tblLayout')
            tblLayout.set(qn('w:type'), 'fixed')
            tblPr.append(tblLayout)

            # Define column widths for exactly 1.75 inches each
            col_width_inches = 1.75 
            fixed_col_width = str(int(col_width_inches * 1440))  # Convert inches to twips
            
            tblGrid = OxmlElement('w:tblGrid')
            for _ in range(cols):
                gridCol = OxmlElement('w:gridCol')
                gridCol.set(qn('w:w'), fixed_col_width)
                tblGrid.append(gridCol)
            new_table._element.insert(0, tblGrid)
            
            # Populate the new table
            for i in range(rows):
                for j in range(cols):
                    label_num = i * cols + j + 1
                    cell = new_table.cell(i, j)
                    cell._tc.clear_content()
                    
                    new_tc = deepcopy(source_cell_xml)
                    for text_el in new_tc.iter():
                        if text_el.tag == qn('w:t') and text_el.text and "Label1" in text_el.text:
                            text_el.text = text_el.text.replace("Label1", f"Label{label_num}")
                    cell._tc.extend(new_tc.xpath("./*"))
                
                # Set row height for a 5x4 grid
                row = new_table.rows[i]
                row.height = Inches(2.0)  # Increased to ensure only 5 rows fit per page
                row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY

            # Enforce fixed cell dimensions to prevent any growth
            enforce_fixed_cell_dimensions(new_table, self.template_type)

            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            return buffer
        except Exception as e:
            self.logger.error(f"Error expanding template to 4x5: {e}\n{traceback.format_exc()}")
            # Fallback to original template
            with open(self._template_path, 'rb') as f:
                return BytesIO(f.read())

    def _create_double_template_from_scratch(self):
        """Create double template from scratch to guarantee exact 1.7 inch column widths, copying all fields/markers from the template's first cell."""
        try:
            from src.core.constants import CELL_DIMENSIONS
            # Load the Double.docx template to get the source cell
            base_path = Path(__file__).resolve().parent / "templates"
            template_path = base_path / "Double.docx"
            doc = Document(str(template_path))
            if not doc.tables:
                raise ValueError("Double template must contain at least one table.")
            old_table = doc.tables[0]
            source_cell_xml = deepcopy(old_table.cell(0, 0)._tc)
            # Remove the old table and any leading empty paragraphs
            old_table._element.getparent().remove(old_table._element)
            while doc.paragraphs and not doc.paragraphs[0].text.strip():
                doc.paragraphs[0]._element.getparent().remove(doc.paragraphs[0]._element)
            # Create 4x3 table from scratch
            num_cols, num_rows = 4, 3
            new_table = doc.add_table(rows=num_rows, cols=num_cols)
            new_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            
            # Remove any table style that might interfere
            new_table.style = None
            
            # Set table properties to fixed layout
            tblPr = new_table._element.find(qn('w:tblPr'))
            if tblPr is None:
                tblPr = OxmlElement('w:tblPr')
            else:
                # Remove any existing table properties that might interfere
                for child in list(tblPr):
                    if child.tag != qn('w:tblLayout'):
                        tblPr.remove(child)
            
            tblLayout = OxmlElement('w:tblLayout')
            tblLayout.set(qn('w:type'), 'fixed')
            tblPr.append(tblLayout)
            spacing = OxmlElement('w:tblCellSpacing')
            spacing.set(qn('w:w'), '0')
            spacing.set(qn('w:type'), 'dxa')
            tblPr.append(spacing)
            new_table._element.insert(0, tblPr)
            
            # Set exact column widths (1.75 inches each)
            col_width_twips = str(int(1.75 * 1440))
            tblGrid = OxmlElement('w:tblGrid')
            for _ in range(num_cols):
                gridCol = OxmlElement('w:gridCol')
                gridCol.set(qn('w:w'), col_width_twips)
                tblGrid.append(gridCol)
            new_table._element.insert(0, tblGrid)
            
            # Set row heights
            row_height = CELL_DIMENSIONS['double']['height']
            for row in new_table.rows:
                row.height = Inches(row_height)
                row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
            
            # Copy the source cell XML into each cell, replacing Label1 with LabelN
            label_num = 1
            for i in range(num_rows):
                for j in range(num_cols):
                    cell = new_table.cell(i, j)
                    cell._tc.clear_content()
                    new_tc = deepcopy(source_cell_xml)
                    for text_el in new_tc.iter():
                        if text_el.tag == qn('w:t') and text_el.text and "Label1" in text_el.text:
                            text_el.text = text_el.text.replace("Label1", f"Label{label_num}")
                    cell._tc.extend(new_tc.xpath("./*"))
                    # Force cell width to exactly 1.75 inches
                    cell.width = Inches(1.75)
                    label_num += 1
            
            # Disable autofit
            new_table.autofit = False
            if hasattr(new_table, 'allow_autofit'):
                new_table.allow_autofit = False
            
            # Enforce fixed dimensions
            enforce_fixed_cell_dimensions(new_table, 'double')
            
            # Final check: force all cell widths again
            for row in new_table.rows:
                for cell in row.cells:
                    cell.width = Inches(1.75)
            
            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            return buffer
        except Exception as e:
            self.logger.error(f"Error creating double template from scratch: {e}")
            raise

    def process_records(self, records):
        try:
            import pandas as pd
            # Debug: print Price column from records if possible
            if isinstance(records, pd.DataFrame) and 'Price' in records.columns:
                print('DEBUG: Price column before template rendering:')
                print(records['Price'])
            elif isinstance(records, list) and len(records) > 0 and isinstance(records[0], dict) and 'Price' in records[0]:
                print('DEBUG: Price values before template rendering:')
                print([r['Price'] for r in records])
            
            # Always try template-based generation first
            documents = []
            for i in range(0, len(records), self.chunk_size):
                chunk = records[i:i + self.chunk_size]
                result = self._process_chunk(chunk)
                if result: 
                    # Validate each document before adding to list
                    if self._validate_document(result):
                        documents.append(result)
                    else:
                        self.logger.error(f"Document validation failed for chunk {i//self.chunk_size + 1}")
                        return None
            
            if not documents: 
                self.logger.error("No valid documents generated")
                return None
                
            if len(documents) == 1: 
                # Validate final document before returning
                if self._validate_document(documents[0]):
                    return documents[0]
                else:
                    self.logger.error("Final single document validation failed")
                    return None
            
            # Use safer document combination method
            final_doc = self._combine_documents_safely(documents)
            if final_doc and self._validate_document(final_doc):
                return final_doc
            else:
                self.logger.error("Final combined document validation failed")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing records: {e}")
            self.logger.error(traceback.format_exc())
            
            # Try to create a fallback document (simple or table-based)
            try:
                self.logger.warning("Attempting to create fallback document")
                fallback_doc = self._create_fallback_document(records)
                if fallback_doc and self._validate_document(fallback_doc):
                    self.logger.info("Fallback document created successfully")
                    return fallback_doc
                else:
                    self.logger.error("Fallback document validation failed")
                    return None
            except Exception as fallback_error:
                self.logger.error(f"Fallback document creation also failed: {fallback_error}")
                return None

    def _validate_document(self, doc):
        """Validate that a document is not corrupted and can be opened."""
        try:
            # Save to buffer and try to reload
            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            
            # Try to load the document back
            test_doc = Document(buffer)
            
            # Basic validation checks
            if not test_doc.paragraphs and not test_doc.tables:
                self.logger.warning("Document has no content")
                return False
                
            # Check for malformed tables
            for table in test_doc.tables:
                try:
                    _ = table.rows
                    _ = table.columns
                except Exception as e:
                    self.logger.error(f"Malformed table found: {e}")
                    return False
                    
            # Check for malformed paragraphs
            for para in test_doc.paragraphs:
                try:
                    _ = para.runs
                except Exception as e:
                    self.logger.error(f"Malformed paragraph found: {e}")
                    return False
            
            buffer.seek(0)
            return True
            
        except Exception as e:
            self.logger.error(f"Document validation failed: {e}")
            return False

    def _combine_documents_safely(self, documents):
        """Combine multiple documents using a safer method than Composer."""
        try:
            if not documents:
                return None
                
            # Use the first document as the base
            master_doc = documents[0]
            
            # If only one document, return it
            if len(documents) == 1:
                return master_doc
            
            # For multiple documents, use a simpler approach
            # Create a new document and copy content
            final_doc = Document()
            
            for i, doc in enumerate(documents):
                # Copy all content from the source document
                for element in doc.element.body:
                    # Create a deep copy to avoid reference issues
                    new_element = deepcopy(element)
                    final_doc.element.body.append(new_element)
                
                # Add spacing between documents (except for the last one)
                if i < len(documents) - 1:
                    final_doc.add_paragraph()
            
            return final_doc
            
        except Exception as e:
            self.logger.error(f"Error combining documents safely: {e}")
            self.logger.error(traceback.format_exc())
            return None

    def _create_fallback_document(self, records):
        """Create a simple fallback document when main generation fails."""
        try:
            self.logger.warning("Creating fallback document due to generation failure")
            
            doc = Document()
            doc.add_heading('Generated Labels', 0)
            
            # Add a simple table with the records
            if records:
                table = doc.add_table(rows=1, cols=len(records[0].keys()))
                table.style = 'Table Grid'
                
                # Add headers
                headers = list(records[0].keys())
                header_cells = table.rows[0].cells
                for i, header in enumerate(headers):
                    header_cells[i].text = str(header)
                
                # Add data rows
                for record in records:
                    row_cells = table.add_row().cells
                    for i, key in enumerate(headers):
                        value = record.get(key, '')
                        row_cells[i].text = str(value) if value is not None else ''
            
            return doc
            
        except Exception as e:
            self.logger.error(f"Error creating fallback document: {e}")
            # Create a minimal safe document
            doc = Document()
            doc.add_paragraph("Document generation failed. Please try again.")
            return doc

    def _create_simple_labels_document(self, records):
        """Create a simple labels document without complex template processing."""
        try:
            self.logger.info("Creating simple labels document")
            
            doc = Document()
            
            # Create a simple grid layout based on template type
            if self.template_type == 'mini':
                cols, rows = 4, 5
                labels_per_page = 20
            elif self.template_type == 'double':
                cols, rows = 4, 3
                labels_per_page = 12
            else:
                cols, rows = 3, 3
                labels_per_page = 9
            
            # Process records in chunks
            for chunk_start in range(0, len(records), labels_per_page):
                chunk = records[chunk_start:chunk_start + labels_per_page]
                
                # Create table for this page
                table = doc.add_table(rows=rows, cols=cols)
                table.style = 'Table Grid'
                
                # Fill the table with labels
                for i, record in enumerate(chunk):
                    row = i // cols
                    col = i % cols
                    cell = table.cell(row, col)
                    
                    # Create simple label content
                    label_text = []
                    
                    # Add key fields
                    if record.get('ProductBrand'):
                        label_text.append(f"Brand: {record['ProductBrand']}")
                    if record.get('ProductStrain'):
                        label_text.append(f"Strain: {record['ProductStrain']}")
                    if record.get('Description'):
                        label_text.append(f"Desc: {record['Description']}")
                    if record.get('Price'):
                        label_text.append(f"Price: {record['Price']}")
                    if record.get('Lineage'):
                        label_text.append(f"Lineage: {record['Lineage']}")
                    if record.get('Ratio_or_THC_CBD'):
                        label_text.append(f"Ratio: {record['Ratio_or_THC_CBD']}")
                    
                    # Join with line breaks
                    cell.text = '\n'.join(label_text)
                
                # Add spacing between pages
                if chunk_start + labels_per_page < len(records):
                    doc.add_paragraph()
            
            return doc
            
        except Exception as e:
            self.logger.error(f"Error creating simple labels document: {e}")
            return self._create_fallback_document(records)

    def _process_chunk(self, chunk):
        try:
            if hasattr(self._expanded_template_buffer, 'seek'):
                self._expanded_template_buffer.seek(0)
            
            doc = DocxTemplate(self._expanded_template_buffer)
            context = {f'Label{i+1}': self._build_label_context(record, doc) for i, record in enumerate(chunk)}
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

            # Build cell-to-record mapping for the main table (assume first table)
            cell_record_map = {}
            if rendered_doc.tables:
                table = rendered_doc.tables[0]
                for i, row in enumerate(table.rows):
                    for j, cell in enumerate(row.cells):
                        idx = i * len(row.cells) + j
                        if idx < len(chunk):
                            cell_record_map[(i, j)] = chunk[idx]

            # Post-process the document to apply dynamic font sizing first
            self._post_process_and_replace_content(rendered_doc)

            # Apply lineage colors last to ensure they are not overwritten
            apply_lineage_colors(rendered_doc, cell_record_map)

            # Final enforcement of fixed cell dimensions to prevent any expansion
            for table in rendered_doc.tables:
                enforce_fixed_cell_dimensions(table, self.template_type)
                table.autofit = False
                if hasattr(table, 'allow_autofit'):
                    table.allow_autofit = False

            # For double template, force widths BEFORE centering
            if self.template_type == 'double':
                print(f"DEBUG: _process_chunk - Forcing double table width BEFORE centering")
                self._force_double_table_width(rendered_doc)

            # Ensure proper table centering and document setup
            print(f"DEBUG: _process_chunk - About to call _ensure_proper_centering with template_type: '{self.template_type}'")
            self._ensure_proper_centering(rendered_doc)

            # --- FINAL: For double template, force all widths to 1.7" AFTER centering ---
            print(f"DEBUG: _process_chunk - About to call _force_double_table_width with template_type: '{self.template_type}'")
            if self.template_type == 'double':
                self._force_double_table_width(rendered_doc)
                # AGGRESSIVE: Force all widths again as very last step
                for table in rendered_doc.tables:
                    force_table_widths(table, 7.0, [1.75, 1.75, 1.75, 1.75])

            logging.warning(f"POST-TEMPLATE context: {repr(context)}")

            return rendered_doc
        except Exception as e:
            self.logger.error(f"Error in _process_chunk: {e}\n{traceback.format_exc()}")
            raise

    def _build_label_context(self, record, doc):
        label_context = record.copy()

        # Clean all values
        for key, value in label_context.items():
            label_context[key] = str(value).strip() if value is not None else ""

        # Combine Description and WeightUnits, ensuring no double hyphens, no hanging hyphens, and only a single space after the hyphen
        desc = (label_context.get('Description', '') or '').strip()
        weight = (label_context.get('WeightUnits', '') or '').strip().replace('\u202F', '')
        # Remove trailing hyphens/spaces from desc and leading hyphens/spaces from weight
        desc = re.sub(r'[-\s]+$', '', desc)
        weight = re.sub(r'^[-\s]+', '', weight)
        
        # For mini templates, only use description without weight
        if self.template_type == 'mini':
            label_context['DescAndWeight'] = desc
        else:
            # For other templates, combine description and weight
            if desc and weight:
                label_context['DescAndWeight'] = f"{desc} -\u00A0{weight}"
            else:
                label_context['DescAndWeight'] = desc or weight

        # Handle DOH image processing
        if 'DOH' in label_context:
            doh_value = label_context.get('DOH', '')
            # Ensure we get the correct product type from all possible keys
            product_type = (
                label_context.get('ProductType')
                or label_context.get('Product Type*')
                or record.get('ProductType')
                or record.get('Product Type*')
                or ''
            )

            # Process DOH image based on DOH value and product type
            image_path = process_doh_image(doh_value, product_type)

            if image_path:
                # Set image width based on template type
                if self.template_type == 'mini':
                    image_width = Mm(7)
                elif self.template_type == 'double':
                    image_width = Mm(7)  # Smaller for double template
                else:  # horizontal and vertical
                    image_width = Mm(11)
                # Create the InlineImage object correctly with the doc object
                label_context['DOH'] = InlineImage(doc, image_path, width=image_width)
            else:
                label_context['DOH'] = ''
        else:
            label_context['DOH'] = ''
        
        # Always set Ratio_or_THC_CBD: clean if present, else empty string
        ratio_val = label_context.get('Ratio', '')
        if ratio_val:
            cleaned_ratio = re.sub(r'^[-\s]+', '', ratio_val)
            # --- NEW: For edibles, break to new line after every 2nd space ---
            product_type = (label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower())
            edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
            classic_types = ["flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge"]
            
            if product_type in edible_types:
                # Insert a line break after every 2nd space
                def break_after_2nd_space(s):
                    parts = s.split(' ')
                    out = []
                    for i, part in enumerate(parts):
                        out.append(part)
                        if (i+1) % 2 == 0 and i != len(parts)-1:
                            out.append('\n')
                    return ' '.join(out).replace(' \n ', '\n')
                cleaned_ratio = break_after_2nd_space(cleaned_ratio)
            elif product_type in classic_types:
                # For classic types, format as "THC:\nCBD:"
                cleaned_ratio = self.format_classic_ratio(cleaned_ratio)
            
            label_context['Ratio_or_THC_CBD'] = cleaned_ratio
        else:
            label_context['Ratio_or_THC_CBD'] = ''
        
        # --- FORCE: For classic types, always set Ratio_or_THC_CBD to 'THC:\nCBD:' ---
        product_type_check = (label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower())
        classic_types_force = ["flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge"]
        if product_type_check in classic_types_force:
            label_context['Ratio_or_THC_CBD'] = "THC:\nCBD:"
        
        # Do NOT wrap text fields with markers for template rendering
        # Just use plain values
        # (If you want to keep marker logic for other uses, do it elsewhere)
        
        # Ensure ProductType is present in the context
        if 'ProductType' not in label_context:
            label_context['ProductType'] = record.get('ProductType', '')
        
        # Set ProductStrain for non-classic types only
        product_type = label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower()
        classic_types = [
            "flower", "pre-roll", "infused pre-roll", "concentrate", 
            "solventless concentrate", "vape cartridge"
        ]
        if product_type in classic_types:
            label_context['ProductStrain'] = ''
        else:
            # For non-classic types, use the actual ProductStrain value from the record
            label_context['ProductStrain'] = record.get('ProductStrain', '') or record.get('Product Strain', '')
        # Do NOT wrap ProductStrain with markers

        # Debug print to check JointRatio value before template rendering
        logging.warning(f"PRE-TEMPLATE JointRatio: {repr(record.get('JointRatio'))}")
        # JointRatio: format with regular space + hyphen + nonbreaking space + value pattern
        if 'JointRatio' in label_context and label_context['JointRatio']:
            val = label_context['JointRatio']
            # Format as "regular space + hyphen + nonbreaking space + value"
            formatted_val = self.format_joint_ratio_pack(val)
            # Always use plain value
            label_context['JointRatio'] = formatted_val

        return label_context

    def _post_process_and_replace_content(self, doc):
        """
        Iterates through the document to find and process all placeholders,
        using template-type-specific font sizing based on the original font-sizing utilities.
        Also ensures DOH image is perfectly centered in its cell.
        """
        # Use template-type-specific font sizing
        self._post_process_template_specific(doc)

        # --- Center DOH image in its cell ---
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    # Keep vertical alignment as TOP to prevent cell expansion
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                    for paragraph in cell.paragraphs:
                        # If the paragraph contains only an image (no text), center it horizontally
                        if len(paragraph.runs) == 1 and not paragraph.text.strip():
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # After existing processing, add this for double template:
        if self.template_type == 'double':
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                words = run.text.split()
                                for word in words:
                                    if len(word) >= 10:
                                        run.font.size = Pt(18)
                                        break
        return doc

    def _post_process_template_specific(self, doc):
        """
        Apply template-type-specific font sizing to all markers in the document.
        Uses the original font-sizing functions based on template type.
        """
        # Define marker processing for all template types
        markers = [
            'DESC', 'PRODUCTBRAND_CENTER', 'PRICE', 'PRIC', 'LINEAGE', 
            'THC_CBD', 'RATIO', 'PRODUCTSTRAIN', 'DOH'
        ]
        
        for marker_name in markers:
            self._recursive_autosize_template_specific(doc, marker_name)

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

    def _apply_price_formatting(self, paragraph, content, font_size):
        """
        Apply price-specific formatting with Arial Bold font (Arial + bold=True).
        """
        try:
            # Clear paragraph and add new run with price formatting
            paragraph.clear()
            run = paragraph.add_run(content)
            
            # Set Arial font and bold
            run.font.name = "Arial"
            run.font.bold = True
            run.font.size = font_size
            
            # Force Arial at XML level for maximum compatibility
            rPr = run._element.get_or_add_rPr()
            
            # Set font family to Arial
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
            
            # Set font size at XML level
            sz = OxmlElement('w:sz')
            sz.set(qn('w:val'), str(int(font_size.pt * 2)))  # Word uses half-points
            rPr.append(sz)
            
            self.logger.debug(f"Applied Arial Bold formatting to price: '{content}' with size {font_size.pt}pt")
            
        except Exception as e:
            self.logger.error(f"Error applying price formatting: {e}")
            # Fallback to basic formatting
            paragraph.clear()
            run = paragraph.add_run(content)
            run.font.name = "Arial"
            run.font.bold = True
            run.font.size = font_size

    def _process_paragraph_for_marker_template_specific(self, paragraph, marker_name):
        """
        Process paragraph for template-specific formatting and font sizing.
        """
        full_text = paragraph.text
        start_marker = f"{marker_name}_START"
        end_marker = f"{marker_name}_END"
        
        if start_marker in full_text and end_marker in full_text:
            try:
                # Extract content between markers
                start_pos = full_text.find(start_marker) + len(start_marker)
                end_pos = full_text.find(end_marker)
                content = full_text[start_pos:end_pos].strip()
                
                # Get template-specific font size
                font_size = self._get_template_specific_font_size(content, marker_name)
                
                # Debug logging for brand processing in mini template
                if marker_name in ['PRODUCTBRAND_CENTER'] and self.template_type == 'mini':
                    first_word = content.split()[0] if content.split() else ''
                    self.logger.debug(f"Processing brand in mini template: '{content}', first_word='{first_word}' ({len(first_word)} letters), font_size={font_size.pt}pt")
                
                # Special handling for price formatting
                if marker_name in ['PRICE', 'PRIC']:
                    self._apply_price_formatting(paragraph, content, font_size)
                else:
                    # Clear paragraph and rebuild with clean content
                    paragraph.clear()
                    run = paragraph.add_run(content)
                    run.font.size = font_size
                
                self.logger.debug(f"Applied template-specific font sizing: {font_size.pt}pt for {marker_name} marker")

            except Exception as e:
                self.logger.error(f"Error processing template-specific marker {marker_name}: {e}")
                # Fallback: clear paragraph and rebuild with clean content
                paragraph.clear()
                run = paragraph.add_run(content)
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

    def _ensure_proper_centering(self, doc):
        """
        Ensure tables are properly centered in the document with correct margins and spacing.
        """
        try:
            # Set document margins to ensure proper centering
            for section in doc.sections:
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
                
                # DEBUG: Log the template type and width calculation
                print(f"DEBUG: _ensure_proper_centering - template_type: '{self.template_type}'")
                
                # Calculate and set proper table width for perfect centering
                if self.template_type == 'double':
                    total_table_width = 6.8
                    col_width = 1.75  # ENFORCE 1.75" per column
                    print(f"DEBUG: Double template - total_table_width: {total_table_width}, col_width: {col_width}")
                elif self.template_type == 'vertical':
                    total_table_width = 6.75
                    col_width = total_table_width / 3
                    print(f"DEBUG: Vertical template - total_table_width: {total_table_width}, col_width: {col_width}")
                elif self.template_type == 'horizontal':
                    total_table_width = 3.3
                    col_width = total_table_width / 3
                    print(f"DEBUG: Horizontal template - total_table_width: {total_table_width}, col_width: {col_width}")
                elif self.template_type == 'mini':
                    total_table_width = 7.0
                    col_width = total_table_width / 4
                    print(f"DEBUG: Mini template - total_table_width: {total_table_width}, col_width: {col_width}")
                else:
                    total_table_width = 6.75
                    col_width = total_table_width / 3
                    print(f"DEBUG: Default/fallback template - total_table_width: {total_table_width}, col_width: {col_width}")
                
                # Set table grid with proper column widths
                tblGrid = OxmlElement('w:tblGrid')
                for _ in range(len(table.columns)):
                    gridCol = OxmlElement('w:gridCol')
                    # ENFORCE 1.7" for double template
                    if self.template_type == 'double':
                        gridCol.set(qn('w:w'), str(int(1.75 * 1440)))
                        print(f"DEBUG: _ensure_proper_centering - Setting double template grid column to 1.75 inches")
                    else:
                        gridCol.set(qn('w:w'), str(int(col_width * 1440)))
                    tblGrid.append(gridCol)
                table._element.insert(0, tblGrid)
                
                # Force every cell's width for double template
                if self.template_type == 'double':
                    for row in table.rows:
                        for cell in row.cells:
                            cell.width = Inches(1.75)
                    print(f"DEBUG: _ensure_proper_centering - Set all double template cells to 1.75 inches")
                    
                    # Set tblCellSpacing to 0 to minimize gutter
                    spacing = OxmlElement('w:tblCellSpacing')
                    spacing.set(qn('w:w'), '0')
                    spacing.set(qn('w:type'), 'dxa')
                    tblPr.append(spacing)
                    table._element.insert(0, tblPr)
                
                # Debug printout: show actual column widths
                actual_widths = [cell.width.inches if hasattr(cell.width, 'inches') else cell.width for cell in table.columns]
                print(f"DEBUG: {self.template_type} template actual column widths: {actual_widths}")
            
            self.logger.debug("Ensured proper table centering and document setup")
            
        except Exception as e:
            self.logger.error(f"Error ensuring proper centering: {e}")

    def _get_template_specific_font_size(self, content, marker_name):
        """
        Get font size using the unified font sizing system.
        """
        from src.core.generation.unified_font_sizing import get_font_size
        
        # Map marker names to field types
        marker_to_field_type = {
            'DESC': 'description',
            'PRODUCTBRAND_CENTER': 'brand',
            'PRICE': 'price',
            'PRIC': 'price',
            'LINEAGE': 'lineage',
            'THC_CBD': 'thc_cbd',
            'RATIO': 'ratio',
            'THC_CBD_LABEL': 'thc_cbd',
            'PRODUCTSTRAIN': 'strain',
            'DOH': 'doh'
        }
        
        field_type = marker_to_field_type.get(marker_name, 'default')
        
        # Use unified font sizing with appropriate complexity type
        complexity_type = 'mini' if self.template_type == 'mini' else 'standard'
        return get_font_size(content, field_type, self.template_type, self.scale_factor, complexity_type)

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
        Format ratio for classic types to show "THC:\nCBD:" format.
        Handles various input formats and converts them to the standard display format.
        """
        if not text:
            return text
        
        # Clean the text and normalize
        text = text.strip()
        
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
            return f"THC: {thc_value}%\nCBD: {cbd_value}%"
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
        import re
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

    def _force_double_table_width(self, doc):
        """Remove all table styles and force every column and cell width to 1.75 inches for double template, and set table width to exactly 7 inches."""
        print(f"DEBUG: _force_double_table_width - Starting with template_type: '{self.template_type}'")
        for table in doc.tables:
            # Remove table style
            table.style = None
            # Set table autofit off
            table.autofit = False
            if hasattr(table, 'allow_autofit'):
                table.allow_autofit = False
            # Set table preferred width to exactly 7 inches
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            from docx.shared import Inches
            table.preferred_width = Inches(7.0)
            # Get or create <w:tblPr>
            tblPr = table._element.find(qn('w:tblPr'))
            if tblPr is None:
                tblPr = OxmlElement('w:tblPr')
                table._element.insert(0, tblPr)
            # Add <w:tblW>
            tblW = OxmlElement('w:tblW')
            tblW.set(qn('w:w'), str(int(7.0 * 1440)))
            tblW.set(qn('w:type'), 'dxa')  # 'dxa' means exact
            tblPr.append(tblW)
            # Set table grid
            tblGrid = OxmlElement('w:tblGrid')
            for _ in range(len(table.columns)):
                gridCol = OxmlElement('w:gridCol')
                gridCol.set(qn('w:w'), str(int(1.75 * 1440)))
                tblGrid.append(gridCol)
            table._element.insert(0, tblGrid)
            # Set every cell width and disable cell autofit
            for row in table.rows:
                for cell in row.cells:
                    cell.width = Inches(1.75)
                    tcPr = cell._tc.get_or_add_tcPr()
                    tcW = OxmlElement('w:tcW')
                    tcW.set(qn('w:w'), str(int(1.75 * 1440)))
                    tcW.set(qn('w:type'), 'dxa')
                    tcPr.append(tcW)
            print(f"DEBUG: _force_double_table_width - Set all cells and table to exact widths (1.75, 7.0)")
        return doc

__all__ = ['get_font_scheme', 'TemplateProcessor']