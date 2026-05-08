import sys, re as re_mod
sys.stdout.reconfigure(encoding='utf-8')

files = [
    'src/non_litigation_validator.py',
    'src/smart_extractor.py',
]

target_right_class = '[\u3015\\)\\]\uff3d\u3011]'

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    def replace_right_class(match):
        return match.group(1) + target_right_class + match.group(2)
    
    new_content = re_mod.sub(
        r'(\\d\{4\})\[.*?\](\\d)',
        replace_right_class,
        content
    )
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed: {filepath}")
    else:
        print(f"No change: {filepath}")
        for i, line in enumerate(content.split('\n'), 1):
            if 'NOTICE_PATTERN' in line and 'compile' in line:
                print(f"  Line {i}: {repr(line)[:300]}")
