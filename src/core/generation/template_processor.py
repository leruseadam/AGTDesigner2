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

# Local imports
from src.core.utils.common import safe_get
from src.core.generation.docx_formatting import (
    apply_lineage_colors,
    enforce_fixed_cell_dimensions,
    clear_cell_background,
    clear_cell_margins,
    clear_table_cell_padding,
)
from src.core.generation.font_sizing import (
    get_thresholded_font_size,
<<<<<<< HEAD
    get_thresholded_font_size_ratio,
=======
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
    get_thresholded_font_size_thc_cbd,
    get_thresholded_font_size_brand,
    get_thresholded_font_size_price,
    get_thresholded_font_size_lineage,
    get_thresholded_font_size_description,
    get_thresholded_font_size_strain,
    set_run_font_size
)
from src.core.generation.text_processing import (
    process_doh_image,
    format_ratio_multiline
)
from src.core.formatting.markers import wrap_with_marker, unwrap_marker, is_already_wrapped

def get_font_scheme(template_type, base_size=12):
    schemes = {
        'default': {"base_size": base_size, "min_size": 16, "max_length": 70},
        'vertical': {"base_size": base_size - 1, "min_size": 8, "max_length": 25},
        'mini': {"base_size": base_size - 2, "min_size": 7, "max_length": 20},
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
            base_path = Path(__file__).resolve().parent / "templates"
            template_name = f"{self.template_type}.docx"
            template_path = base_path / template_name
            
            if not template_path.exists():
                raise FileNotFoundError(f"Template file not found: {template_path}")
            
            return str(template_path)
        except Exception as e:
            self.logger.error(f"Error getting template path: {str(e)}")
            raise

<<<<<<< HEAD
    def _expand_template_if_needed(self):
=======
    def _expand_template_if_needed(self, force_expand=False):
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
        try:
            doc = Document(self._template_path)
            text = doc.element.body.xml
            matches = re.findall(r'\{\{Label(\d+)\.', text)
            max_label = max(int(m) for m in matches) if matches else 0
<<<<<<< HEAD
            if max_label >= 9:
=======
            
            # Force expansion if requested, otherwise only expand if needed
            if not force_expand and max_label >= 9:
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                with open(self._template_path, 'rb') as f:
                    return BytesIO(f.read())
            
            if self.template_type == 'mini':
                return self._expand_template_to_4x5_fixed_scaled()
            elif self.template_type == 'double':
                return self._expand_template_to_4x3_fixed_double()
            else:
                return self._expand_template_to_3x3_fixed()
        except Exception as e:
            self.logger.error(f"Error expanding template: {e}")
            with open(self._template_path, 'rb') as f:
                return BytesIO(f.read())
<<<<<<< HEAD
=======
    
    def force_re_expand_template(self):
        """Force re-expansion of the template to ensure latest fixes are applied."""
        self._expanded_template_buffer = self._expand_template_if_needed(force_expand=True)
        self.logger.info(f"Force re-expanded template for {self.template_type}")
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)

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
            new_table = doc.add_table(rows=3, cols=3)
            new_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            tblPr = new_table._element.find(qn('w:tblPr'))
            if tblPr is None:
                tblPr = OxmlElement('w:tblPr')
            tblLayout = OxmlElement('w:tblLayout')
            tblLayout.set(qn('w:type'), 'fixed')
            tblPr.append(tblLayout)
            new_table._element.insert(0, tblPr)
            # Use identical logic, but swap width/height for vertical
            if self.template_type == 'vertical':
                cell_width = CELL_DIMENSIONS['vertical']['width']
                cell_height = CELL_DIMENSIONS['vertical']['height']
            else:
                cell_width = CELL_DIMENSIONS['horizontal']['width']
                cell_height = CELL_DIMENSIONS['horizontal']['height']
            fixed_col_width = str(int(cell_width * 1440 / 3))
            tblGrid = OxmlElement('w:tblGrid')
            for _ in range(3):
                gridCol = OxmlElement('w:gridCol')
                gridCol.set(qn('w:w'), fixed_col_width)
                tblGrid.append(gridCol)
            new_table._element.insert(0, tblGrid)
            for i in range(3):
                for j in range(3):
                    label_num = i * 3 + j + 1
                    cell = new_table.cell(i, j)
                    cell._tc.clear_content()
                    new_tc = deepcopy(source_cell_xml)
                    for text_el in new_tc.iter():
                        if text_el.tag == qn('w:t') and text_el.text and "Label1" in text_el.text:
                            text_el.text = text_el.text.replace("Label1", f"Label{label_num}")
                    cell._tc.extend(new_tc.xpath("./*"))
<<<<<<< HEAD
=======
                    
                    # CRITICAL: Explicitly override cell width to prevent inheritance from template
                    # Remove any existing width properties from the copied content
                    tcPr = cell._tc.get_or_add_tcPr()
                    tcW = tcPr.find(qn('w:tcW'))
                    if tcW is not None:
                        tcW.getparent().remove(tcW)
                    
                    # Create new width property with correct value
                    tcW = OxmlElement('w:tcW')
                    tcW.set(qn('w:w'), fixed_col_width)
                    tcW.set(qn('w:type'), 'dxa')
                    tcPr.append(tcW)
                    
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                row = new_table.rows[i]
                row.height = Inches(cell_height)
                row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
            
            # Enforce fixed cell dimensions to prevent any growth
            enforce_fixed_cell_dimensions(new_table)
            
            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            return buffer
        except Exception as e:
            self.logger.error(f"Error expanding template to 3x3: {e}")
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
            new_table._element.insert(0, tblPr)

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
            enforce_fixed_cell_dimensions(new_table)

            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            return buffer
        except Exception as e:
            self.logger.error(f"Error expanding template to 4x5: {e}\n{traceback.format_exc()}")
            # Fallback to original template
            with open(self._template_path, 'rb') as f:
                return BytesIO(f.read())

    def _expand_template_to_4x3_fixed_double(self):
        """
        Expand the double template to a 4x3 grid with fixed cell dimensions.
        Each cell is exactly 1.75" wide and 2.5" tall.
        """
        try:
            from src.core.constants import CELL_DIMENSIONS
            doc = Document(self._template_path)
            source_cell_xml = None
            
            # Find the source cell from the original template
            for table in doc.tables:
                if table.rows and table.rows[0].cells:
                    source_cell_xml = deepcopy(table.rows[0].cells[0]._tc)
                    # Fix the cell width property in the source cell to 1.75 inches
                    tcPr = source_cell_xml.get_or_add_tcPr()
                    tcW = tcPr.find(qn('w:tcW'))
                    if tcW is None:
                        tcW = OxmlElement('w:tcW')
                        tcPr.append(tcW)
                    tcW.set(qn('w:w'), str(int(1.75 * 1440)))  # 1.75 inches in twips
                    tcW.set(qn('w:type'), 'dxa')
                    break
                    
            if not source_cell_xml:
                self.logger.error("Could not find source cell in double template")
                with open(self._template_path, 'rb') as f:
                    return BytesIO(f.read())
            
            # Clear the document and create new table
            doc._element.body.clear_content()
            
            # Create 4x3 table (4 columns, 3 rows)
            new_table = doc.add_table(rows=3, cols=4)
            new_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            tblPr = new_table._element.find(qn('w:tblPr'))
            if tblPr is None:
                tblPr = OxmlElement('w:tblPr')
            tblLayout = OxmlElement('w:tblLayout')
            tblLayout.set(qn('w:type'), 'fixed')
            tblPr.append(tblLayout)
            new_table._element.insert(0, tblPr)
            
            # FORCE: Double template cell width to exactly 1.75 inches
            cell_width = 1.75  # Hardcoded override
            cell_height = CELL_DIMENSIONS['double']['height']  # 2.5 inches per cell
            
            # Each column should be exactly 1.75" wide (not divided by 3)
            fixed_col_width = str(int(cell_width * 1440))  # 1.75 inches in twips
            
            # Remove any existing table grid
            existing_grid = new_table._element.find(qn('w:tblGrid'))
            if existing_grid is not None:
                existing_grid.getparent().remove(existing_grid)
            
            # Create new table grid with proper column widths
            tblGrid = OxmlElement('w:tblGrid')
            for _ in range(4):  # 4 columns
                gridCol = OxmlElement('w:gridCol')
                gridCol.set(qn('w:w'), fixed_col_width)
                tblGrid.append(gridCol)
            new_table._element.insert(0, tblGrid)
            
            for i in range(3):  # 3 rows
                for j in range(4):  # 4 columns
                    label_num = i * 4 + j + 1  # Update label numbering for 4x3 grid
                    cell = new_table.cell(i, j)
                    cell._tc.clear_content()
                    new_tc = deepcopy(source_cell_xml)
                    for text_el in new_tc.iter():
                        if text_el.tag == qn('w:t') and text_el.text and "Label1" in text_el.text:
                            text_el.text = text_el.text.replace("Label1", f"Label{label_num}")
                    cell._tc.extend(new_tc.xpath("./*"))
                    
                    # Set cell width property to match the grid
                    tcPr = cell._tc.get_or_add_tcPr()
                    tcW = tcPr.find(qn('w:tcW'))
                    if tcW is None:
                        tcW = OxmlElement('w:tcW')
                        tcPr.append(tcW)
                    tcW.set(qn('w:w'), fixed_col_width)
                    tcW.set(qn('w:type'), 'dxa')
                    
                row = new_table.rows[i]
                row.height = Inches(cell_height)  # 2.5 inches
                row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
            
            # Disable autofit to prevent any auto-sizing
            new_table.autofit = False
            if hasattr(new_table, 'allow_autofit'):
                new_table.allow_autofit = False
            
            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            return buffer
        except Exception as e:
            self.logger.error(f"Error expanding template to 4x3 double: {e}")
            with open(self._template_path, 'rb') as f:
                return BytesIO(f.read())

    def process_records(self, records):
        try:
            documents = []
            for i in range(0, len(records), self.chunk_size):
                chunk = records[i:i + self.chunk_size]
                result = self._process_chunk(chunk)
                if result: documents.append(result)
            
            if not documents: return None
            if len(documents) == 1: return documents[0]
            
            composer = Composer(documents[0])
            for doc in documents[1:]:
                composer.append(doc)
            
            final_doc_buffer = BytesIO()
            composer.save(final_doc_buffer)
            final_doc_buffer.seek(0)
            return Document(final_doc_buffer)
        except Exception as e:
            self.logger.error(f"Error processing records: {e}")
            return None

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
            
            # Post-process the document to apply dynamic font sizing first
            self._post_process_and_replace_content(rendered_doc)
            
            # Apply lineage colors last to ensure they are not overwritten
            apply_lineage_colors(rendered_doc)
            
            # Final enforcement of fixed cell dimensions to prevent any expansion
            for table in rendered_doc.tables:
                if self.template_type == 'double':
                    self._enforce_double_template_dimensions(table)
                else:
                    enforce_fixed_cell_dimensions(table)
            
<<<<<<< HEAD
=======
            # CRITICAL: For horizontal templates, explicitly override cell widths after DocxTemplate rendering
            if self.template_type == 'horizontal':
                from src.core.constants import CELL_DIMENSIONS
                individual_cell_width = CELL_DIMENSIONS['horizontal']['width']
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
            
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
            # Ensure proper table centering and document setup
            self._ensure_proper_centering(rendered_doc)
            
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
                    image_width = Mm(9)
                elif self.template_type == 'double':
                    image_width = Mm(6)  # Smaller DOH image for double template
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
            # --- NEW: For edibles and RSO/CO2 Tankers, break to new line after every 2nd space ---
            product_type = (label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower())
            edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
            classic_types = ["flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge", "rso/co2 tankers"]
            
            if product_type in classic_types:
                # For classic types, check if content contains mg values
                if 'mg' in cleaned_ratio.lower():
                    # Use format_ratio_multiline to add line breaks after every 2nd word
                    cleaned_ratio = format_ratio_multiline(cleaned_ratio)
                else:
                    # For non-mg content, use classic ratio formatting
                    cleaned_ratio = self.format_classic_ratio(cleaned_ratio)
            elif product_type in edible_types or 'mg' in cleaned_ratio.lower():
                # For edibles OR any product type with mg values, add line breaks
                if 'mg' in cleaned_ratio.lower():
                    # Use format_ratio_multiline to add line breaks after every 2nd word
                    cleaned_ratio = format_ratio_multiline(cleaned_ratio)
            
            label_context['Ratio_or_THC_CBD'] = cleaned_ratio
        else:
            label_context['Ratio_or_THC_CBD'] = ''
        
        # --- FORCE: For classic types, set Ratio_or_THC_CBD based on template type ---
        product_type_check = (label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower())
        classic_types_force = ["flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge", "rso/co2 tankers"]
        
        if product_type_check in classic_types_force:
            # For classic types, always use "THC: CBD:" format regardless of template type
            label_context['Ratio_or_THC_CBD'] = "THC: CBD:"
            # Classic: wrap with RATIO marker
            label_context['Ratio_or_THC_CBD'] = wrap_with_marker(unwrap_marker(label_context['Ratio_or_THC_CBD'], 'RATIO'), 'RATIO')

        elif label_context.get('Ratio_or_THC_CBD') == "THC: CBD:":
            # Non-classic: wrap with THC_CBD_LABEL marker
            label_context['Ratio_or_THC_CBD'] = wrap_with_marker(unwrap_marker(label_context['Ratio_or_THC_CBD'], 'THC_CBD_LABEL'), 'THC_CBD_LABEL')
        else:
            # Existing logic for other cases
            if label_context.get('Ratio_or_THC_CBD'):
                label_context['Ratio_or_THC_CBD'] = wrap_with_marker(unwrap_marker(label_context['Ratio_or_THC_CBD'], 'RATIO'), 'RATIO')

        # Handle both 'ProductBrand' and 'Product Brand' field names
        # Don't wrap with markers here - pass raw data to DocxTemplate
        product_brand = label_context.get('ProductBrand') or label_context.get('Product Brand', '')
        
        # If no brand name, try fallback options
        if not product_brand or product_brand.strip() == '':
            # Try to extract brand from product name (e.g., "White Widow CBG Platinum Distillate" -> "Platinum Distillate")
            product_name = label_context.get('ProductName', '') or label_context.get('Product Name*', '')
            if product_name:
                # Look for common brand patterns in product name
                # Pattern: product name followed by brand name (e.g., "White Widow CBG Platinum Distillate")
                brand_patterns = [
                    r'(.+?)\s+(Platinum|Premium|Gold|Silver|Elite|Select|Reserve|Craft|Artisan|Boutique|Signature|Limited|Exclusive|Private|Custom|Special|Deluxe|Ultra|Super|Mega|Max|Pro|Plus|X|Elite|Premium|Select|Reserve|Craft|Artisan|Boutique|Signature|Limited|Exclusive|Private|Custom|Special|Deluxe|Ultra|Super|Mega|Max|Pro|Plus|X)\s+(Distillate|Extract|Concentrate|Oil|Tincture|Gel|Capsule|Edible|Gummy|Chocolate|Beverage|Topical|Cream|Lotion|Salve|Balm|Spray|Drops|Syrup|Sauce|Dab|Wax|Shatter|Live|Rosin|Resin|Kief|Hash|Bubble|Ice|Water|Solventless|Full\s+Spectrum|Broad\s+Spectrum|Isolate|Terpene|Terpenes|Terp|Terps)',
                    r'(.+?)\s+(Distillate|Extract|Concentrate|Oil|Tincture|Gel|Capsule|Edible|Gummy|Chocolate|Beverage|Topical|Cream|Lotion|Salve|Balm|Spray|Drops|Syrup|Sauce|Dab|Wax|Shatter|Live|Rosin|Resin|Kief|Hash|Bubble|Ice|Water|Solventless|Full\s+Spectrum|Broad\s+Spectrum|Isolate|Terpene|Terpenes|Terp|Terps)',
                    r'(.+?)\s+(Platinum|Premium|Gold|Silver|Elite|Select|Reserve|Craft|Artisan|Boutique|Signature|Limited|Exclusive|Private|Custom|Special|Deluxe|Ultra|Super|Mega|Max|Pro|Plus|X)',
                ]
                
                for pattern in brand_patterns:
                    match = re.search(pattern, product_name, re.IGNORECASE)
                    if match:
                        # Extract the brand part (everything after the product name)
                        full_match = match.group(0)
                        product_part = match.group(1).strip()
                        brand_part = full_match[len(product_part):].strip()
                        if brand_part:
                            product_brand = brand_part
                            break
                
                # If still no brand, try vendor as fallback
                if not product_brand or product_brand.strip() == '':
                    vendor = record.get('Vendor', '') or record.get('Vendor/Supplier*', '')
                    if vendor and vendor.strip() != '':
                        product_brand = vendor.strip()
        
        if product_brand:
            # Clean the brand data but don't wrap with markers yet
            # For classic types (including RSO/CO2 Tankers), use PRODUCTBRAND marker
            product_type = label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower()
            classic_types = ["flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge", "rso/co2 tankers"]
            
            if product_type in classic_types:
                label_context['ProductBrand'] = wrap_with_marker(unwrap_marker(product_brand, 'PRODUCTBRAND'), 'PRODUCTBRAND')
            else:
                # For non-classic types, use PRODUCTBRAND_CENTER marker (centered like edibles)
                label_context['ProductBrand'] = wrap_with_marker(unwrap_marker(product_brand, 'PRODUCTBRAND_CENTER'), 'PRODUCTBRAND_CENTER')
        if label_context.get('Price'):
            label_context['Price'] = wrap_with_marker(unwrap_marker(label_context['Price'], 'PRICE'), 'PRICE')
        if label_context.get('Lineage'):
            product_type = label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower()
            classic_types = ["flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge", "rso/co2 tankers"]
            edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
<<<<<<< HEAD
            
            # For edibles, use brand instead of lineage
            if product_type in edible_types:
                # Get brand directly from the record to avoid marker wrapping issues
=======
            template_types_with_indent = {"horizontal", "double", "vertical"}
            # For edibles, use brand instead of lineage
            if product_type in edible_types:
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                product_brand = record.get('ProductBrand', '') or record.get('Product Brand', '')
                if product_brand:
                    lineage_value = product_brand.upper()
                else:
                    lineage_value = label_context['Lineage']
<<<<<<< HEAD
            elif product_type in classic_types:
                # For classic types, just use the lineage value (alignment will be handled in post-processing)
                lineage_value = label_context['Lineage']
            else:
                # For non-classic types, just use the lineage value (alignment will be handled in post-processing)
                lineage_value = label_context['Lineage']
            
=======
            else:
                lineage_value = label_context['Lineage']
            # Only add bullet+2 spaces for classic types in horizontal, double, vertical if lineage is not empty
            if self.template_type in template_types_with_indent and lineage_value and product_type in classic_types:
                lineage_value = '\u2022  ' + lineage_value
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
            label_context['Lineage'] = wrap_with_marker(unwrap_marker(lineage_value, 'LINEAGE'), 'LINEAGE')
        # Only wrap Ratio_or_THC_CBD with RATIO marker if it's not already wrapped
        if label_context.get('Ratio_or_THC_CBD'):
            if ('WEIGHTUNITS_START' not in label_context['Ratio_or_THC_CBD'] and 
                'THC_CBD_START' not in label_context['Ratio_or_THC_CBD']):
                label_context['Ratio_or_THC_CBD'] = wrap_with_marker(unwrap_marker(label_context['Ratio_or_THC_CBD'], 'RATIO'), 'RATIO')
        if label_context.get('DescAndWeight'):
            label_context['DescAndWeight'] = wrap_with_marker(unwrap_marker(label_context['DescAndWeight'], 'DESC'), 'DESC')
        
        # Ensure ProductType is present in the context
        if 'ProductType' not in label_context:
            label_context['ProductType'] = record.get('ProductType', '')
        
        # Set ProductStrain for all product types
        product_type = label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower()
        classic_types = [
            "flower", "pre-roll", "infused pre-roll", "concentrate", 
            "solventless concentrate", "vape cartridge", "rso/co2 tankers"
        ]
        
        # Set ProductStrain for all product types
        product_type = label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower()
        edible_types = {"edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule"}
        
        # For all product types, use the actual Product Strain value
        label_context['ProductStrain'] = record.get('ProductStrain', '') or record.get('Product Strain', '')
        
        # Now wrap ProductStrain with markers if it has content
        if label_context.get('ProductStrain'):
            label_context['ProductStrain'] = wrap_with_marker(unwrap_marker(label_context['ProductStrain'], 'PRODUCTSTRAIN'), 'PRODUCTSTRAIN')

        # Debug print to check JointRatio value before template rendering
        logging.warning(f"PRE-TEMPLATE JointRatio: {repr(record.get('JointRatio'))}")
        # JointRatio: format with regular space + hyphen + nonbreaking space + value pattern
        if 'JointRatio' in label_context and label_context['JointRatio']:
            val = label_context['JointRatio']
            marker = 'JOINT_RATIO'
            # First unwrap if already wrapped
            if is_already_wrapped(val, marker):
                val = unwrap_marker(val, marker)
            # Format as "regular space + hyphen + nonbreaking space + value"
            formatted_val = self.format_joint_ratio_pack(val)
            # Debug: print Unicode code points for inspection
            logging.warning(f"DEBUG JointRatio codepoints: {[hex(ord(c)) for c in formatted_val]}")
            # Always wrap with markers
            label_context['JointRatio'] = wrap_with_marker(formatted_val, marker)

        # Apply non-breaking hyphen only to Description
        if 'Description' in label_context and label_context['Description']:
            label_context['Description'] = self.fix_hyphen_spacing(label_context['Description'])

        # For JointRatio and non-classic types, always break at hyphen
        if product_type not in classic_types:
            if 'DescAndWeight' in label_context and label_context['DescAndWeight']:
                # First handle hanging hyphens, then add line breaks before all hyphens
                desc_weight = label_context['DescAndWeight']
                # Check for hanging hyphens and add line breaks before them
                if re.search(r' - $', desc_weight) or re.search(r' - \s*$', desc_weight):
                    desc_weight = re.sub(r' - (\s*)$', r'\n- \1', desc_weight)
                # Add line breaks before all hyphens for non-classic types and RSO/CO2 Tankers
                desc_weight = desc_weight.replace(' - ', '\n- ')
                label_context['DescAndWeight'] = desc_weight
        
        # For pre-roll products with JointRatio, always ensure line breaks
        if product_type in ["pre-roll", "infused pre-roll"]:
            if 'DescAndWeight' in label_context and label_context['DescAndWeight']:
                desc_weight = label_context['DescAndWeight']
                # Ensure JointRatio is on a new line by adding line breaks before hyphens
                desc_weight = desc_weight.replace(' - ', '\n- ')
                label_context['DescAndWeight'] = desc_weight

        # Format WeightUnits and Ratio with soft hyphen + nonbreaking space + value pattern
        for key, marker in [
            ('WeightUnits', 'WEIGHTUNITS'),
            ('Ratio', 'RATIO')
        ]:
            if key in label_context and label_context[key]:
                val = label_context[key]
                # Format as "soft hyphen + nonbreaking space + value"
                formatted_val = self.format_with_soft_hyphen(val)
                label_context[key] = wrap_with_marker(unwrap_marker(formatted_val, marker), marker)
        
        return label_context

    def _post_process_and_replace_content(self, doc):
        """
        Iterates through the document to find and process all placeholders,
        using template-type-specific font sizing based on the original font-sizing utilities.
        Also ensures DOH image is perfectly centered in its cell.
        """
        # Add markers for mini templates with classic types (weight units)
        if self.template_type == 'mini':
            self._add_weight_units_markers(doc)
        

        
        # Use template-type-specific font sizing
        self._post_process_template_specific(doc)

        # Clear blank cells for mini templates when they run out of values
        if self.template_type == 'mini':
            self._clear_blank_cells_in_mini_template(doc)

        # --- Convert |BR| markers to actual line breaks in all paragraphs ---
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        self._convert_br_markers_to_line_breaks(paragraph)
        
        # Also process paragraphs outside of tables
        for paragraph in doc.paragraphs:
            self._convert_br_markers_to_line_breaks(paragraph)
        
        # --- Fix paragraph spacing for ratio content to prevent excessive gaps ---
        self._fix_ratio_paragraph_spacing(doc)

        # --- Enforce Arial Bold for all text to ensure consistency across platforms ---
        from src.core.generation.docx_formatting import enforce_arial_bold_all_text
        enforce_arial_bold_all_text(doc)

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
                    # --- Center any inner tables in this cell ---
                    for inner_table in cell.tables:
                        inner_table.alignment = WD_TABLE_ALIGNMENT.CENTER
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
        # Define marker processing for all template types
        markers = [
            'DESC', 'PRODUCTBRAND_CENTER', 'PRICE', 'LINEAGE', 
            'THC_CBD', 'RATIO', 'WEIGHTUNITS', 'PRODUCTSTRAIN', 'DOH'
        ]
        
        # Process all markers in a single pass to avoid conflicts
        self._recursive_autosize_template_specific_multi(doc, markers)

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
            try:
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
<<<<<<< HEAD
                        content = final_content[marker_start:marker_end].strip()
=======
                        content = final_content[marker_start:marker_end]
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                        
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
                        if text_before.strip():
                            run = paragraph.add_run(text_before)
                            run.font.name = "Arial"
                            run.font.bold = True
                            run.font.size = Pt(12)  # Default size for non-marker text
                    
                    # Add the processed marker content (use the potentially modified content)
                    display_content = marker_data.get('display_content', marker_data['content'])
                    run = paragraph.add_run(display_content)
                    run.font.name = "Arial"
                    run.font.bold = True
                    run.font.size = marker_data['font_size']
                    
                    # Apply template-specific font size setting
                    set_run_font_size(run, marker_data['font_size'])
<<<<<<< HEAD
=======
                    # Debug log for Ratio marker font size
                    if marker_name == 'RATIO':
                        import logging
                        logging.warning(f"[RATIO FONT SIZE SET] Text: '{display_content}' | Font size: {marker_data['font_size']}")
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                    
                    current_pos = marker_data['end_pos']
                
                # Add any remaining text
                if current_pos < len(full_text):
                    text_after = full_text[current_pos:]
                    if text_after.strip():
                        run = paragraph.add_run(text_after)
                        run.font.name = "Arial"
                        run.font.bold = True
                        run.font.size = Pt(12)  # Default size for non-marker text
                
                # Convert |BR| markers to actual line breaks after marker processing
                self._convert_br_markers_to_line_breaks(paragraph)
                
                # Apply special formatting for specific markers
                for marker_name, marker_data in processed_content.items():
                    if 'PRODUCTBRAND' in marker_name:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    
                    # Center DOH content
                    if marker_name == 'DOH':
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    
                    # Special handling for lineage markers
                    if marker_name == 'LINEAGE':
                        content = marker_data['content']
                        # For classic types, left-justify the text
                        # For non-classic types, center the text
                        # We need to determine the product type from the context
                        # Since we can't access the record context here, we'll use a different approach
                        # We'll check if this is a classic lineage and assume it's for a classic product type
                        classic_lineages = [
                            "SATIVA", "INDICA", "HYBRID", "HYBRID/SATIVA", "HYBRID/INDICA", 
                            "CBD", "MIXED", "PARAPHERNALIA", "PARA"
                        ]
                        
                        # For classic lineages (SATIVA, INDICA, HYBRID, etc.), left-justify
                        # But exclude PARAPHERNALIA which should be centered
                        if content.upper() in classic_lineages and content.upper() != "PARAPHERNALIA":
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        else:
                            # For non-classic lineages and PARAPHERNALIA, center
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
<<<<<<< HEAD
=======
                        # --- NEW: Force left indent for horizontal, double, vertical ---
                        if self.template_type in {"horizontal", "double", "vertical"}:
                            paragraph.paragraph_format.left_indent = Inches(0.15)
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                
                self.logger.debug(f"Applied multi-marker processing for: {list(processed_content.keys())}")

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
        else:
            # No markers found, but still check for |BR| markers
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
<<<<<<< HEAD
                content = full_text[start_idx:end_idx].strip()
=======
                content = full_text[start_idx:end_idx]
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                
                # Use template-type-specific font sizing based on original functions
                font_size = self._get_template_specific_font_size(content, marker_name)
                
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
                
                # Convert |BR| markers to actual line breaks after adding content
                self._convert_br_markers_to_line_breaks(paragraph)
                
                # Handle special formatting for specific markers
                if marker_name in ['THC_CBD', 'RATIO', 'THC_CBD_LABEL']:
                    # Line spacing for THC: CBD: content across all templates
                    if content == 'THC: CBD:':
                        if self.template_type == 'vertical':
                            paragraph.paragraph_format.line_spacing = 2.0
                            # Add left upper alignment for vertical template
                            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        elif self.template_type == 'horizontal':
                            paragraph.paragraph_format.line_spacing = 0.9
                        elif self.template_type == 'mini':
                            paragraph.paragraph_format.line_spacing = 0.8
                        else:  # Default for other templates (double, etc.)
                            paragraph.paragraph_format.line_spacing = 1.0
                        
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

    def _convert_br_markers_to_line_breaks(self, paragraph):
        """
        Convert |BR| markers and \n characters in paragraph text to actual line breaks.
        This splits the text at |BR| markers or \n characters and creates separate runs for each part.
        """
        try:
            # Get all text from the paragraph
            full_text = "".join(run.text for run in paragraph.runs)
            
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
            paragraph.paragraph_format.line_spacing = 1.0
            
            # Add each part as a separate run, with line breaks between them
            for i, part in enumerate(parts):
                if part.strip():  # Only add non-empty parts
                    run = paragraph.add_run(part.strip())
                    run.font.name = "Arial"
                    run.font.bold = True
                    
                    # Apply the same font size as the original content
                    # We'll use a default size and let the marker processing handle specific sizing
                    run.font.size = Pt(12)
                    
                    # Add a line break after this part only if the next part is not empty
                    if i < len(parts) - 1 and parts[i + 1].strip():
                        # Use add_break() with WD_BREAK.LINE to create proper line breaks within the same paragraph
                        run.add_break(WD_BREAK.LINE)
            
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
                
                # For double template, ensure proper centering without overriding width settings
                if self.template_type == 'double':
                    # Ensure table alignment is set to center
                    table.alignment = WD_TABLE_ALIGNMENT.CENTER
                    # Skip width calculation since it's already set by _enforce_double_template_dimensions
                    continue
                
                # Calculate and set proper table width for perfect centering
<<<<<<< HEAD
                if self.template_type == 'vertical':
                    # For vertical template: 3 columns of 2.4 inches each = 7.2 inches total
                    total_table_width = 7.2
                elif self.template_type == 'horizontal':
                    # For horizontal template: 3 columns of 3.4/3 = 1.133 inches each = 3.4 inches total
                    total_table_width = 3.4
                elif self.template_type == 'mini':
                    # For mini template: 4 columns of 1.75 inches each = 7.0 inches total
                    total_table_width = 7.0
                else:
                    # Default fallback
                    total_table_width = 6.0
=======
                from src.core.constants import CELL_DIMENSIONS, GRID_LAYOUTS
                
                # Get individual cell dimensions and grid layout
                cell_dims = CELL_DIMENSIONS.get(self.template_type, {'width': 2.4, 'height': 2.4})
                grid_layout = GRID_LAYOUTS.get(self.template_type, {'rows': 3, 'cols': 3})
                
                # Calculate total table width: individual cell width * number of columns
                individual_cell_width = cell_dims['width']
                num_columns = grid_layout['cols']
                total_table_width = individual_cell_width * num_columns
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                
                # Set table width to ensure proper centering
                table.width = Inches(total_table_width)
                
<<<<<<< HEAD
                # Ensure table grid is properly set (skip for double template since it's handled by _enforce_double_template_dimensions)
                if self.template_type != 'double':
=======
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
                
                # Ensure table grid is properly set (skip for double template since it's handled by _enforce_double_template_dimensions)
                # Skip width setting for horizontal templates since they should already be correct from template expansion
                if self.template_type != 'double' and self.template_type != 'horizontal':
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                    tblGrid = table._element.find(qn('w:tblGrid'))
                    if tblGrid is not None:
                        # Remove existing grid and recreate with proper widths
                        tblGrid.getparent().remove(tblGrid)
                    
                    # Create new grid with proper column widths
                    tblGrid = OxmlElement('w:tblGrid')
<<<<<<< HEAD
                    if self.template_type == 'vertical':
                        col_width = total_table_width / 3  # 2.4 inches per column
                    elif self.template_type == 'horizontal':
                        col_width = total_table_width / 3  # 1.133 inches per column
                    elif self.template_type == 'mini':
                        col_width = total_table_width / 4  # 1.75 inches per column
                    else:
                        col_width = total_table_width / 3
=======
                    # Use individual cell width directly from CELL_DIMENSIONS
                    col_width = cell_dims['width']
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
                    
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
        from src.core.generation.unified_font_sizing import get_font_size
        
        # Map marker names to field types
        marker_to_field_type = {
            'DESC': 'description',
            'PRODUCTBRAND_CENTER': 'brand',
            'PRICE': 'price',
            'LINEAGE': 'lineage',
            'THC_CBD': 'thc_cbd',
            'RATIO': 'ratio',
            'WEIGHTUNITS': 'weight',
            'THC_CBD_LABEL': 'thc_cbd',
            'PRODUCTSTRAIN': 'strain',
            'DOH': 'doh'
        }
        
<<<<<<< HEAD
        # Special handling for RATIO marker in mini templates with classic types
        # If it's a RATIO marker and the content looks like weight units, treat it as weight
        if marker_name == 'RATIO' and self.template_type == 'mini':
            # Check if content looks like weight units (contains 'g' or 'mg')
            if content and ('g' in content.lower() or 'mg' in content.lower()):
                field_type = 'weight'
            else:
                field_type = marker_to_field_type.get(marker_name, 'default')
=======
        # Always set complexity_type before use
        complexity_type = 'mini' if self.template_type == 'mini' else 'standard'
        # Use correct field type for each marker
        if marker_name == 'RATIO':
            field_type = 'ratio'
            content_for_complexity = content.replace('\n', ' ').replace('\r', ' ')
            return get_font_size(content_for_complexity, field_type, self.template_type, self.scale_factor, complexity_type)
        elif marker_name in ['THC_CBD', 'THC_CBD_LABEL']:
            field_type = 'thc_cbd'
            content_for_complexity = content.replace('\n', ' ').replace('\r', ' ')
            return get_font_size(content_for_complexity, field_type, self.template_type, self.scale_factor, complexity_type)
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
        else:
            field_type = marker_to_field_type.get(marker_name, 'default')
        
        # Use unified font sizing with appropriate complexity type
<<<<<<< HEAD
        complexity_type = 'mini' if self.template_type == 'mini' else 'standard'
=======
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
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
        Format ratio for classic types. Handles various input formats and converts them to the standard display format.
        """
        if not text:
            return text
        
        # Clean the text and normalize
        text = text.strip()
        
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

    def _enforce_double_template_dimensions(self, table):
        """
        Enforce fixed cell dimensions for the double template, preserving the 1.75" width.
        """
        try:
            # FORCE: Double template cell width to exactly 1.75 inches
            col_width = 1.75  # Hardcoded override
            
            # Ensure table is properly centered
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            
            # Ensure table is not auto-fit
            table.autofit = False
            if hasattr(table, 'allow_autofit'):
                table.allow_autofit = False
            # Calculate and set proper table width for perfect centering
            total_table_width = col_width * 4  # 4 columns of 1.75 inches each = 7.0 inches total
            table.width = Inches(total_table_width)
            
            # Remove any existing table grid
            existing_grid = table._element.find(qn('w:tblGrid'))
            if existing_grid is not None:
                existing_grid.getparent().remove(existing_grid)
            
            # Create new grid with proper column widths
            tblGrid = OxmlElement('w:tblGrid')
            for _ in range(4):  # 4 columns
                gridCol = OxmlElement('w:gridCol')
                gridCol.set(qn('w:w'), str(int(col_width * 1440)))  # 1.75 inches in twips
                tblGrid.append(gridCol)
            table._element.insert(0, tblGrid)
            
            # Enforce fixed cell dimensions for each cell
            for row in table.rows:
                for cell in row.cells:
                    tcPr = cell._tc.get_or_add_tcPr()
                    tcW = tcPr.find(qn('w:tcW'))
                    if tcW is None:
                        tcW = OxmlElement('w:tcW')
                        tcPr.append(tcW)
                    tcW.set(qn('w:w'), str(int(col_width * 1440))) # 1.75 inches in twips
                    tcW.set(qn('w:type'), 'dxa')
                row.height = Inches(2.5)
                row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
        except Exception as e:
            self.logger.error(f"Error enforcing double template dimensions: {e}")

__all__ = ['get_font_scheme', 'TemplateProcessor']