import os
import re
from collections import defaultdict

# Config
EXCLUDED_FILES = ['script-skinshortcuts-includes.xml']
PATTERN = re.compile(r'<(include|variable|constant|template|default)\s+name="([^"]+)"', re.IGNORECASE)

def scan_skin():
    occurrences = defaultdict(list)
    
    for root, _, files in os.walk("."):
        for file in files:
            # Skip excluded files and non-xml files
            if file in EXCLUDED_FILES or not file.endswith(".xml"):
                continue
                
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        for match in PATTERN.finditer(line):
                            tag_type = match.group(1)
                            name_val = match.group(2)
                            occurrences[name_val].append({
                                'tag': tag_type,
                                'path': path,
                                'line': i
                            })
            except Exception as e:
                print(f"Error reading {path}: {e}")

    # Report results
    found_dupes = False
    for name, locations in occurrences.items():
        if len(locations) > 1:
            found_dupes = True
            print(f"\n[!] DUPLICATE DEFINITION: '{name}'")
            for loc in locations:
                print(f"    - <{loc['tag']}> in {loc['path']} (Line {loc['line']})")
    
    if not found_dupes:
        print("Clean! No duplicate definitions found (excluding skin-shortcuts).")

if __name__ == "__main__":
    scan_skin()