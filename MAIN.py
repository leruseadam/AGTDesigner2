import os
import sys
import platform
import subprocess
import pandas as pd
import concurrent.futures
import numpy as np
import re
from io import BytesIO
from pathlib import Path
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm, Pt, RGBColor
from docx import Document
from docxcompose.composer import Composer
from docx.oxml.ns import qn
from docx.oxml.shared import OxmlElement
import tkinter as tk
from tkinter import filedialog, messagebox
import logging
import multiprocessing
import time
import datetime
import html  # For unescaping HTML entities
import threading
from AppKit import NSApplication, NSCriticalRequest
from xml.sax.saxutils import escape, unescape
from docx.enum.text import WD_ALIGN_PARAGRAPH
from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
NSRunningApplication.currentApplication().activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from copy import deepcopy


# Fix missing import for docxcompose
import docxcompose

docxcompose_templates = (os.path.join(os.path.dirname(docxcompose.__file__), "templates"), "docxcompose/templates")

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ---------- File Handling and Preprocessing Functions ----------
def open_file(file_path):
    if not os.path.exists(file_path):
        logging.error("File not found: %s", file_path)
        return
    try:
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", file_path])
        else:
            subprocess.Popen(["xdg-open", file_path])
    except Exception as e:
        logging.error("Error opening file: %s", e)


# ---------- Global Variables ----------
global_df = None  # Global DataFrame after file upload

# ---------- Font Schemes ----------
FONT_SCHEME_HORIZONTAL = {
    "DESC": {"base_size": 28, "min_size": 12, "max_length": 100},
    "PRIC": {"base_size": 36, "min_size": 20, "max_length": 20},
    "LINEAGE": {"base_size": 20, "min_size": 12, "max_length": 30},
    "LINEAGE_CENTER": {"base_size": 18, "min_size": 12, "max_length": 30},
    "THC_CBD": {"base_size": 12, "min_size": 10, "max_length": 50},
    "RATIO": {"base_size": 16, "min_size": 8, "max_length": 30},
    "WEIGHT": {"base_size": 18, "min_size": 10, "max_length": 20},
    "UNITS": {"base_size": 18, "min_size": 10, "max_length": 20},
    "PRODUCTSTRAIN": {"base_size": 22, "min_size": 14, "max_length": 40}  # Updated value
}
FONT_SCHEME_VERTICAL = {
    "DESC": {"base_size": 23, "min_size": 12, "max_length": 100},
    "PRIC": {"base_size": 36, "min_size": 20, "max_length": 20},
    "LINEAGE": {"base_size": 18, "min_size": 12, "max_length": 30},
    "LINEAGE_CENTER": {"base_size": 18, "min_size": 12, "max_length": 30},
    "THC_CBD": {"base_size": 12, "min_size": 10, "max_length": 50},
    "RATIO": {"base_size": 8, "min_size": 10, "max_length": 30},
    "WEIGHT": {"base_size": 16, "min_size": 10, "max_length": 20},
    "UNITS": {"base_size": 16, "min_size": 10, "max_length": 20},
    "PRODUCTSTRAIN": {"base_size": 2, "min_size": 2, "max_length": 40}  # Updated value
}


# ---------- Helper Functions for Formatting ----------
def remove_leading_empty_paragraphs(doc):
    while doc.paragraphs and not doc.paragraphs[0].text.strip():
        p = doc.paragraphs[0]._element
        p.getparent().remove(p)


def set_vertical_alignment(doc, alignment='center'):
    """
    Sets the vertical alignment for all sections in the document.
    Valid values for alignment are 'top', 'center', 'both', or 'bottom'.
    """
    for section in doc.sections:
        sectPr = section._sectPr
        vAlign = sectPr.find(qn('w:vAlign'))
        if vAlign is None:
            vAlign = OxmlElement('w:vAlign')
            sectPr.append(vAlign)
        vAlign.set(qn('w:val'), alignment)


def expand_template_to_3x3(template_path):
    doc = Document(template_path)
    if not doc.tables:
        raise ValueError("The template must contain at least one table.")
    old_table = doc.tables[0]
    source_cell = old_table.cell(0, 0)
    source_cell_xml = deepcopy(source_cell._tc)

    # Remove the original table.
    tbl_element = old_table._element
    tbl_element.getparent().remove(tbl_element)

    # Remove any empty paragraphs at the top.
    while doc.paragraphs and not doc.paragraphs[0].text.strip():
        p = doc.paragraphs[0]._element
        p.getparent().remove(p)

    # Create a new 3x3 table.
    new_table = doc.add_table(rows=3, cols=3)
    new_table.autofit = True
    from docx.enum.table import WD_TABLE_ALIGNMENT
    new_table.alignment = WD_TABLE_ALIGNMENT.CENTER  # Center horizontally

    for i in range(3):
        for j in range(3):
            label_num = i * 3 + j + 1
            cell = new_table.cell(i, j)
            cell._tc.clear_content()
            new_tc = deepcopy(source_cell_xml)
            for text_el in new_tc.iter():
                if text_el.tag == qn('w:t') and text_el.text and "Label1" in text_el.text:
                    text_el.text = text_el.text.replace("Label1", f"Label{label_num}")
            cell._tc.clear_content()
            cell._tc.extend(new_tc.xpath("./*"))

    # Center the section vertically using our helper function.
    set_vertical_alignment(doc, 'center')

    temp_path = os.path.join(os.path.dirname(template_path), "expanded_template.docx")
    doc.save(temp_path)
    return temp_path



def adjust_productstrain_font(doc, desired_size):
    """
    For cells that originally held a Product Strain marker,
    clear the marker and set the font size to the desired value.
    """
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = cell.text
                if "PRODUCTSTRAIN_START" in cell_text:
                    # Extract the original value
                    value = get_marker_value(cell_text, "PRODUCTSTRAIN")
                    # Clear the paragraph(s)
                    for para in cell.paragraphs:
                        # Remove all runs
                        p_element = para._element
                        for child in list(p_element):
                            p_element.remove(child)
                        # Add new run with the desired font size
                        run = para.add_run(value)
                        run.font.size = Pt(desired_size)
                        run.font.name = "Arial"  # Adjust as needed
    return doc



def format_price(p):
    """
    Format a price such that:
      - If the price is exactly an integer (e.g. 100.0), returns "'100"
      - Otherwise, returns the full float value (e.g. 2.50 becomes "'2.5")
    Any leading '$' is removed.
    The leading apostrophe forces Excel to treat the cell as text.
    """
    try:
        value = str(p).strip().lstrip("$")
        val = float(value)
        if val.is_integer():
            return f"'{int(val)}"
        else:
            s = str(val).rstrip("0").rstrip(".")
            return f"'{s}"
    except Exception:
        return f"'{str(p).strip().lstrip('$')}"

def format_weight(w):
    try:
        val = float(w)
        return str(int(val)) if val.is_integer() else str(val)
    except Exception:
        return str(w)

def sanitize_filename(s):
    # Only keep allowed characters: letters, digits, space, underscore, hyphen, and ampersand.
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _-&"
    return "".join(ch for ch in s if ch in allowed).replace(" ", "_")

def preprocess_excel(file_path, filters=None):
    print(f"Processing Excel file: {file_path}")
    logging.debug("Processing Excel file: %s", file_path)

    df = pd.read_excel(file_path, engine="openpyxl")
    df.drop_duplicates(inplace=True)

    # Remove rows where Product Type* is "Samples - Educational" or "Sample - Vendor"
    if "Product Type*" in df.columns:
        exclude_types = ["Samples - Educational", "Sample - Vendor"]
        df = df[~df["Product Type*"].isin(exclude_types)]

    rename_map = {
        "Weight Unit* (grams/gm or ounces/oz)": "Units",
        "Quantity*": "Length",
        "Price* (Tier Name for Bulk)": "Price",
        "Vendor/Supplier*": "Vendor",
        "DOH Compliant (Yes/No)": "DOH",
        "Concentrate Type": "Ratio"
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # Standardize Units
    if "Units" in df.columns:
        df["Units"] = df["Units"].astype(str).replace({"ounces": "oz", "grams": "g"}, regex=True)

    # Normalize Lineage
    replacement_map = {
        "indica_hybrid": "HYBRID/INDICA",
        "sativa_hybrid": "HYBRID/SATIVA",
        "sativa": "SATIVA",
        "hybrid": "HYBRID",
        "indica": "INDICA"
    }
    df["Lineage"] = df["Lineage"].astype(str).replace(replacement_map).fillna("HYBRID")
    if "Product Type*" in df.columns and "Lineage" in df.columns and "Product Brand" in df.columns:
        df.loc[~df["Product Type*"].isin(["Flower", "Vape Cartridge", "Concentrate", "Solventless Concentrate"]),
               "Lineage"] = df["Product Brand"].astype(str).str.upper()

    # Extract Description and Ratio from Product Name
    if "Product Name*" in df.columns:
        last_row = df["Product Name*"].last_valid_index()
        if "Product Strain" in df.columns:
            df.loc[1:last_row, "Product Strain"] = df["Product Name*"].astype(str).apply(
                lambda x: "CBD Blend" if ":" in x else "Mixed"
            )
        else:
            print("Error: 'Product Strain' column not found.")

        df["Length"] = df["Product Name*"].astype(str).apply(len)
        df["Description"] = df["Product Name*"].astype(str).apply(
            lambda x: x.split(" by")[0] if " by" in x else x
        )
        df["Ratio"] = df["Product Name*"].astype(str).apply(
            lambda x: x.split("- ", 1)[1].strip() if "- " in x else np.nan
        )
        df["Ratio"] = df["Ratio"].astype(str).str.replace(" / ", " ", regex=True)
    else:
        print("Error: 'Product Name*' column not found.")

    # Limit columns
    if len(df.columns) > 41:
        df = df.iloc[:, :41]

    # Format Weight
    if "Weight*" in df.columns:
        def remove_trailing_zero(x):
            try:
                num = float(x)
                return str(int(num)) if num.is_integer() else str(num)
            except Exception:
                return x
        df["Weight*"] = df["Weight*"].apply(remove_trailing_zero)

    if "Weight*" in df.columns and "Units" in df.columns:
        df["CombinedWeight"] = df["Weight*"] + df["Units"].astype(str)

    # Format Price
    if "Price" in df.columns:
        df["Price"] = df["Price"].apply(lambda x: format_price(x) if pd.notnull(x) else "")
        df["Price"] = df["Price"].astype("string")

    # Generate output file name
    today = datetime.datetime.today().strftime("%Y-%m-%d")

    def safe(val):
        return str(val).replace(" ", "").replace("/", "").replace("-", "").replace("*", "") if val and val != "All" else None

    suffix_parts = [safe(filters.get(k)) for k in ["product_type", "lineage", "brand", "vendor", "weight", "strain"]] if filters else []
    suffix = "_".join([part for part in suffix_parts if part]) or "all"

    base_file_name = f"{today}_{suffix}.xlsx"
    downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
    new_file_name = os.path.join(downloads_folder, base_file_name)

    # Save file
    df.to_excel(new_file_name, index=False, engine="openpyxl")
    print(f"Preprocessed file saved as {new_file_name}")

    # Force Excel to treat Price column as text
    import openpyxl
    from openpyxl.utils import get_column_letter
    wb = openpyxl.load_workbook(new_file_name)
    ws = wb.active
    if "Price" in df.columns:
        col_index = list(df.columns).index("Price") + 1
        col_letter = get_column_letter(col_index)
        for cell in ws[col_letter]:
            cell.number_format = "@"
    wb.save(new_file_name)

    return new_file_name


def chunk_records(records, chunk_size=9):
    for i in range(0, len(records), chunk_size):
        yield records[i:i+chunk_size]

def no_filters_selected():
    filters = [
        product_type_filter_var.get(),
        lineage_filter_var.get(),
        product_brand_filter_var.get(),
        vendor_filter_var.get(),
        weight_filter_var.get(),
        product_strain_filter_var.get()
    ]
    return all(f == "All" for f in filters)




# ---------- Full Process Function (Excel and Word) ----------
def run_full_process(template_type):
    """
    Process the Excel file and generate a Word document.
    The output file names are based on today's date, the template type (horizontal/vertical),
    and include the word "tags".
    """
    file_path_val = file_entry.get()
    if not file_path_val:
        messagebox.showerror("Error", "Please select a data file.")
        return

    global global_df

    # (A) Preprocess Excel file
    filters = {
        "product_type": product_type_filter_var.get(),
        "lineage": lineage_filter_var.get(),
        "brand": product_brand_filter_var.get(),
        "vendor": vendor_filter_var.get(),
        "weight": weight_filter_var.get(),
        "strain": product_strain_filter_var.get()
    }
    new_excel_file = preprocess_excel(file_path_val, filters)
    global_df = pd.read_excel(new_excel_file, engine="openpyxl")

    # (B) Filter based on selected dropdowns
    df = global_df.copy()
    if product_type_filter_var.get() != "All":
        df = df[df["Product Type*"] == product_type_filter_var.get()]
    if lineage_filter_var.get() != "All":
        df = df[df["Lineage"] == lineage_filter_var.get()]
    if product_brand_filter_var.get() != "All" and "Product Brand" in df.columns:
        df = df[df["Product Brand"] == product_brand_filter_var.get()]
    if vendor_filter_var.get() != "All" and "Vendor" in df.columns:
        df = df[df["Vendor"] == vendor_filter_var.get()]
    if weight_filter_var.get() != "All" and "CombinedWeight" in df.columns:
        df = df[df["CombinedWeight"] == weight_filter_var.get()]
    if product_strain_filter_var.get() != "All" and "Product Strain" in df.columns:
        df = df[df["Product Strain"] == product_strain_filter_var.get()]

    if "Price" in df.columns:
        df["Price"] = df["Price"].apply(lambda x: x.lstrip("'") if isinstance(x, str) else x)

    # Filter by selected checkboxes
    selected_names = [name for name, var in product_check_vars.items() if var.get()]
    if "Product Name*" in df.columns:
        df = df[df["Product Name*"].isin(selected_names)]

    records = df.to_dict(orient="records")

    if not records:
        messagebox.showerror("Error", "No records found after filtering.")
        return

    # (C) Pick template and font scheme
    if template_type == "horizontal":
        base_template = resource_path("templates/templateHLong.docx")
        template_file = expand_template_to_3x3(base_template)
        current_font_scheme = FONT_SCHEME_HORIZONTAL
        orientation = "horizontal"
    else:
        base_template = resource_path("templates/vertical.docx")
        template_file = expand_template_to_3x3(base_template)
        current_font_scheme = FONT_SCHEME_VERTICAL  # Add this line
        orientation = "vertical"

    # (D) Process label chunks using threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        docs_bytes = list(executor.map(
            process_chunk,
            [(chunk, template_file, current_font_scheme, orientation) for chunk in chunk_records(records)]
        ))

    docs = [Document(BytesIO(b)) for b in docs_bytes if b]
    if not docs:
        messagebox.showerror("Error", "No documents were generated.")
        return

    # (E) Merge documents
    master_doc = docs[0]
    composer = Composer(master_doc)
    for sub_doc in docs[1:]:
        composer.append(sub_doc)

    # (F) Create final file name
    today = datetime.datetime.today().strftime("%Y-%m-%d")

    def safe(val):
        return str(val).replace(" ", "").replace("/", "").replace("-", "").replace("*", "") if val and val != "All" else None

    suffix_parts = [
        safe(product_type_filter_var.get()),
        safe(lineage_filter_var.get()),
        safe(product_brand_filter_var.get()),
        safe(vendor_filter_var.get()),
        safe(weight_filter_var.get()),
        safe(product_strain_filter_var.get())
    ]
    suffix = "_".join([part for part in suffix_parts if part])
    suffix = suffix or "all"

    doc_name = f"{today}_{orientation}_{suffix}_tags.docx"
    doc_path = os.path.join(os.path.expanduser("~"), "Downloads", doc_name)

    # (G) Save and open Word document
    master_doc.save(doc_path)
    open_file(doc_path)

    messagebox.showinfo(
        "Success",
        f"Word file saved as:\n{doc_path}"
    )

    # ---------------- Font Logic ----------------
def wrap_with_marker(text, marker):
    safe_text = str(text).replace('&', '&amp;')  # manually escape ampersand only
    return f"{marker.upper()}_START{safe_text}{marker.upper()}_END"


def get_thresholded_font_size_by_word_count(text, orientation='vertical'):
    word_count = len(text.split())
    if orientation.lower() == 'vertical':
        if word_count < 4:
            return Pt(28)
        elif word_count < 6:
            return Pt(25)
        elif word_count < 8:
            return Pt(21)
        elif word_count < 10:
            return Pt(19)
        else:
            return Pt(22)
    elif orientation.lower() == 'horizontal':
        if word_count < 2:
            return Pt(32)
        elif word_count < 4:
            return Pt(28)
        elif word_count < 5:
            return Pt(26)
        elif word_count < 6:
            return Pt(24)
        elif word_count < 9:
            return Pt(22)
        else:
            return Pt(20)
    else:
        if word_count < 5:
            return Pt(34)
        elif word_count < 7:
            return Pt(30)
        elif word_count < 10:
            return Pt(28)
        elif word_count < 15:
            return Pt(24)
        else:
            return Pt(22)

def get_thresholded_font_size_ratio(text, orientation='vertical'):
    word_count = len(text.split())
    if orientation.lower() == 'vertical':
        if word_count <= 2:
            return Pt(16)
        elif word_count <= 4:
            return Pt(14)
        elif word_count <= 8:
            return Pt(11)
        else:
            return Pt(10)
    elif orientation.lower() == 'horizontal':
        if word_count < 4:
            return Pt(16)
        elif word_count < 8:
            return Pt(11)
        elif word_count < 10:
            return Pt(10)
        elif word_count < 15:
            return Pt(8)
        else:
            return Pt(8)
    else:
        if word_count < 3:
            return Pt(16)
        elif word_count < 7:
            return Pt(12)
        elif word_count < 10:
            return Pt(8)
        else:
            return Pt(10)

def get_thresholded_font_size_brand(text, orientation='vertical'):
    word_count = len(text.split())
    if orientation.lower() == 'vertical':
        if word_count <= 3:
            return Pt(20)
        elif word_count <= 5:
            return Pt(18)
        elif word_count <= 7:
            return Pt(16)
        else:
            return Pt(14)
    elif orientation.lower() == 'horizontal':
        if word_count < 2:
            return Pt(20)
        elif word_count < 3:
            return Pt(18)
        elif word_count < 4:
            return Pt(16)
        else:
            return Pt(14)
    else:
        if word_count <= 3:
            return Pt(22)
        elif word_count <= 5:
            return Pt(20)
        elif word_count <= 7:
            return Pt(18)
        else:
            return Pt(16)

def set_run_font_size(run, font_size):
    run.font.size = None
    run.font.size = font_size
    sz_val = str(int(font_size.pt * 2))
    rPr = run._element.get_or_add_rPr()
    sz = rPr.find(qn('w:sz'))
    if sz is None:
        sz = OxmlElement('w:sz')
        rPr.append(sz)
    sz.set(qn('w:val'), sz_val)

def autosize_field_in_paragraph(para, marker_start, marker_end, font_params, orientation, font_name="Arial", bold=True):
    full_text = "".join([run.text for run in para.runs])
    if marker_start in full_text and marker_end in full_text:
        try:
            field_text = full_text.split(marker_start)[1].split(marker_end)[0].strip()
        except IndexError:
            return

        # Use a fixed size for Product Strain and autosize for others
        if marker_start == "PRODUCTSTRAIN_START":
            new_size_val = Pt(font_params["base_size"])
        elif marker_start == "DESC_START":
            new_size_val = get_thresholded_font_size_by_word_count(field_text, orientation)
        elif marker_start == "RATIO_START":
            new_size_val = get_thresholded_font_size_ratio(field_text, orientation)
        else:
            length = len(field_text)
            base_size = font_params["base_size"]
            max_length = font_params["max_length"]
            min_size = font_params["min_size"]
            if length <= max_length:
                new_size_val = Pt(base_size)
            else:
                new_size_val = Pt(max(min_size, base_size * (max_length / length)))

        new_text = unescape(full_text.replace(marker_start, "").replace(marker_end, ""))
        p_element = para._element
        for child in list(p_element):
            p_element.remove(child)
        new_run = para.add_run(new_text)
        new_run.font.size = new_size_val
        new_run.font.name = font_name
        new_run.font.bold = bold
        set_run_font_size(new_run, new_size_val)
        if marker_start == "LINEAGE_CENTER_START":
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER



def autosize_field_recursive(element, marker_start, marker_end, font_params, orientation, font_name="Arial", bold=True):
    for para in element.paragraphs:
        autosize_field_in_paragraph(para, marker_start, marker_end, font_params, orientation, font_name, bold)
    for table in element.tables:
        for row in table.rows:
            for cell in row.cells:
                autosize_field_recursive(cell, marker_start, marker_end, font_params, orientation, font_name, bold)

def autosize_fields(doc, font_scheme, orientation):
    autosize_field_recursive(doc, "DESC_START", "DESC_END", font_scheme["DESC"], orientation)
    autosize_field_recursive(doc, "PRIC_START", "PRIC_END", font_scheme["PRIC"], orientation)
    autosize_field_recursive(doc, "LINEAGE_START", "LINEAGE_END", font_scheme["LINEAGE"], orientation)
    autosize_field_recursive(doc, "LINEAGE_CENTER_START", "LINEAGE_CENTER_END", font_scheme["LINEAGE_CENTER"], orientation)
    autosize_field_recursive(doc, "THC_CBD_START", "THC_CBD_END", font_scheme["THC_CBD"], orientation)
    autosize_field_recursive(doc, "RATIO_START", "RATIO_END", font_scheme["RATIO"], orientation)
    autosize_field_recursive(doc, "WEIGHT_START", "WEIGHT_END", font_scheme["WEIGHT"], orientation)
    autosize_field_recursive(doc, "UNITS_START", "UNITS_END", font_scheme["UNITS"], orientation)
    autosize_field_recursive(doc, "PRODUCTSTRAIN_START", "PRODUCTSTRAIN_END", font_scheme["PRODUCTSTRAIN"], orientation)

def set_cell_background(cell, color_hex):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), color_hex)
    tcPr.append(shd)

def set_font_color_white(cell):
    for para in cell.paragraphs:
        for run in para.runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.highlight_color = None

def apply_conditional_formatting(doc):
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.strip().upper()  # Normalize text
                if "SATIVA" in text:
                    set_cell_background(cell, "ED4123")
                    set_font_color_white(cell)
                elif "INDICA" in text:
                    set_cell_background(cell, "9900FF")
                    set_font_color_white(cell)
                elif "HYBRID" in text:
                    set_cell_background(cell, "009900")
                    set_font_color_white(cell)
                elif text == "CBD BLEND":  # Exact match for "CBD Blend"
                    set_cell_background(cell, "F1C232")
                    set_font_color_white(cell)
                elif "MIXED" in text:
                    set_cell_background(cell, "0021F5")
                    set_font_color_white(cell)
                else:
                    set_cell_background(cell, "FFFFFF")
                    set_font_color_white(cell)
    return doc


def process_chunk(args):
    chunk, template_path, font_scheme, orientation = args
    tpl = DocxTemplate(template_path)
    context = {}
    doh_image_path = resource_path(os.path.join("templates", "DOH.png"))

    for i in range(9):
        label_data = {}
        if i < len(chunk):
            row = chunk[i]
            doh_value = str(row.get("DOH", "")).strip()
            label_data["DOH"] = InlineImage(tpl, doh_image_path, width=Mm(12 if orientation == 'vertical' else 14)) if doh_value == "Yes" else ""
            label_data["Price"] = wrap_with_marker(f"${row.get('Price', '')}", "PRIC")
            product_type = str(row.get("Product Type*", "")).strip()
            lineage_text = row.get("Lineage", "")
            normalized_type = product_type.title().strip()

            if normalized_type in ["Flower", "Vape Cartridge", "Concentrate", "Solventless Concentrate"]:
                label_data["Lineage"] = wrap_with_marker(lineage_text, "LINEAGE")
                label_data["Ratio_or_THC_CBD"] = wrap_with_marker("THC:\n\nCBD:", "THC_CBD")
            else:
                label_data["Lineage"] = wrap_with_marker(lineage_text, "LINEAGE_CENTER")
                label_data["Ratio_or_THC_CBD"] = wrap_with_marker(row.get("Ratio", ""), "RATIO")

            label_data["Description"] = wrap_with_marker(row.get("Description", ""), "DESC")
            label_data["ProductStrain"] = wrap_with_marker(row.get("Product Strain", ""), "PRODUCTSTRAIN")

            try:
                weight_val = float(row.get("Weight*", ""))
            except:
                weight_val = None
            units_val = row.get("Units", "")
            if weight_val is not None and units_val:
                weight_str = f"{weight_val:.2f}".rstrip("0").rstrip(".")
                weight_units = f" -\u00A0{weight_str}{units_val}"
            else:
                weight_units = ""
            label_data["WeightUnits"] = weight_units
        else:
            label_data = {
                "DOH": "", "Description": "", "Price": "", "Lineage": "",
                "Ratio_or_THC_CBD": "", "WeightUnits": "", "ProductStrain": ""
            }

        context[f"Label{i+1}"] = label_data

    tpl.render(context)
    buffer = BytesIO()
    tpl.docx.save(buffer)
    doc = Document(BytesIO(buffer.getvalue()))
    autosize_fields(doc, font_scheme, orientation)
    apply_conditional_formatting(doc)
    final_buffer = BytesIO()
    doc.save(final_buffer)
    return final_buffer.getvalue()



def populate_filter_dropdowns():
    global global_df, product_type_option, lineage_option, product_brand_option, weight_option, vendor_option, product_strain_option
    if global_df is None:
        return
    df = global_df.copy()
    if "Product Type*" in df.columns:
        product_types = sorted(df["Product Type*"].dropna().unique())
        product_types.insert(0, "All")
        menu = product_type_option["menu"]
        menu.delete(0, "end")
        for pt in product_types:
            menu.add_command(label=pt, command=lambda value=pt: product_type_filter_var.set(value))
    if "Lineage" in df.columns:
        lineage_values = sorted(df["Lineage"].dropna().unique())
        lineage_values.insert(0, "All")
        menu = lineage_option["menu"]
        menu.delete(0, "end")
        for lv in lineage_values:
            menu.add_command(label=lv, command=lambda value=lv: lineage_filter_var.set(value))
    if "Product Brand" in df.columns:
        product_brands = sorted(df["Product Brand"].dropna().unique())
        product_brands.insert(0, "All")
        menu = product_brand_option["menu"]
        menu.delete(0, "end")
        for pb in product_brands:
            menu.add_command(label=pb, command=lambda value=pb: product_brand_filter_var.set(value))
    if "Vendor" in df.columns:
        vendors = sorted(df["Vendor"].dropna().unique())
        vendors.insert(0, "All")
        menu = vendor_option["menu"]
        menu.delete(0, "end")
        for v in vendors:
            menu.add_command(label=v, command=lambda value=v: vendor_filter_var.set(value))
    if "Product Strain" in df.columns:
        strains = sorted(df["Product Strain"].dropna().unique())
        strains.insert(0, "All")
        menu = product_strain_option["menu"]
        menu.delete(0, "end")
        for s in strains:
            menu.add_command(label=s, command=lambda value=s: product_strain_filter_var.set(value))

def update_weight_dropdown():
    """Dynamically repopulate the weight dropdown based on current Brand, Product Type, etc."""
    if global_df is None:
        return
    
    df = global_df.copy()
    
    # Apply all filters except weight
    if product_type_filter_var.get() != "All":
        df = df[df["Product Type*"] == product_type_filter_var.get()]
    if lineage_filter_var.get() != "All":
        df = df[df["Lineage"] == lineage_filter_var.get()]
    if product_brand_filter_var.get() != "All" and "Product Brand" in df.columns:
        df = df[df["Product Brand"] == product_brand_filter_var.get()]
    if vendor_filter_var.get() != "All" and "Vendor" in df.columns:
        df = df[df["Vendor"] == vendor_filter_var.get()]
    if product_strain_filter_var.get() != "All" and "Product Strain" in df.columns:
        df = df[df["Product Strain"] == product_strain_filter_var.get()]
    
    # If you're also filtering by quantity>0, do that here too:
    # if quantity_filter_var.get() == True and "Length" in df.columns:
    #     df = df[df["Length"] > 0]

    if "CombinedWeight" in df.columns:
        weight_values = sorted(
            df["CombinedWeight"].dropna().unique(),
            key=lambda x: float(re.findall(r"[\d\.]+", x)[0]) if re.findall(r"[\d\.]+", x) else 0
        )
        weight_values.insert(0, "All")

        # Clear existing menu items
        menu = weight_option["menu"]
        menu.delete(0, "end")

        # Re-add items from the filtered subset
        for w in weight_values:
            menu.add_command(label=w, command=lambda value=w: weight_filter_var.set(value))
    
    else:
        # If the column doesn't exist, at least reset to "All"
        menu = weight_option["menu"]
        menu.delete(0, "end")
        menu.add_command(label="All", command=lambda: weight_filter_var.set("All"))

def populate_product_names():
    for widget in desc_frame.winfo_children():
        widget.destroy()
    global global_df
    if global_df is None:
        return
    df = global_df.copy()
    if product_type_filter_var.get() != "All":
        df = df[df["Product Type*"] == product_type_filter_var.get()]
    if lineage_filter_var.get() != "All":
        df = df[df["Lineage"] == lineage_filter_var.get()]
    if product_brand_filter_var.get() != "All" and "Product Brand" in df.columns:
        df = df[df["Product Brand"] == product_brand_filter_var.get()]
    if vendor_filter_var.get() != "All" and "Vendor" in df.columns:
        df = df[df["Vendor"] == vendor_filter_var.get()]
    if weight_filter_var.get() != "All" and "CombinedWeight" in df.columns:
        df = df[df["CombinedWeight"] == weight_filter_var.get()]
    if product_strain_filter_var.get() != "All" and "Product Strain" in df.columns:
        df = df[df["Product Strain"] == product_strain_filter_var.get()]
    
    if "Product Name*" in df.columns:
        product_names = sorted(df["Product Name*"].dropna().unique())
        global product_check_vars, select_all_var
        product_check_vars = {}
        select_all_var = tk.BooleanVar(value=True)
        select_all_chk = tk.Checkbutton(desc_frame, text="Select All", variable=select_all_var,
                                        bg="white", anchor="w",
                                        command=lambda: select_all_toggle())
        select_all_chk.pack(fill="x", pady=2)
        for name in product_names:
            var = tk.BooleanVar(value=True)
            chk = tk.Checkbutton(desc_frame, text=name, variable=var,
                                 bg="white", anchor="w")
            chk.pack(fill="x", pady=2)
            product_check_vars[name] = var

        # Update scrollregion after all children are packed
        desc_frame.update_idletasks()
        bbox = desc_canvas.bbox("all")  # Get the bounding box for the canvas content
        if bbox:
            desc_canvas.configure(scrollregion=bbox)  # Recalculate scroll region
            desc_canvas.yview_moveto(0)  # Scroll to the top
            print("✅ Scroll moved to top")

    else:
        logging.debug("No 'Product Name*' column found.")


def select_all_toggle():
    global product_check_vars, select_all_var
    new_value = select_all_var.get()
    for var in product_check_vars.values():
        var.set(new_value)

def _on_mousewheel(event):
    if sys.platform == "darwin":
        desc_canvas.yview_scroll(-1 * int(event.delta), "units")
    else:
        desc_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

def _bind_mousewheel(event):
    if sys.platform == "darwin":
        desc_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    else:
        desc_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        desc_canvas.bind_all("<Button-4>", lambda e: desc_canvas.yview_scroll(-1, "units"))
        desc_canvas.bind_all("<Button-5>", lambda e: desc_canvas.yview_scroll(1, "units"))

def _unbind_mousewheel(event):
    desc_canvas.unbind_all("<MouseWheel>")
    desc_canvas.unbind_all("<Button-4>")
    desc_canvas.unbind_all("<Button-5>")


def bind_dropdown_traces():
    product_type_filter_var.trace_add("write", lambda *args: (
        populate_product_names(), 
        update_weight_dropdown()
    ))
    lineage_filter_var.trace_add("write", lambda *args: (
        populate_product_names(), 
        update_weight_dropdown()
    ))
    product_brand_filter_var.trace_add("write", lambda *args: (
        populate_product_names(), 
        update_weight_dropdown()
    ))
    vendor_filter_var.trace_add("write", lambda *args: (
        populate_product_names(), 
        update_weight_dropdown()
    ))
    product_strain_filter_var.trace_add("write", lambda *args: (
        populate_product_names(), 
        update_weight_dropdown()
    ))
    
    # For weight filter, you usually only need to re-populate product names
    # once weight changes:
    weight_filter_var.trace_add("write", lambda *args: populate_product_names())


if __name__ == '__main__':
    multiprocessing.freeze_support()
    # Start your GUI or main logic
    root = tk.Tk()
    root.title("AGT Price Tag Transformer")
    root.geometry("1240x800")

    # Hide main window initially
    root.withdraw()

    # Create splash screen window
    splash = tk.Toplevel()
    splash.overrideredirect(True)  # Remove window decorations
    splash.geometry("400x300+500+300")  # Set size and position (adjust as needed)

    # Customize your splash screen – here we use a simple label.
    splash_label = tk.Label(splash, text="Loading...", font=("Helvetica", 24))
    splash_label.pack(expand=True, fill="both")

    # After 3000 ms (3 seconds), destroy splash screen and show main window.
    def show_main():
        splash.destroy()
        root.deiconify()  # Show main window

    root.after(3000, show_main)

    from Foundation import NSObject
    from AppKit import NSApplication, NSApplicationActivationPolicyRegular

    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyRegular)

    import threading

    def load_initial_data():
        # Do heavy Excel/Word/template stuff here
        populate_filter_dropdowns()
        populate_product_names()

    root.after(500, lambda: threading.Thread(target=load_initial_data).start())


    # (The rest of your code continues here.)
    if platform.system() != "Windows":
        try:
            multiprocessing.set_start_method('fork')
        except RuntimeError:
            pass  # start method already set
    multiprocessing.freeze_support()
    
    try:
        icon = tk.PhotoImage(file=resource_path("your_icon.icns"))
        root.iconphoto(True, icon)
    except Exception as exc:
        print("Error setting icon:", exc)
    
    main_frame = tk.Frame(root, bg="#228B22")
    main_frame.pack(fill="both", expand=True)
    
    # LEFT FRAME
    left_frame = tk.Frame(main_frame, bg="#228B22", width=275)
    left_frame.pack(side="left", fill="y", padx=10, pady=10)
    left_frame.pack_propagate(False)
    
    def upload_file():
        file_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx"), ("CSV Files", "*.csv")])
        if file_path:
            label_file.config(text=os.path.basename(file_path))
            file_entry.delete(0, tk.END)
            file_entry.insert(0, file_path)
            global global_df
            cleaned_file = preprocess_excel(file_path)
            global_df = pd.read_excel(cleaned_file, engine="openpyxl")
            populate_filter_dropdowns()
            populate_product_names()
    
    btn_upload = tk.Button(
        left_frame, text="Upload Spreadsheet", command=upload_file,
        bg="#228B22", fg="#228B22", bd=2, relief="raised",
        activebackground="#228B22", activeforeground="#228B22",
        highlightthickness=0, width="15", font=("Arial", 16), height="4"
    )
    btn_upload.pack(pady=20)
    
    label_file = tk.Label(left_frame, text="No POSaBit file selected", bg="#228B22", fg="white")
    label_file.pack(pady=10)
    
    vendor_label = tk.Label(left_frame, text="\nSelect Vendor:", bg="#228B22", font=("Arial", 16), fg="white")
    vendor_label.pack(pady=5)
    vendor_filter_var = tk.StringVar(left_frame, value="All")
    global vendor_option
    vendor_option = tk.OptionMenu(left_frame, vendor_filter_var, "All")
    vendor_option.config(bg="white", width=10, anchor="center")
    vendor_option["menu"].config(bg="white")
    vendor_option.pack(pady=5, fill="x")
    
    product_brand_label = tk.Label(left_frame, text="\nSelect Product Brand:", font=("Arial", 16), bg="#228B22", fg="white")
    product_brand_label.pack(pady=5)
    product_brand_filter_var = tk.StringVar(left_frame, value="All")
    global product_brand_option
    product_brand_option = tk.OptionMenu(left_frame, product_brand_filter_var, "All")
    product_brand_option.config(bg="white", width=10, anchor="center")
    product_brand_option["menu"].config(bg="white")
    product_brand_option.pack(pady=5, fill="x")
    
    product_type_label = tk.Label(left_frame, text="\nSelect Product Type:", font=("Arial", 16), bg="#228B22", fg="white")
    product_type_label.pack(pady=5)
    product_type_filter_var = tk.StringVar(left_frame, value="All")
    global product_type_option
    product_type_option = tk.OptionMenu(left_frame, product_type_filter_var, "All")
    product_type_option.config(bg="white", width=10, anchor="center")
    product_type_option["menu"].config(bg="white")
    product_type_option.pack(pady=5, fill="x")
    
    lineage_label = tk.Label(left_frame, text="\nSelect Product Lineage:", font=("Arial", 16), bg="#228B22", fg="white")
    lineage_label.pack(pady=5)
    lineage_filter_var = tk.StringVar(left_frame, value="All")
    global lineage_option
    lineage_option = tk.OptionMenu(left_frame, lineage_filter_var, "All")
    lineage_option.config(bg="white", width=10, anchor="center")
    lineage_option["menu"].config(bg="white")
    lineage_option.pack(pady=5, fill="x")
    
    product_strain_label = tk.Label(left_frame, text="\nSelect Ratio (CBD or THC):", font=("Arial", 16), bg="#228B22", fg="white")
    product_strain_label.pack(pady=5)
    product_strain_filter_var = tk.StringVar(left_frame, value="All")
    global product_strain_option
    product_strain_option = tk.OptionMenu(left_frame, product_strain_filter_var, "All")
    product_strain_option.config(bg="white", width=10, anchor="center")
    product_strain_option["menu"].config(bg="white")
    product_strain_option.pack(pady=5, fill="x")
    
    weight_label = tk.Label(left_frame, text="\nSelect Product Weight:", font=("Arial", 16), bg="#228B22", fg="white")
    weight_label.pack(pady=5)
    weight_filter_var = tk.StringVar(left_frame, value="All")
    global weight_option
    weight_option = tk.OptionMenu(left_frame, weight_filter_var, "All")
    weight_option.config(bg="white", width=10, anchor="center")
    weight_option["menu"].config(bg="white")
    weight_option.pack(pady=5, fill="x")

    quantity_filter_var = tk.BooleanVar(value=True)
    quantity_chk = tk.Checkbutton(
        left_frame,
        text="Only show products with Quantity > 0",
        variable=quantity_filter_var,
        bg="#228B22",
        font=("Arial", 14),
        fg="white",
        anchor="w"
    )
    quantity_chk.pack(pady=10, fill="x")
    
    file_entry = tk.Entry(left_frame, bd=0, bg="white", fg="#000716", highlightthickness=0)
    
    # CENTER FRAME
    center_frame = tk.Frame(main_frame, bg="white", width=600)
    center_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    center_frame.pack_propagate(False)
    
    desc_label = tk.Label(center_frame, text="Selected Tag List:", bg="white")
    desc_label.pack(pady=5)
    
    desc_container = tk.Frame(center_frame, bg="white")
    desc_container.pack(fill="both", expand=True)
    
    global desc_canvas
    desc_canvas = tk.Canvas(desc_container, width=600, height=300, bg="white")
    desc_canvas.pack(side="top", fill="both", expand=True)
    
    desc_scrollbar = tk.Scrollbar(desc_container, orient="vertical", command=desc_canvas.yview)
    desc_scrollbar.pack(side="right", fill="y")
    desc_canvas.configure(yscrollcommand=desc_scrollbar.set, bg="white")
    
    desc_canvas.bind("<Enter>", _bind_mousewheel)
    desc_canvas.bind("<Leave>", _unbind_mousewheel)
    desc_canvas.bind("<Button-4>", lambda event: desc_canvas.yview_scroll(-1, "units"))
    desc_canvas.bind("<Button-5>", lambda event: desc_canvas.yview_scroll(1, "units"))
    
    global desc_frame
    desc_frame = tk.Frame(desc_canvas, bg="white")
    desc_canvas.create_window((0, 0), window=desc_frame, anchor="nw")
    desc_frame.bind("<Configure>", lambda event: desc_canvas.configure(scrollregion=desc_canvas.bbox("all")))
    
    # RIGHT FRAME
    right_frame = tk.Frame(main_frame, bg="#228B22", width=275)
    right_frame.pack(side="left", fill="y", padx=10, pady=10)
    right_frame.pack_propagate(False)
    
    btn_horizontal = tk.Button(
        right_frame, text="Generate Horizontal Tags",
        command=lambda: (
            messagebox.showwarning("Missing Filters", "Please choose at least one filter before generating.")
            if no_filters_selected()
            else run_full_process("horizontal")
        ),
        bg="#228B22", fg="#228B22", bd=2, relief="raised",
        activebackground="#228B22", activeforeground="#228B22",
        highlightthickness=0, font=("Arial", 16), height=4
    )
    btn_horizontal.pack(pady=20, fill="x")
    
    btn_vertical = tk.Button(
        right_frame, text="Generate Vertical Tags",
        command=lambda: (
            messagebox.showwarning("Missing Filters", "Please choose at least one filter before generating.")
            if no_filters_selected()
            else run_full_process("vertical")
        ),
        bg="#228B22", fg="#228B22", bd=2, relief="raised",
        activebackground="#228B22", activeforeground="#228B22",
        highlightthickness=0, font=("Arial", 16), height=4
    )
    btn_vertical.pack(pady=20, fill="x")
    
    info_text = (
        "\n\n\nTips For Generating Dataset:\n\n"
        "Step 1: Go to POSaBit > Inventory > 'Lots'\n\n"
        "Step 2: Set LOTs filters below:\n\n"
        "   * Status: 'Active'\n\n"
        "   * On Hand Greater Than: '0'.\n\n"
        "   (Don't Forget to Click 'Search')\n\n"
        "Step 3: Click the Blue Download icon,\n\n"
        "Step 4: Return to this app\n"
        "& Click the 'Upload Data' button\n\n"
        "Step 5: Select Template Above\n\n\n"
        "(Hint: Adding more filters to your initial\n"
        "POSaBit download can drastically\n"
        "reduce download time)"
    )
    info_label = tk.Label(
    right_frame,
    text=info_text,
    bg="white",
    fg="#228B22",
    font=("Arial", 14),
    justify="center",
    wraplength=240
    )
    info_label.pack(side="top", padx=10, pady=10, fill="both", expand=True)

    
    def bind_dropdown_traces():
        product_type_filter_var.trace_add("write", lambda *args: (populate_product_names(), update_weight_dropdown()))
        lineage_filter_var.trace_add("write", lambda *args: (populate_product_names(), update_weight_dropdown()))
        product_brand_filter_var.trace_add("write", lambda *args: (populate_product_names(), update_weight_dropdown()))
        vendor_filter_var.trace_add("write", lambda *args: (populate_product_names(), update_weight_dropdown()))
        product_strain_filter_var.trace_add("write", lambda *args: (populate_product_names(), update_weight_dropdown()))
        
        # When weight changes, you may only need to update product names
        weight_filter_var.trace_add("write", lambda *args: populate_product_names())

    bind_dropdown_traces()
    
    
    root.mainloop()

