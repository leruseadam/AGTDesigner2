def safe_get(obj, key, default=None):
    """
    Safely get a value from an object using a key, with a default value if the key doesn't exist.
    
    Args:
        obj: The object to get the value from
        key: The key to look up
        default: The default value to return if the key doesn't exist
        
    Returns:
        The value if found, otherwise the default value
    """
    try:
        return obj.get(key, default)
    except (AttributeError, TypeError):
        return default 