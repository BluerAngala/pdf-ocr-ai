import sys
sys.stdout.reconfigure(encoding='utf-8')

files_to_fix = [
    'src/non_litigation_export.py',
    'src/non_litigation_validator.py',
    'src/smart_extractor.py',
]

# Current: [〕\)\］]  (matches 〕, ), ［ fullwidth)
# Target:  [〕\)\]］] (matches 〕, ), ], ］ fullwidth)
# In the raw string, \) is escaped ), \] is escaped ], ］ is fullwidth
# The actual bytes in the file are: 〔\\)\\］]
# But we need: 〔\\)\\]\\uFF3D]
# Wait - let me check what's actually in the file

for filepath in files_to_fix:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    for i, line in enumerate(content.split('\n'), 1):
        if 'NOTICE_PATTERN' in line and 'compile' in line:
            # Find the right bracket class
            # Looking for the pattern between the year \d{4} and \d+
            idx = line.find('\\d{4}')
            if idx > 0:
                right_part = line[idx:idx+30]
                print(f"{filepath} Line {i}: ...{right_part}...")

# Now do the replacement
# The right bracket class in the file raw string is: [\〕\\)\\］]
# Wait no. Let me be more precise.
# In raw string r'...[〕\)\］]...'
# Python reads this as char class containing: 〕, ), ］
# We need: r'...[〕\)\]］]...'
# Which means char class: 〕, ), ], ］

old_part = '[〕\\)\\］]'
new_part = '[〕\\)\\]\\uff3d]'

for filepath in files_to_fix:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if old_part in content:
        content = content.replace(old_part, new_part)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
    else:
        print(f"Not found: {filepath}")
        # Try with actual chars
        print(f"  Looking for: {repr(old_part)}")
