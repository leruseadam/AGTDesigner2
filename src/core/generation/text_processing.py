import re
from typing import Optional

# Performance optimization: disable debug logging in production
DEBUG_ENABLED = False

def format_ratio_multiline(text):
    # ... full implementation from formatting_utils.py ...
    pass

def format_cannabinoid_content(text):
    # ... full implementation from formatting_utils.py ...
    pass

def format_description_text(text, max_width=40):
    # ... full implementation from formatting_utils.py ...
    pass

def format_price(price):
    # ... full implementation from formatting_utils.py ...
    pass

def remove_marker(value):
    # ... full implementation from formatting_utils.py ...
    pass

def safe_get(record, key, default=''):
    # ... full implementation from formatting_utils.py ...
    pass

def safe_get_text(value):
    # ... full implementation from formatting_utils.py ...
    pass

def fix_description_spacing(desc: str) -> str:
    # ... full implementation from formatting_utils.py ...
    pass

def make_nonbreaking_hyphens(text):
    # ... full implementation from formatting_utils.py ...
    pass

def replace_placeholder_with_markers(doc, placeholder, marker_value):
    # ... full implementation from formatting_utils.py ...
    pass

def process_doh_image(doh_value, product_type):
    """
    Determine the correct DOH image path based on product type.
    Returns the image path or an empty string.
    """
    import os
    from src.core.utils import resource_path
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.warning(f"process_doh_image called with doh_value='{doh_value}', product_type='{product_type}'")
        if str(doh_value).upper() == 'YES':
            # Get DOH image path
            doh_image_path = resource_path(os.path.join("templates", "DOH.png"))
            high_cbd_image_path = resource_path(os.path.join("templates", "HighCBD.png"))

            # Use HighCBD.png if product_type contains 'high cbd' (case-insensitive)
            if 'high cbd' in str(product_type).strip().lower():
                logger.warning(f"Using HighCBD image for product type '{product_type}': {high_cbd_image_path}")
                return high_cbd_image_path
            else:
                logger.warning(f"Using DOH image for product type '{product_type}': {doh_image_path}")
                return doh_image_path
        else:
            logger.warning("Skipping DOH image - value is not 'YES'")
            return ""
    except Exception as e:
        logger.error(f"Error processing DOH image path: {str(e)}")
        return "" 