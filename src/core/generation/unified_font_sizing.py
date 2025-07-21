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
<<<<<<< HEAD

logger = logging.getLogger(__name__)

# Font sizing configurations for different field types and orientations
FONT_SIZING_CONFIG = {
    'standard': {
        'mini': {
            'description': [(10, 20), (20, 18), (30, 16), (35, 14), (40, 13), (50, 12), (float('inf'), 9)],
            'brand': [(10, 14), (20, 12), (30, 10), (40, 8), (float('inf'), 7)],
            'price': [(20, 20), (30, 14), (40, 10), (float('inf'), 8)],
            'lineage': [(10, 10), (20, 9), (30, 8), (40, 7), (float('inf'), 6)],
            'ratio': [(5, 10), (8, 9), (12, 8), (20, 7), (float('inf'), 6)],
            'thc_cbd': [(10, 10), (20, 9), (25, 8), (35, 7), (float('inf'), 6)],
            'strain': [(10, 8), (20, 7), (30, 6), (float('inf'), 5)],
            'weight': [(10, 16), (20, 9), (30, 8), (float('inf'), 7)],
            'doh': [(10, 10), (20, 9), (float('inf'), 8)],
            'default': [(20, 10), (40, 9), (float('inf'), 8)]
        },
        'double': {
            'description': [(25, 24), (35, 22), (45, 20), (55, 18), (65, 16), (75, 14), (85, 12), (float('inf'), 10)],
            'brand': [(15, 22), (25, 20), (35, 18), (45, 16), (float('inf'), 10)],
            'price': [(20, 20), (30, 18), (40, 16), (50, 14), (float('inf'), 10)],
            'lineage': [(15, 16), (25, 14), (35, 12), (45, 10), (float('inf'), 9)],
            'ratio': [(10, 16), (15, 14), (20, 12), (25, 10), (float('inf'), 9)],
            'thc_cbd': [(15, 16), (25, 14), (30, 12), (40, 10), (float('inf'), 9)],
            'strain': [(10, 1), (20, 1), (30, 1), (float('inf'), 1)],
            'weight': [(15, 16), (25, 14), (35, 12), (float('inf'), 9)],
            'doh': [(15, 12), (25, 10), (float('inf'), 7)],
            'default': [(20, 16), (40, 14), (60, 12), (float('inf'), 10)]
        },
        'vertical': {
            'description': [(20, 28), (40, 26), (80, 24), (100, 22), (120, 20), (float('inf'), 14)],
            'brand': [(20, 12), (30, 10), (40, 8), (float('inf'), 11)],
            'price': [(10, 32), (20, 30), (30, 26), (float('inf'), 14)],
            'lineage': [(20, 16), (40, 14), (60, 12), (float('inf'), 8)],
            'ratio': [(10, 12), (20, 10), (30, 8), (float('inf'), 10)],
            'thc_cbd': [(15, 12), (25, 11), (35, 10), (float('inf'), 10)],
            'strain': [(10, 1), (20, 1), (30, 1), (float('inf'), 1)],
            'default': [(30, 16), (60, 14), (100, 12), (float('inf'), 10)]
        },
        'horizontal': {
            'description': [(20, 34), (30, 32), (40, 28), (50, 26), (55, 23), (70, 22), (80, 20), (90, 18), (100, 16), (120, 14), (float('inf'), 14)],
            'brand': [(15, 16), (25, 14), (35, 12), (45, 10), (float('inf'), 8)],
            'price': [(20, 36), (40, 34), (80, 32), (float('inf'), 10)],
            'lineage': [(20, 18), (40, 14), (60, 12), (float('inf'), 12)],
            'ratio': [(15, 16), (25, 14), (35, 12), (45, 10), (55, 8), (float('inf'), 8)],
            'thc_cbd': [(20, 16), (30, 14), (40, 12), (float('inf'), 12)],
            'strain': [(10, 1), (20, 1), (30, 1), (float('inf'), 1)],
            'default': [(20, 18), (40, 16), (60, 14), (float('inf'), 12)]
        }
    }
}
=======
import json
import os

logger = logging.getLogger(__name__)

def _load_font_sizing_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'font_sizing_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            raw = json.load(f)
        # Convert all int thresholds to float for compatibility
        for orientation in raw:
            for field in raw[orientation]:
                raw[orientation][field] = [(float(th), float(sz)) for th, sz in raw[orientation][field]]
        return {'standard': raw}
    else:
        # Fallback to built-in defaults (copied from previous FONT_SIZING_CONFIG)
        return {
            'standard': {
                'mini': {
                    'description': [(10, 20), (20, 18), (30, 16), (35, 14), (40, 13), (50, 12), (float('inf'), 9)],
                    'brand': [(10, 14), (20, 12), (30, 10), (40, 8), (float('inf'), 7)],
                    'price': [(20, 20), (30, 14), (40, 10), (float('inf'), 8)],
                    'lineage': [(10, 10), (20, 9), (30, 8), (40, 7), (float('inf'), 6)],
                    'ratio': [(5, 10), (8, 9), (12, 8), (20, 7), (float('inf'), 6)],
                    'thc_cbd': [(10, 10), (20, 9), (25, 8), (35, 7), (float('inf'), 6)],
                    'strain': [(10, 8), (20, 7), (30, 6), (float('inf'), 5)],
                    'weight': [(10, 16), (20, 9), (30, 8), (float('inf'), 7)],
                    'doh': [(10, 10), (20, 9), (float('inf'), 8)],
                    'default': [(20, 10), (40, 9), (float('inf'), 8)]
                },
                'double': {
                    'description': [(25, 24), (35, 22), (45, 20), (55, 18), (65, 16), (75, 14), (85, 12), (float('inf'), 10)],
                    'brand': [(15, 22), (25, 20), (35, 18), (45, 16), (float('inf'), 10)],
                    'price': [(20, 20), (30, 18), (40, 16), (50, 14), (float('inf'), 10)],
                    'lineage': [(15, 16), (25, 14), (35, 12), (45, 10), (float('inf'), 9)],
                    'ratio': [(10, 16), (15, 14), (20, 12), (25, 10), (float('inf'), 9)],
                    'thc_cbd': [(15, 16), (25, 14), (30, 12), (40, 10), (float('inf'), 9)],
                    'strain': [(10, 1), (20, 1), (30, 1), (float('inf'), 1)],
                    'weight': [(15, 16), (25, 14), (35, 12), (float('inf'), 9)],
                    'doh': [(15, 12), (25, 10), (float('inf'), 7)],
                    'default': [(20, 16), (40, 14), (60, 12), (float('inf'), 10)]
                },
                'vertical': {
                    'description': [(20, 28), (40, 26), (80, 24), (100, 22), (120, 20), (float('inf'), 14)],
                    'brand': [(20, 12), (30, 10), (40, 8), (float('inf'), 11)],
                    'price': [(10, 32), (20, 30), (30, 26), (float('inf'), 14)],
                    'lineage': [(20, 16), (40, 14), (60, 12), (float('inf'), 8)],
                    'ratio': [(10, 12), (20, 10), (30, 8), (float('inf'), 10)],
                    'thc_cbd': [(15, 12), (25, 11), (35, 10), (float('inf'), 10)],
                    'strain': [(10, 1), (20, 1), (30, 1), (float('inf'), 1)],
                    'default': [(30, 16), (60, 14), (100, 12), (float('inf'), 10)]
                },
                'horizontal': {
                    'description': [(20, 34), (30, 32), (40, 28), (45, 26), (50, 24), (55, 22), (60, 20), (70, 18), (100, 16), (120, 14), (float('inf'), 14)],
                    'brand': [(10, 18), (20, 16), (30, 14), (40, 12), (50, 10), (float('inf'), 8)],
                    'price': [(20, 36), (40, 34), (80, 32), (float('inf'), 10)],
                    'lineage': [(20, 18), (30, 16), (40, 14), (50, 12), (60, 10), (float('inf'), 10)],
                    'ratio': [(5, 11), (10, 10), (20, 9), (30, 8), (40, 7), (50, 6), (float('inf'), 10)],
                    'thc_cbd': [(20, 16), (30, 14), (40, 12), (50, 10), (float('inf'), 12)],
                    'strain': [(10, 1), (20, 1), (30, 1), (float('inf'), 1)],
                    'default': [(20, 18), (40, 16), (60, 14), (float('inf'), 12)]
                }
            }
        }

FONT_SIZING_CONFIG = _load_font_sizing_config()
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)

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
    
    # Special rule: If Description is 10 or more consecutive characters for the first word in Vertical Template, cap at 24pt
    if field_type.lower() == 'description' and orientation.lower() == 'vertical':
        first_word = str(text).split()[0] if str(text).split() else ''
        if len(first_word) >= 10:
            # Use the normal logic, but cap at 24pt before scaling
            comp = calculate_text_complexity(text, complexity_type)
            config = FONT_SIZING_CONFIG.get('standard', {}).get(orientation.lower(), {}).get(field_type.lower(), [])
            if not config:
                config = FONT_SIZING_CONFIG.get('standard', {}).get(orientation.lower(), {}).get('default', [])
            for threshold, size in config:
                if comp < threshold:
                    capped_size = min(size, 24)
                    final_size = capped_size * scale_factor
                    logger.debug(f"Special cap: text='{text}', first_word='{first_word}', complexity={comp:.2f}, threshold={threshold}, base_size={size}, capped_size={capped_size}, final_size={final_size}")
                    return Pt(final_size)
            fallback_size = min(8, 24) * scale_factor
            logger.debug(f"Special cap fallback: text='{text}', first_word='{first_word}', complexity={comp:.2f}, fallback_size={fallback_size}")
            return Pt(fallback_size)
    
    # Special rule: If brand contains 20 or more letters in horizontal template, force font size to 14
    if field_type.lower() == 'brand' and orientation.lower() == 'horizontal':
        if len(text) >= 20:
            final_size = 14 * scale_factor
            logger.debug(f"Special brand rule: text='{text}' ({len(text)} chars) >= 20, forcing 14pt font")
            return Pt(final_size)
        # Special rule: If brand contains multiple words and is greater than 9 characters, set font to 14
        elif len(text.split()) > 1 and len(text) > 9:
            final_size = 14 * scale_factor
            logger.debug(f"Special brand rule: text='{text}' ({len(text)} chars, {len(text.split())} words) > 9 chars and multiple words, forcing 14pt font")
            return Pt(final_size)
        # Special rule: If brand is all caps and 9 or more characters, set font to 14
        elif text.isupper() and len(text) >= 9:
            final_size = 14 * scale_factor
            logger.debug(f"Special brand rule: text='{text}' ({len(text)} chars) is all caps >= 9 chars, forcing 14pt font")
            return Pt(final_size)
    
    # Calculate complexity
<<<<<<< HEAD
    comp = calculate_text_complexity(text, complexity_type)
=======
    if field_type.lower() == 'ratio':
        comp = len(str(text).split())
        logger.error(f"[RATIO TEST] text='{text}' | word_count={comp} | config={config}")
    else:
        comp = calculate_text_complexity(text, complexity_type)
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
    
    # Get configuration for this field type and orientation
    config = FONT_SIZING_CONFIG.get('standard', {}).get(orientation.lower(), {}).get(field_type.lower(), [])
    
<<<<<<< HEAD
    if not config:
        # Fallback to default configuration
        config = FONT_SIZING_CONFIG.get('standard', {}).get(orientation.lower(), {}).get('default', [])
    
=======
    # --- DEBUG LOGGING FOR RATIO ---
    if field_type.lower() == 'ratio':
        logger.warning(f"[RATIO FONT SIZE DEBUG] orientation='{orientation}' field_type='{field_type}' config={config} complexity={comp}")
    if not config:
        # Fallback to default configuration
        config = FONT_SIZING_CONFIG.get('standard', {}).get(orientation.lower(), {}).get('default', [])
        if field_type.lower() == 'ratio':
            logger.warning(f"[RATIO FONT SIZE DEBUG] FALLBACK TO DEFAULT config={config}")
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
    # Find appropriate font size based on complexity
    for threshold, size in config:
        if comp < threshold:
            final_size = size * scale_factor
<<<<<<< HEAD
            logger.debug(f"Dynamic font sizing: text='{text}', complexity={comp:.2f}, "
                        f"field_type={field_type}, orientation={orientation}, "
                        f"threshold={threshold}, base_size={size}, final_size={final_size}")
=======
            if field_type.lower() == 'ratio':
                logger.error(f"[RATIO TEST] Chosen: threshold={threshold}, size={size}, final_size={final_size}")
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
            return Pt(final_size)
    
    # Fallback to smallest size
    fallback_size = 8 * scale_factor
<<<<<<< HEAD
    logger.debug(f"Dynamic font sizing fallback: text='{text}', complexity={comp:.2f}, "
                f"field_type={field_type}, orientation={orientation}, fallback_size={fallback_size}")
=======
    if field_type.lower() == 'ratio':
        logger.warning(f"[RATIO FONT SIZE DEBUG] Fallback used. text='{text}' | orientation='{orientation}' | complexity={comp} | fallback_size={fallback_size}")
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
    return Pt(fallback_size)

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

def set_mini_run_font_size(run, font_size):
    """Legacy function - use set_run_font_size instead."""
    return set_run_font_size(run, font_size) 