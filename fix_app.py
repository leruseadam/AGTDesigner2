#!/usr/bin/env python3
"""
Script to fix the incorrect replacements made by the optimization script
"""

import re

def fix_app_py():
    """Fix all the incorrect replacements in app.py."""
    
    # Read the current app.py
    with open('app.py', 'r') as f:
        content = f.read()
    
    # Fix 1: Replace incorrect variable assignments
    content = re.sub(r'get_excel_processor\(\) = get_excel_processor\(\)', 'excel_processor = get_excel_processor()', content)
    
    # Fix 2: Replace incorrect method calls on function results
    content = re.sub(r'get_excel_processor\(\)\.df', 'excel_processor.df', content)
    content = re.sub(r'get_excel_processor\(\)\.selected_tags', 'excel_processor.selected_tags', content)
    content = re.sub(r'get_excel_processor\(\)\.dropdown_cache', 'excel_processor.dropdown_cache', content)
    content = re.sub(r'get_excel_processor\(\)\.get_available_tags\(\)', 'excel_processor.get_available_tags()', content)
    content = re.sub(r'get_excel_processor\(\)\.load_file\(', 'excel_processor.load_file(', content)
    content = re.sub(r'get_excel_processor\(\)\.get_selected_records\(', 'excel_processor.get_selected_records(', content)
    content = re.sub(r'get_excel_processor\(\)\.get_dynamic_filter_options\(', 'excel_processor.get_dynamic_filter_options(', content)
    
    # Fix 3: Add excel_processor = get_excel_processor() where needed
    # Look for patterns where we use excel_processor but haven't assigned it
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # If line uses excel_processor but previous line doesn't assign it
        if 'excel_processor.' in line and i > 0:
            prev_line = lines[i-1].strip()
            if not prev_line.startswith('excel_processor = get_excel_processor()') and not prev_line.startswith('def ') and not prev_line.startswith('class '):
                # Check if we need to add the assignment
                if not any('excel_processor = get_excel_processor()' in l for l in lines[max(0, i-5):i]):
                    # Add the assignment before this line
                    fixed_lines.append('        excel_processor = get_excel_processor()')
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    # Write the fixed content back
    with open('app.py', 'w') as f:
        f.write(content)
    
    print("✅ Fixed app.py - corrected all incorrect replacements")

if __name__ == "__main__":
    fix_app_py() 