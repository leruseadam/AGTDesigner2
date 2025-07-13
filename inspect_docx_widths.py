import zipfile
import xml.etree.ElementTree as ET
import sys
from pathlib import Path

def inspect_docx_widths(docx_path):
    with zipfile.ZipFile(docx_path, 'r') as z:
        with z.open('word/document.xml') as f:
            tree = ET.parse(f)
            root = tree.getroot()
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            print(f"Inspecting: {docx_path}")
            for tbl_idx, tbl in enumerate(root.findall('.//w:tbl', ns)):
                print(f"\nTable {tbl_idx+1}:")
                tblW = tbl.find('.//w:tblW', ns)
                if tblW is not None:
                    print(f"  <w:tblW>: w={tblW.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w')}, type={tblW.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type')}")
                tblGrid = tbl.find('.//w:tblGrid', ns)
                if tblGrid is not None:
                    for col_idx, gridCol in enumerate(tblGrid.findall('w:gridCol', ns)):
                        print(f"  Column {col_idx+1} <w:w>: {gridCol.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w')}")
                # Print each cell's <w:tcW>
                for row_idx, tr in enumerate(tbl.findall('w:tr', ns)):
                    for cell_idx, tc in enumerate(tr.findall('w:tc', ns)):
                        tcW = tc.find('.//w:tcW', ns)
                        if tcW is not None:
                            print(f"    Row {row_idx+1} Cell {cell_idx+1} <w:tcW>: w={tcW.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w')}, type={tcW.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type')}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python inspect_docx_widths.py <path_to_docx>")
        return
    docx_path = Path(sys.argv[1])
    if not docx_path.exists():
        print(f"File not found: {docx_path}")
        return
    inspect_docx_widths(docx_path)

if __name__ == "__main__":
    main() 