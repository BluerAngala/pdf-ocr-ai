import sys
sys.stdout.reconfigure(encoding='utf-8')

files_to_fix = [
    'src/non_litigation_export.py',
    'src/non_litigation_validator.py',
    'src/smart_extractor.py',
]

# Current left: [〔\[(［]  -> need [〔\[(［【]
# Current right: [〕\)\]］] -> need [〕\)\]］】

old_left = '[\u3014\\[(\uff3b]'
new_left = '[\u3014\\[(\uff3b\u3010]'

old_right = '[\u3015\\)\\\uff3d]'
new_right = '[\u3015\\)\\\uff3d\u3011]'

for filepath in files_to_fix:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    if old_left in content:
        content = content.replace(old_left, new_left)
        modified = True
    if old_right in content:
        content = content.replace(old_right, new_right)
        modified = True
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
    else:
        print(f"No changes needed: {filepath}")
        for i, line in enumerate(content.split('\n'), 1):
            if 'NOTICE_PATTERN' in line and 'compile' in line:
                print(f"  Line {i}: {repr(line)[:300]}")
