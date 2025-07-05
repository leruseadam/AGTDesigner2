from docx.shared import Pt
import logging
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)

WORD_WEIGHT = 2

def _complexity(text):
    """Combine character count, weighted word count, and penalize long words for font sizing."""
    text = str(text or "")
    words = text.split()
    char_count = len(text)
    word_count = len(words)
    # Penalty for long words
    max_word_length = max((len(word) for word in words), default=0)
    long_word_penalty = max(0, max_word_length - 12) * 2  # 2 points per char over 12
    return char_count + word_count * WORD_WEIGHT + long_word_penalty

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

def get_thresholded_font_size(text, orientation='vertical', scale_factor=1.0, field_type='default'):
    """Get appropriate font size based on text length and field type."""
    if not text:
        result = Pt(12 * scale_factor)
        logger.debug(f"get_thresholded_font_size: returning {result} (type: {type(result)}) for empty text")
        return result
    
    comp = _complexity(text)
    o = orientation.lower()
    
    # Handle different field types
    if field_type in ['weight', 'description', 'DescAndWeight']:
        # Unified logic for weight and description since they stay together
        if o == 'mini':
            if comp < 30:
                size = Pt(16 * scale_factor)
            elif comp < 40:
                size = Pt(15 * scale_factor)
            elif comp < 50:
                size = Pt(14 * scale_factor)
            elif comp < 70:
                size = Pt(13 * scale_factor)
            elif comp < 90:
                size = Pt(12 * scale_factor)
            elif comp < 100:
                size = Pt(11 * scale_factor)
            else:
                size = Pt(9 * scale_factor)
        elif o == 'vertical':
            if comp < 30:
                size = Pt(20 * scale_factor)
            elif comp < 60:
                size = Pt(18 * scale_factor)
            elif comp < 100:
                size = Pt(14 * scale_factor)
            elif comp < 140:
                size = Pt(11 * scale_factor)
            else:
                size = Pt(14 * scale_factor)
        elif o == 'horizontal':
            if comp < 20:
                size = Pt(36 * scale_factor)
            elif comp < 30:
                size = Pt(36 * scale_factor)
            elif comp < 40:
                size = Pt(28 * scale_factor)
            elif comp < 50:
                size = Pt(26 * scale_factor)
            elif comp < 55:
                size = Pt(24 * scale_factor)
            elif comp < 60:
                size = Pt(22 * scale_factor)
            elif comp < 75:
                size = Pt(20 * scale_factor)
            elif comp < 80:
                size = Pt(18 * scale_factor)
            else:
                size = Pt(14 * scale_factor)
        else:
            size = Pt(11 * scale_factor)

    elif field_type == 'ratio':
        # Fixed appropriate sizes for ratio content
        if o == 'mini':
            size = Pt(9 * scale_factor)
        elif o == 'vertical':
            size = Pt(12 * scale_factor)  # Reduced from 18 to 12
        elif o == 'horizontal':
            size = Pt(12 * scale_factor)  # Reduced from 14 to 12
        else:
            size = Pt(12 * scale_factor)
        
        logger.debug(f"Ratio font size: {size} for text: {text}")
        return size

    elif field_type == 'brand':
        if o == 'mini':
            if comp < 10:
                size = Pt(14 * scale_factor)
            elif comp < 30:
                size = Pt(11 * scale_factor)
            elif comp < 40:
                size = Pt(8 * scale_factor)
            else:
                size = Pt(7 * scale_factor)
        elif o == 'vertical':
            if comp < 20:
                size = Pt(12 * scale_factor)
            elif comp < 30:
                size = Pt(10 * scale_factor)
            elif comp < 40:
                size = Pt(8 * scale_factor)
            else:
                size = Pt(11 * scale_factor)
        elif o == 'horizontal':
            if comp < 20:
                size = Pt(16 * scale_factor)
            elif comp < 40:
                size = Pt(14 * scale_factor)
            elif comp < 80:
                size = Pt(12 * scale_factor)
            else:
                size = Pt(10 * scale_factor)
        else:
            size = Pt(8 * scale_factor)

    elif field_type == 'price':
        if o == 'mini':
            if comp < 20:
                size = Pt(14 * scale_factor)
            elif comp < 30:
                size = Pt(12 * scale_factor)
            elif comp < 40:
                size = Pt(10 * scale_factor)
            else:
                size = Pt(8 * scale_factor)
        elif o == 'vertical':
            if comp < 10:
                size = Pt(20 * scale_factor)
            elif comp < 20:
                size = Pt(18 * scale_factor)
            elif comp < 30:
                size = Pt(16 * scale_factor)
            else:
                size = Pt(14 * scale_factor)
        elif o == 'horizontal':
            if comp < 20:
                size = Pt(36 * scale_factor)
            elif comp < 40:
                size = Pt(34 * scale_factor)
            elif comp < 80:
                size = Pt(32 * scale_factor)
            else:
                size = Pt(10 * scale_factor)
        else:
            size = Pt(28 * scale_factor)

    elif field_type == 'lineage':
        if o == 'mini':
            if comp < 20:
                size = Pt(12 * scale_factor)
            elif comp < 60:
                size = Pt(10 * scale_factor)
            elif comp < 100:
                size = Pt(8 * scale_factor)
            else:
                size = Pt(6 * scale_factor)
        elif o == 'vertical':
            if comp < 20:
                size = Pt(12 * scale_factor)
            elif comp < 60:
                size = Pt(10 * scale_factor)
            elif comp < 80:
                size = Pt(8 * scale_factor)
            else:
                size = Pt(8 * scale_factor)
        elif o == 'horizontal':
            if comp < 100:
                size = Pt(16 * scale_factor)
            elif comp < 140:
                size = Pt(14 * scale_factor)
            elif comp < 180:
                size = Pt(12 * scale_factor)
            else:
                size = Pt(10 * scale_factor)
        else:
            size = Pt(10 * scale_factor)

    else:
        # Default fallback
        size = Pt(12 * scale_factor)

    return size

def get_thresholded_font_size_brand(text, orientation='vertical', scale_factor=1.0):
    """Calculate font size for brand names."""
    logger.debug(f"Calculating brand font size: {text}")
    
    # Brand names typically need larger font sizes
    base_size = 14 if orientation == 'vertical' else 16
    min_size = 10 if orientation == 'vertical' else 12
    max_size = 20 if orientation == 'vertical' else 24
    
    # Calculate size based on length
    length = len(text)
    if length <= 10:
        size = base_size
    elif length <= 20:
        size = base_size - 2
    else:
        size = base_size - 4
    
    # Apply scale factor
    size = int(size * scale_factor)
    
    # Ensure size is within bounds
    size = max(min_size, min(size, max_size))
    
    final_size = Pt(size)
    logger.debug(f"Calculated brand font size: {final_size.pt}pt")
    return final_size

def get_thresholded_font_size_ratio(text, orientation='vertical', scale_factor=1.0):
    """Calculate appropriate font size for ratio text."""
    logger.debug(f"Calculating ratio font size for: {text}")

    # Clean the text for analysis
    clean_text = text.replace('THC_CBD_START', '').replace('THC_CBD_END', '').replace('RATIO_START', '').replace('RATIO_END', '')
    clean_text = ' '.join(clean_text.split())
    
    # Use consistent sizing across all orientations for ratio content
    if orientation == 'mini':
        base_size = 9
    elif orientation == 'vertical':
        base_size = 12
    elif orientation == 'horizontal':
        base_size = 12
    else:
        base_size = 12
    
    # Determine if this is standard THC/CBD format
    if 'THC:' in clean_text and 'CBD:' in clean_text:
        # Standard THC/CBD format - can be slightly smaller
        size = base_size - 1
    elif 'mg' in clean_text.lower():
        # mg values - can be smaller
        size = base_size - 1
    elif ':' in clean_text and any(c.isdigit() for c in clean_text):
        # Ratio format (e.g., 1:1:1) - can be smaller
        size = base_size - 1
    else:
        # Default size
        size = base_size
    
    # Adjust size based on text length
    length = len(clean_text)
    if length > 30:
        size -= 2
    elif length > 20:
        size -= 1
    
    # Ensure minimum size
    size = max(8, size)
    
    # Apply scale factor
    final_size = Pt(size * scale_factor)
    
    logger.debug(f"Final ratio font size: {final_size.pt}pt")
    return final_size

def get_thresholded_font_size_lineage(text, orientation='vertical', scale_factor=1.0):
    """Calculate a fixed font size for lineage text."""
    # Set a fixed font size for all lineage text
    fixed_size = 20  # Adjust this value as needed
    
    # Apply scale factor
    final_size = Pt(fixed_size * scale_factor)
    
    logger.debug(f"Applying fixed font size for lineage: {final_size.pt}pt")
    return final_size

def get_thresholded_font_size_description(text, orientation='vertical', scale_factor=1.0):
    """
    Calculate font size for description text.
    This function now has its own dedicated logic for description font sizing.
    """
    logger.debug(f"Calculating description font size for: '{text}'")
    
    if not text:
        return Pt(12 * scale_factor)
    
    comp = _complexity(text)
    o = orientation.lower()
    
    # Description-specific font sizing logic
    if o == 'mini':
        if comp < 30:
            size = Pt(16 * scale_factor)
        elif comp < 40:
            size = Pt(15 * scale_factor)
        elif comp < 50:
            size = Pt(14 * scale_factor)
        elif comp < 70:
            size = Pt(13 * scale_factor)
        elif comp < 90:
            size = Pt(12 * scale_factor)
        elif comp < 100:
            size = Pt(11 * scale_factor)
        else:
            size = Pt(9 * scale_factor)
    elif o == 'vertical':
        if comp < 30:
            size = Pt(20 * scale_factor)
        elif comp < 60:
            size = Pt(18 * scale_factor)
        elif comp < 100:
            size = Pt(14 * scale_factor)
        elif comp < 140:
            size = Pt(11 * scale_factor)
        else:
            size = Pt(14 * scale_factor)
    elif o == 'horizontal':
        if comp < 20:
            size = Pt(36 * scale_factor)
        elif comp < 30:
            size = Pt(32 * scale_factor)
        elif comp < 35:
            size = Pt(30 * scale_factor)
        elif comp < 40:
            size = Pt(28 * scale_factor)
        elif comp < 50:
            size = Pt(26 * scale_factor)
        elif comp < 60:
            size = Pt(24 * scale_factor)
        elif comp < 65:
            size = Pt(22 * scale_factor)
        elif comp < 70:
            size = Pt(18 * scale_factor)
        elif comp < 80:
            size = Pt(16 * scale_factor)
        else:
            size = Pt(14 * scale_factor)
    else:
        size = Pt(12 * scale_factor)
    
    logger.debug(f"Description font size: {size.pt}pt for text: {text}")
    return size

def get_thresholded_font_size_price(text, orientation='vertical', scale_factor=1.0):
    """Calculate font size for price text."""
    logger.debug(f"Calculating price font size: {text}")
    
    # Price text typically needs larger font sizes
    base_size = 16 if orientation == 'vertical' else 34
    min_size = 12 if orientation == 'vertical' else 14
    max_size = 24 if orientation == 'vertical' else 36
    
    # Calculate size based on length and content
    length = len(text)
    # Remove currency symbols and spaces for length calculation
    clean_text = text.replace('$', '').replace(' ', '')
    length = len(clean_text)
    
    if length <= 5:  # Short prices like "$9.99"
        size = base_size + 2
    elif length <= 7:  # Medium prices like "$29.99"
        size = base_size
    elif length <= 9:  # Longer prices like "$129.99"
        size = base_size - 2
    else:  # Very long prices
        size = base_size - 4
    
    # Apply scale factor
    size = int(size * scale_factor)
    
    # Ensure size is within bounds
    size = max(min_size, min(size, max_size))
    
    final_size = Pt(size)
    logger.debug(f"Calculated price font size: {final_size.pt}pt")
    return final_size

def get_thresholded_font_size_by_word_count(text, orientation='vertical', scale_factor=1.0):
    """Wrapper function for backward compatibility."""
    return get_thresholded_font_size(text, orientation, scale_factor, 'default')

def get_font_size(text, font_params, scale_factor=1.0):
    """Calculate font size based on text length and font parameters."""
    length = len(text)
    base_size = font_params["base_size"]
    max_length = font_params["max_length"]
    min_size = font_params["min_size"]
    return Pt(base_size) if length <= max_length else Pt(max(min_size, base_size * (max_length / length)))

def get_thresholded_font_size_strain(text, orientation='vertical', scale_factor=1.0):
    """Calculate font size for product strain text with consistent sizing."""
    # Always return 1pt to make Product Strain nearly invisible
    return Pt(1) 