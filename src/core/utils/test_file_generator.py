import pandas as pd
from pathlib import Path
import logging

def create_test_file():
    """Create a test Excel file with sample product data in the Downloads folder."""
    # Sample product data
    test_data = {
        'Product Name*': [
            'Blue Dream', 'OG Kush', 'Sour Diesel', 'Granddaddy Purple', 'Jack Herer',
            'Northern Lights', 'White Widow', 'AK-47', 'CBD Tincture', 'THC Gummies'
        ],
        'Brand': [
            'Brand A', 'Brand B', 'Brand C', 'Brand A', 'Brand B',
            'Brand C', 'Brand A', 'Brand B', 'Brand C', 'Brand A'
        ],
        'Product Type*': [
            'Flower', 'Flower', 'Flower', 'Flower', 'Flower',
            'Flower', 'Flower', 'Flower', 'Tincture', 'Edible'
        ],
        'Weight': [3.5, 7.0, 3.5, 7.0, 3.5, 7.0, 3.5, 7.0, 30.0, 10.0],
        'Weight Units': [
            'Grams', 'Grams', 'Grams', 'Grams', 'Grams',
            'Grams', 'Grams', 'Grams', 'ML', 'Count'
        ],
        'Price': [45.00, 80.00, 50.00, 85.00, 48.00, 82.00, 46.00, 78.00, 35.00, 25.00],
        'Lineage': [
            'SATIVA', 'INDICA', 'SATIVA', 'INDICA', 'SATIVA',
            'INDICA', 'HYBRID', 'HYBRID', 'CBD', 'HYBRID'
        ],
        'Strain': [
            'Blue Dream', 'OG Kush', 'Sour Diesel', 'Granddaddy Purple', 'Jack Herer',
            'Northern Lights', 'White Widow', 'AK-47', 'CBD Blend', 'Mixed'
        ],
        'Description': [
            'Classic sativa-dominant hybrid with sweet berry aroma',
            'Potent indica with earthy pine scent',
            'Energizing sativa with diesel fuel aroma',
            'Relaxing indica with grape and berry flavors',
            'Clear-headed sativa with spicy pine notes',
            'Classic indica with sweet and spicy aroma',
            'Balanced hybrid with white crystal trichomes',
            'Potent hybrid with complex aroma profile',
            'Full-spectrum CBD tincture for wellness',
            'Assorted fruit-flavored THC gummies'
        ],
        'THC %': [18.5, 22.0, 20.5, 18.0, 19.5, 21.0, 20.0, 19.5, 0.3, 10.0],
        'CBD %': [0.2, 0.1, 0.3, 0.2, 0.1, 0.2, 0.3, 0.1, 15.0, 0.5],
        'Ratio_or_THC_CBD': [18.5, 22.0, 20.5, 18.0, 19.5, 21.0, 20.0, 19.5, 15.0, 10.0]
    }

    # Create DataFrame
    df = pd.DataFrame(test_data)

    # Create test file in Downloads folder
    downloads_dir = Path.home() / "Downloads"
    test_file_path = downloads_dir / "testFile.xlsx"

    try:
        # Save as Excel file
        df.to_excel(test_file_path, index=False)
        logging.info(f"Test file created at: {test_file_path}")
        return str(test_file_path)
    except Exception as e:
        logging.error(f"Failed to create test file: {e}")
        return None 