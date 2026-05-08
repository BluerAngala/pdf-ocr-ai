import sys
sys.stdout.reconfigure(encoding='utf-8')

files_to_fix = [
    'src/non_litigation_validator.py',
    'src/smart_extractor.py',
]

old_pattern = "NOTICE_PATTERN = re.compile(r'\u7a57\u516c\u79ef\u91d1\u4e2d\u5fc3[^\\s\uff0c\u3002\uff1b\u3001\u300a\u300b]*?\u8d23\u5b57[\u3014\\[(]\\d{4}[\u3015\\])]\\d+(?:-\\d+)?\u53f7')"
new_pattern = "NOTICE_PATTERN = re.compile(r'\u7a57\u516c\u79ef\u91d1\u4e2d\u5fc3[^\\s\uff0c\u3002\uff1b\u3001\u300a\u300b]*?\u8d23[\u4ee4\u884c]\u5b57[\u3014\\[(\uff3b]\\d{4}[\u3015\\)\uff3d]\\d+(?:-\\d+)?\u53f7')"

for filepath in files_to_fix:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
    else:
        print(f"Pattern not found in: {filepath}")
        for i, line in enumerate(content.split('\n'), 1):
            if 'NOTICE_PATTERN' in line and 'compile' in line:
                print(f"  Line {i}: {repr(line)}")
