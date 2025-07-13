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
                cell_width = 1.7  # ENFORCE 1.7"
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
                fixed_col_width = str(int(1.7 * 1440))
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
                        cell.width = Inches(1.7)
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
                        cell.width = Inches(1.7)
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
            # Set table properties to fixed layout
            tblPr = new_table._element.find(qn('w:tblPr'))
            if tblPr is None:
                tblPr = OxmlElement('w:tblPr')
            tblLayout = OxmlElement('w:tblLayout')
            tblLayout.set(qn('w:type'), 'fixed')
            tblPr.append(tblLayout)
            spacing = OxmlElement('w:tblCellSpacing')
            spacing.set(qn('w:w'), '0')
            spacing.set(qn('w:type'), 'dxa')
            tblPr.append(spacing)
            new_table._element.insert(0, tblPr)
            # Set exact column widths (1.7 inches each)
            col_width_twips = str(int(1.7 * 1440))
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
                    cell.width = Inches(1.7)
                    label_num += 1
            # Disable autofit
            new_table.autofit = False
            if hasattr(new_table, 'allow_autofit'):
                new_table.allow_autofit = False
            # Enforce fixed dimensions
            enforce_fixed_cell_dimensions(new_table, 'double')
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

            # Ensure proper table centering and document setup
            self._ensure_proper_centering(rendered_doc)

            # --- FINAL: For double template, force all widths to 1.7" ---
            if self.template_type == 'double':
                self._force_double_table_width(rendered_doc)

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
            # Classic: wrap with RATIO marker
            label_context['Ratio_or_THC_CBD'] = wrap_with_marker(unwrap_marker(label_context['Ratio_or_THC_CBD'], 'RATIO'), 'RATIO')
        elif label_context.get('Ratio_or_THC_CBD') == "THC:\nCBD:":
            # Non-classic: wrap with THC_CBD_LABEL marker
            label_context['Ratio_or_THC_CBD'] = wrap_with_marker(unwrap_marker(label_context['Ratio_or_THC_CBD'], 'THC_CBD_LABEL'), 'THC_CBD_LABEL')
        else:
            # Existing logic for other cases
            if label_context.get('Ratio_or_THC_CBD'):
                label_context['Ratio_or_THC_CBD'] = wrap_with_marker(unwrap_marker(label_context['Ratio_or_THC_CBD'], 'RATIO'), 'RATIO')

        # Wrap text fields with markers
        if label_context.get('ProductBrand'):
            label_context['ProductBrand'] = wrap_with_marker(
                unwrap_marker(label_context['ProductBrand'], 'PRODUCTBRAND_CENTER'),
                'PRODUCTBRAND_CENTER'
            )
        if label_context.get('Price'):
            label_context['Price'] = wrap_with_marker(unwrap_marker(label_context['Price'], 'PRICE'), 'PRICE')
        if label_context.get('Lineage'):
            # Include product type information in the lineage marker for centering decisions
            product_type = label_context.get('ProductType', '').strip().lower() or label_context.get('Product Type*', '').strip().lower()
            classic_types = ["flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge"]
            is_classic_type = product_type in classic_types
            lineage_with_type = f"{label_context['Lineage']}_PRODUCT_TYPE_{product_type}_IS_CLASSIC_{is_classic_type}"
            label_context['Lineage'] = wrap_with_marker(unwrap_marker(lineage_with_type, 'LINEAGE'), 'LINEAGE')
        if label_context.get('Ratio_or_THC_CBD'):
            label_context['Ratio_or_THC_CBD'] = wrap_with_marker(unwrap_marker(label_context['Ratio_or_THC_CBD'], 'RATIO'), 'RATIO')
        if label_context.get('DescAndWeight'):
            label_context['DescAndWeight'] = wrap_with_marker(unwrap_marker(label_context['DescAndWeight'], 'DESC'), 'DESC')
        
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
                # Add line breaks before all hyphens for non-classic types
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
        return doc

    def _post_process_template_specific(self, doc):
        """
        Apply template-type-specific font sizing to all markers in the document.
        Uses the original font-sizing functions based on template type.
        """
        # Define marker processing for all template types
        markers = [
            'DESC', 'PRODUCTBRAND_CENTER', 'PRICE', 'LINEAGE', 
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
                
                # Special handling for double template: check for long words
                if self.template_type == 'double' and content:
                    words = content.split()
                    has_long_word = any(len(word) > 11 for word in words)
                    if has_long_word:
                        # Set font size to 16pt for long words in double template
                        font_size = Pt(16)
                        # Remove markers and apply font size
                        for run in paragraph.runs:
                            run.text = run.text.replace(start_marker, "").replace(end_marker, "")
                            run.font.size = font_size
                        self.logger.debug(f"Applied 16pt font for long word in double template: '{content[:50]}...'")
                        return
                
                # Get template-specific font size
                font_size = self._get_template_specific_font_size(content, marker_name)
                
                # Remove markers and apply font size
                for run in paragraph.runs:
                    run.text = run.text.replace(start_marker, "").replace(end_marker, "")
                    run.font.size = font_size
                
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
                
                # Calculate and set proper table width for perfect centering
                if self.template_type == 'double':
                    total_table_width = 6.8
                    col_width = 1.7  # ENFORCE 1.7" per column
                elif self.template_type == 'vertical':
                    total_table_width = 6.75
                    col_width = total_table_width / 3
                elif self.template_type == 'horizontal':
                    total_table_width = 3.3
                    col_width = total_table_width / 3
                elif self.template_type == 'mini':
                    total_table_width = 7.0
                    col_width = total_table_width / 4
                else:
                    total_table_width = 6.75
                    col_width = total_table_width / 3
                
                # Set table grid with proper column widths
                tblGrid = OxmlElement('w:tblGrid')
                for _ in range(len(table.columns)):
                    gridCol = OxmlElement('w:gridCol')
                    # ENFORCE 1.7" for double template
                    if self.template_type == 'double':
                        gridCol.set(qn('w:w'), str(int(1.7 * 1440)))
                    else:
                        gridCol.set(qn('w:w'), str(int(col_width * 1440)))
                    tblGrid.append(gridCol)
                table._element.insert(0, tblGrid)
                
                # Force every cell's width for double template
                if self.template_type == 'double':
                    for row in table.rows:
                        for cell in row.cells:
                            cell.width = Inches(1.7)
                    
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
        """Remove all table styles and force every column and cell width to 1.7 inches for double template."""
        for table in doc.tables:
            # Remove table style
            table.style = None
            # Set table autofit off
            table.autofit = False
            if hasattr(table, 'allow_autofit'):
                table.allow_autofit = False
            # Set table grid
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            tblGrid = OxmlElement('w:tblGrid')
            for _ in range(len(table.columns)):
                gridCol = OxmlElement('w:gridCol')
                gridCol.set(qn('w:w'), str(int(1.7 * 1440)))
                tblGrid.append(gridCol)
            table._element.insert(0, tblGrid)
            # Set every cell width
            for row in table.rows:
                for cell in row.cells:
                    cell.width = Inches(1.7)
        return doc

__all__ = ['get_font_scheme', 'TemplateProcessor']