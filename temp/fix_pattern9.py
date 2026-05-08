import sys
sys.stdout.reconfigure(encoding='utf-8')

# Fix: [〕\)\］】] should be [〕\)\]］】]
# Need to add \] before ］ to match halfwidth ]

files = [
    'src/non_litigation_export.py',
    'src/non_litigation_validator.py',
    'src/smart_extractor.py',
]

# In the raw string, the right bracket class looks like:
# [〕\)\］】]  -> missing \] for halfwidth ]
# Should be: [〕\)\]］】]

old_right = '[〕\\)\\］】]'
new_right = '[〕\\)\\]\\uff3d\\u3011]'

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if old_right in content:
        content = content.replace(old_right, new_right)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
    else:
        print(f"Not found in: {filepath}")
        for i, line in enumerate(content.split('\n'), 1):
            if 'NOTICE_PATTERN' in line and 'compile' in line:
                print(f"  Line {i}: {repr(line)[:300]}")
