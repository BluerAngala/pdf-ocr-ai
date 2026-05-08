import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('src/non_litigation_export.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_pattern = "NOTICE_PATTERN = re.compile(r'\u7a57\u516c\u79ef\u91d1\u4e2d\u5fc3[^\\s\uff0c\u3002\uff1b\u3001\u300a\u300b]*?\u8d23\u5b57[\u3014\\[(]\\d{4}[\u3015\\])]\\d+(?:-\\d+)?\u53f7')"
new_pattern = "NOTICE_PATTERN = re.compile(r'\u7a57\u516c\u79ef\u91d1\u4e2d\u5fc3[^\\s\uff0c\u3002\uff1b\u3001\u300a\u300b]*?\u8d23[\u4ee4\u884c]\u5b57[\u3014\\[(\uff3b]\\d{4}[\u3015\\)\uff3d]\\d+(?:-\\d+)?\u53f7')"

if old_pattern in content:
    content = content.replace(old_pattern, new_pattern)
    print("Replaced NOTICE_PATTERN in non_litigation_export.py")
else:
    print("ERROR: old pattern not found!")
    for i, line in enumerate(content.split('\n'), 1):
        if 'NOTICE_PATTERN' in line and 'compile' in line:
            print(f"  Line {i}: {repr(line)}")

with open('src/non_litigation_export.py', 'w', encoding='utf-8') as f:
    f.write(content)
