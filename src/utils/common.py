def safe_get(record, key, default=''):
    """Safely get a value from a record, handling None and NaN cases."""
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