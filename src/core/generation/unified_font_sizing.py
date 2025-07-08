#!/usr/bin/env python3
"""
Unified font sizing system that consolidates all font sizing logic.
This module replaces the repetitive font sizing functions across the codebase.
"""

import logging
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from src.core.utils.common import calculate_text_complexity

logger = logging.getLogger(__name__)

# Font sizing configurations for different field types and orientations
FONT_SIZING_CONFIG = {
    'standard': {
        'mini': {
            'description': [(30, 16), (40, 15), (50, 14), (70, 13), (90, 12), (100, 11), (float('inf'), 9)],
            'brand': [(10, 14), (30, 11), (40, 8), (float('inf'), 7)],
            'price': [(20, 14), (30, 12), (40, 10), (float('inf'), 8)],
            'lineage': [(10, 10), (20, 9), (30, 8), (40, 7), (float('inf'), 6)],
            'ratio': [(5, 10), (8, 9), (12, 8), (20, 7), (float('inf'), 6)],
            'thc_cbd': [(10, 10), (20, 9), (25, 8), (35, 7), (float('inf'), 6)],
            'strain': [(15, 12), (25, 10), (35, 9), (float('inf'), 8)],
            'weight': [(10, 10), (20, 9), (30, 8), (float('inf'), 7)],
            'doh': [(10, 10), (20, 9), (float('inf'), 8)],
            'default': [(20, 10), (40, 9), (float('inf'), 8)]
        },
        'vertical': {
            'description': [(30, 26), (60, 24), (100, 22), (140, 18), (float('inf'), 14)],
            'brand': [(20, 12), (30, 10), (40, 8), (float('inf'), 11)],
            'price': [(10, 30), (20, 28), (30, 26), (float('inf'), 14)],
            'lineage': [(20, 14), (40, 12), (60, 10), (float('inf'), 8)],
            'ratio': [(10, 16), (20, 14), (30, 12), (float('inf'), 10)],
            'thc_cbd': [(15, 16), (25, 14), (35, 12), (float('inf'), 10)],
            'strain': [(20, 16), (40, 14), (60, 12), (float('inf'), 10)],
            'default': [(30, 16), (60, 14), (100, 12), (float('inf'), 10)]
        },
        'horizontal': {
            'description': [(20, 36), (25, 32), (30, 28), (40, 24), (50, 22), (60, 20), (70, 18), (float('inf'), 14)],
            'brand': [(20, 16), (40, 14), (80, 12), (float('inf'), 10)],
            'price': [(20, 36), (40, 34), (80, 32), (float('inf'), 10)],
            'lineage': [(20, 18), (40, 16), (60, 14), (float('inf'), 12)],
            'ratio': [(15, 18), (25, 16), (35, 14), (float('inf'), 12)],
            'thc_cbd': [(20, 18), (30, 16), (40, 14), (float('inf'), 12)],
            'strain': [(20, 18), (40, 16), (60, 14), (float('inf'), 12)],
            'default': [(20, 18), (40, 16), (60, 14), (float('inf'), 12)]
        }
    }
}

def get_font_size(text: str, field_type: str = 'default', orientation: str = 'vertical', 
                 scale_factor: float = 1.0, complexity_type: str = 'standard') -> Pt:
    """
    Unified font sizing function that replaces all the repetitive font sizing functions.
    
    Args:
        text: The text to size
        field_type: Type of field ('description', 'brand', 'price', 'lineage', 'ratio', 'thc_cbd', 'strain', 'weight', 'doh', 'default')
        orientation: Template orientation ('mini', 'vertical', 'horizontal')
        scale_factor: Scaling factor for the font size
        complexity_type: Type of complexity calculation ('standard', 'description', 'mini')
    
    Returns:
        Font size as Pt object
    """
    if not text:
        return Pt(12 * scale_factor)
    
    # Calculate complexity
    comp = calculate_text_complexity(text, complexity_type)
    
    # Get configuration for this field type and orientation
    config = FONT_SIZING_CONFIG.get('standard', {}).get(orientation.lower(), {}).get(field_type.lower(), [])
    
    if not config:
        # Fallback to default configuration
        config = FONT_SIZING_CONFIG.get('standard', {}).get(orientation.lower(), {}).get('default', [])
    
    # Find appropriate font size based on complexity
    for threshold, size in config:
        if comp < threshold:
            return Pt(size * scale_factor)
    
    # Fallback to smallest size
    return Pt(8 * scale_factor)

def set_run_font_size(run, font_size):
    """Set font size for both the run and its XML element."""
    if not isinstance(font_size, Pt):
        logger.warning(f"Font size was not Pt: {font_size} (type: {type(font_size)}), converting to Pt.")
        font_size = Pt(font_size)
    run.font.size = font_size
    sz_val = str(int(font_size.pt * 2))
    rPr = run._element.get_or_add_rPr()
    sz = rPr.find(qn('w:sz'))
    if sz is None:
        sz = OxmlElement('w:sz')
        rPr.append(sz)
    sz.set(qn('w:val'), sz_val)
    logger.debug(f"Set font size to {font_size.pt}pt for text: {run.text}")

# Legacy function aliases for backward compatibility
def get_thresholded_font_size(text, orientation='vertical', scale_factor=1.0, field_type='default'):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, field_type, orientation, scale_factor)

def get_thresholded_font_size_description(text, orientation='vertical', scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'description', orientation, scale_factor)

def get_thresholded_font_size_brand(text, orientation='vertical', scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'brand', orientation, scale_factor)

def get_thresholded_font_size_price(text, orientation='vertical', scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'price', orientation, scale_factor)

def get_thresholded_font_size_lineage(text, orientation='vertical', scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'lineage', orientation, scale_factor)

def get_thresholded_font_size_ratio(text, orientation='vertical', scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'ratio', orientation, scale_factor)

def get_thresholded_font_size_thc_cbd(text, orientation='vertical', scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'thc_cbd', orientation, scale_factor)

def get_thresholded_font_size_strain(text, orientation='vertical', scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'strain', orientation, scale_factor)

# Mini-specific legacy functions
def get_mini_font_size_description(text, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'description', 'mini', scale_factor, 'mini')

def get_mini_font_size_brand(text, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'brand', 'mini', scale_factor, 'mini')

def get_mini_font_size_price(text, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'price', 'mini', scale_factor, 'mini')

def get_mini_font_size_lineage(text, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'lineage', 'mini', scale_factor, 'mini')

def get_mini_font_size_ratio(text, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'ratio', 'mini', scale_factor, 'mini')

def get_mini_font_size_thc_cbd(text, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'thc_cbd', 'mini', scale_factor, 'mini')

def get_mini_font_size_strain(text, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'strain', 'mini', scale_factor, 'mini')

def get_mini_font_size_weight(text, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'weight', 'mini', scale_factor, 'mini')

def get_mini_font_size_doh(text, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    return get_font_size(text, 'doh', 'mini', scale_factor, 'mini')

def get_mini_font_size_by_marker(text, marker_type, scale_factor=1.0):
    """Legacy function - use get_font_size instead."""
    marker_to_field = {
        'DESC': 'description',
        'DESCRIPTION': 'description',
        'PRICE': 'price',
        'PRIC': 'price',
        'BRAND': 'brand',
        'PRODUCTBRAND': 'brand',
        'PRODUCTBRAND_CENTER': 'brand',
        'LINEAGE': 'lineage',
        'LINEAGE_CENTER': 'lineage',
        'RATIO': 'ratio',
        'THC_CBD': 'thc_cbd',
        'RATIO_OR_THC_CBD': 'thc_cbd',
        'WEIGHT': 'weight',
        'WEIGHTUNITS': 'weight',
        'UNITS': 'weight',
        'STRAIN': 'strain',
        'PRODUCTSTRAIN': 'strain',
        'DOH': 'doh'
    }
    field_type = marker_to_field.get(marker_type.upper(), 'default')
    return get_font_size(text, field_type, 'mini', scale_factor, 'mini') 