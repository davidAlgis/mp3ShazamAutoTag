def find_deepest_metadata_key(data, search_key):
    """
    Recursively searches for the 'text' value corresponding to a given 'title' key
    in a deeply nested structure of lists and dictionaries.

    Args:
        data (dict or list): The nested data to search.
        search_key (str): The 'title' value to search for.

    Returns:
        str or None: The 'text' value corresponding to the search_key, or None if not found.
    """
    # If the current level is a dictionary, search within it
    if isinstance(data, dict):
        # Check if the dictionary contains the 'title' and 'text' keys and matches the search_key
        if data.get("title") == search_key and "text" in data:
            return data["text"]
        # Otherwise, recurse into the dictionary's values
        for value in data.values():
            result = find_deepest_metadata_key(value, search_key)
            if result is not None:
                return result

    # If the current level is a list, iterate through it and search each item
    elif isinstance(data, list):
        for item in data:
            result = find_deepest_metadata_key(item, search_key)
            if result is not None:
                return result

    # If no match is found, return None
    return None
