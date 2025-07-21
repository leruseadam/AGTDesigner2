def safe_get(record, key, default=''):
<<<<<<< HEAD
    """Safely get a value from a record, handling None and NaN cases."""
=======
    """Safely get a value from a record, handling None and NaN cases. If record is a string, always return default."""
    if isinstance(record, str):
        return default
>>>>>>> 1374859 (Refactor: Use only unified get_font_size for all Ratio font sizing; deprecate legacy ratio font size functions)
    if hasattr(record, 'get'):
        value = record.get(key, default)
    else:
        # Handle DataFrame row objects
        try:
            value = getattr(record, key, default)
        except:
            return default
            
    if value is None or str(value).strip().lower() == 'nan':
        return default
    return str(value).strip()