#!/usr/bin/env python3
"""
Script to fix the matching logic in app.py to be more conservative and vendor-aware.
"""

import re

def fix_matching_logic():
    """Update the matching logic in app.py to be more conservative."""
    
    # Read the current app.py
    with open('app.py', 'r') as f:
        content = f.read()
    
    # Find the matching logic section and replace it with more conservative logic
    old_pattern = r'# Strategy 3: Word-based matching \(check if key words match\)\s+if not found:\s+# Extract key words from the name \(remove common prefixes/suffixes\)\s+name_words = set\(name_lower\.replace\("-", " "\)\.replace\("_", " "\)\.split\(\)\)\s+# Remove common words that don\'t help with matching\s+common_words = \{\'medically\', \'compliant\', \'all\', \'in\', \'one\', \'1g\', \'2g\', \'3\.5g\', \'7g\', \'14g\', \'28g\', \'oz\', \'gram\', \'grams\'\}\s+name_words = name_words - common_words\s+if name_words:  # Only try if we have meaningful words\s+for tag in available_tags:\s+tag_name = str\(tag\.get\(\'Product Name\*\', \'\'\)\)\.strip\(\)\.lower\(\)\s+if tag_name:\s+tag_words = set\(tag_name\.replace\("-", " "\)\.replace\("_", " "\)\.split\(\)\)\s+tag_words = tag_words - common_words\s+# Check if there\'s significant word overlap\s+if name_words and tag_words:\s+overlap = name_words\.intersection\(tag_words\)\s+if len\(overlap\) >= min\(len\(name_words\), len\(tag_words\)\) \* 0\.5:  # 50% overlap\s+found = tag\s+break'
    
    new_logic = '''# Strategy 3: Word-based matching with vendor check and high overlap requirement
            if not found:
                # Extract key words from the name (remove common prefixes/suffixes)
                name_words = set(name_lower.replace('-', ' ').replace('_', ' ').split())
                # Remove common words that don't help with matching
                common_words = {'medically', 'compliant', 'all', 'in', 'one', '1g', '2g', '3.5g', '7g', '14g', '28g', 'oz', 'gram', 'grams', 'pk', 'pack', 'packs', 'piece', 'pieces', 'roll', 'rolls', 'stix', 'stick', 'sticks'}
                name_words = name_words - common_words
                
                # Extract vendor/brand from name
                name_vendor = ""
                if 'medically compliant' in name_lower:
                    name_vendor = "medically compliant"
                elif 'dank czar' in name_lower:
                    name_vendor = "dank czar"
                elif 'melt stix' in name_lower:
                    name_vendor = "melt stix"
                elif 'rosin rolls' in name_lower:
                    name_vendor = "rosin rolls"
                
                if name_words:  # Only try if we have meaningful words
                    for tag in available_tags:
                        tag_name = str(tag.get('Product Name*', '')).strip().lower()
                        if tag_name:
                            tag_words = set(tag_name.replace('-', ' ').replace('_', ' ').split())
                            tag_words = tag_words - common_words
                            
                            # Extract vendor/brand from tag
                            tag_vendor = ""
                            if 'medically compliant' in tag_name:
                                tag_vendor = "medically compliant"
                            elif 'dank czar' in tag_name:
                                tag_vendor = "dank czar"
                            elif 'melt stix' in tag_name:
                                tag_vendor = "melt stix"
                            elif 'rosin rolls' in tag_name:
                                tag_vendor = "rosin rolls"
                            
                            # Check if there's significant word overlap AND vendor match
                            if name_words and tag_words:
                                overlap = name_words.intersection(tag_words)
                                vendor_match = (not name_vendor or not tag_vendor or name_vendor == tag_vendor)
                                if len(overlap) >= min(len(name_words), len(tag_words)) * 0.7 and vendor_match:  # 70% overlap and vendor match
                                    found = tag
                                    break'''
    
    # Replace the old logic with new logic
    if old_pattern in content:
        content = re.sub(old_pattern, new_logic, content, flags=re.DOTALL)
        
        # Also update the fuzzy matching threshold
        content = content.replace('best_ratio = 0.8', 'best_ratio = 0.85')
        
        # Write back to file
        with open('app.py', 'w') as f:
            f.write(content)
        
        print("✅ Successfully updated matching logic to be more conservative!")
        print("Changes made:")
        print("- Increased word overlap threshold from 50% to 70%")
        print("- Added vendor/brand matching requirement")
        print("- Increased fuzzy matching threshold from 0.8 to 0.85")
        print("- Added more common words to filter out")
    else:
        print("❌ Could not find the matching logic section to update")

if __name__ == "__main__":
    fix_matching_logic() 