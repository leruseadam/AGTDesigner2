#!/usr/bin/env python3
"""
Fix for PythonAnywhere default file loading issue.
This script creates a sample default file and updates the path handling for PythonAnywhere.
"""

import os
import pandas as pd
from pathlib import Path
import logging

def create_sample_default_file():
    """Create a sample default file for PythonAnywhere."""
    
    # Create uploads directory if it doesn't exist
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    # Sample data for the default file
    sample_data = {
        'ProductName': ['Sample Product 1', 'Sample Product 2', 'Sample Product 3'],
        'Product Type*': ['flower', 'pre-roll', 'concentrate'],
        'ProductBrand': ['Sample Brand', 'Sample Brand', 'Sample Brand'],
        'ProductStrain': ['Sample Strain', 'Sample Strain', 'Sample Strain'],
        'Lineage': ['INDICA', 'HYBRID', 'SATIVA'],
        'Weight*': [3.5, 1.0, 1.0],
        'Units': ['g', 'g', 'g'],
        'Ratio': ['THC: 20%\nCBD: 1%', 'THC: 18%\nCBD: 2%', 'THC: 85%\nCBD: 1%'],
        'Description': ['Sample description 1', 'Sample description 2', 'Sample description 3'],
        'DOH': ['No', 'No', 'No']
    }
    
    # Create DataFrame
    df = pd.DataFrame(sample_data)
    
    # Save to Excel file
    default_file_path = uploads_dir / "A Greener Today - Sample Inventory.xlsx"
    df.to_excel(default_file_path, index=False)
    
    print(f"Created sample default file: {default_file_path}")
    return str(default_file_path)

def update_excel_processor_for_pythonanywhere():
    """Update the excel_processor.py file to handle PythonAnywhere paths better."""
    
    excel_processor_path = Path("src/core/data/excel_processor.py")
    
    if not excel_processor_path.exists():
        print("excel_processor.py not found!")
        return
    
    # Read the current file
    with open(excel_processor_path, 'r') as f:
        content = f.read()
    
    # Create a backup
    backup_path = excel_processor_path.with_suffix('.py.bak')
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"Created backup: {backup_path}")
    
    # Update the get_default_upload_file function
    new_function = '''
def get_default_upload_file() -> Optional[str]:
    """
    Returns the path to the default Excel file.
    First looks in uploads directory, then in Downloads.
    Returns the most recent "A Greener Today" file found.
    Updated for PythonAnywhere compatibility.
    """
    import os
    from pathlib import Path
    
    # Get the current working directory (should be the project root)
    current_dir = os.getcwd()
    print(f"Current working directory: {current_dir}")
    
    # First, look in the uploads directory relative to current directory
    uploads_dir = os.path.join(current_dir, "uploads")
    print(f"Looking in uploads directory: {uploads_dir}")
    
    if os.path.exists(uploads_dir):
        print(f"Uploads directory exists: {uploads_dir}")
        for filename in os.listdir(uploads_dir):
            print(f"Found file in uploads: {filename}")
            if filename.startswith("A Greener Today") and filename.lower().endswith(".xlsx"):
                file_path = os.path.join(uploads_dir, filename)
                logger.info(f"Found default file in uploads: {file_path}")
                return file_path
    
    # If not found in uploads, look in Downloads (for local development)
    downloads_dir = os.path.join(str(Path.home()), "Downloads")
    print(f"Looking in Downloads directory: {downloads_dir}")
    
    if os.path.exists(downloads_dir):
        # Get all matching files and sort by modification time (most recent first)
        matching_files = []
        for filename in os.listdir(downloads_dir):
            if filename.startswith("A Greener Today") and filename.lower().endswith(".xlsx"):
                file_path = os.path.join(downloads_dir, filename)
                mod_time = os.path.getmtime(file_path)
                matching_files.append((file_path, mod_time))
        
        if matching_files:
            # Sort by modification time (most recent first)
            matching_files.sort(key=lambda x: x[1], reverse=True)
            most_recent_file = matching_files[0][0]
            logger.info(f"Found default file in Downloads: {most_recent_file}")
            return most_recent_file
    
    logger.warning("No default 'A Greener Today' file found")
    return None
'''
    
    # Replace the old function with the new one
    import re
    
    # Find and replace the function
    pattern = r'def get_default_upload_file\(\) -> Optional\[str\]:\s*\n\s*""".*?"""\s*\n.*?logger\.warning\("No default \'A Greener Today\' file found"\)\s*\n\s*return None'
    
    # Use a more specific replacement
    old_function_start = 'def get_default_upload_file() -> Optional[str]:'
    old_function_end = '    logger.warning("No default \'A Greener Today\' file found")\n    return None'
    
    if old_function_start in content and old_function_end in content:
        # Find the start and end positions
        start_pos = content.find(old_function_start)
        end_pos = content.find(old_function_end) + len(old_function_end)
        
        # Replace the function
        new_content = content[:start_pos] + new_function + content[end_pos:]
        
        # Write the updated content
        with open(excel_processor_path, 'w') as f:
            f.write(new_content)
        
        print("Updated excel_processor.py with PythonAnywhere-compatible default file loading")
    else:
        print("Could not find the get_default_upload_file function to update")

def main():
    """Main function to fix PythonAnywhere default file loading."""
    print("Fixing PythonAnywhere default file loading...")
    
    # Create sample default file
    default_file = create_sample_default_file()
    
    # Update the excel_processor.py file
    update_excel_processor_for_pythonanywhere()
    
    print(f"\n✅ PythonAnywhere fix completed!")
    print(f"📁 Sample default file created: {default_file}")
    print(f"🔧 excel_processor.py updated for PythonAnywhere compatibility")
    print(f"\nNext steps:")
    print(f"1. Reload your PythonAnywhere web app")
    print(f"2. The app should now load the sample default file automatically")
    print(f"3. You can upload your actual inventory file through the web interface")

if __name__ == "__main__":
    main() 