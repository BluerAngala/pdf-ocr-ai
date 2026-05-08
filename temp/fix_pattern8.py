import sys
sys.stdout.reconfigure(encoding='utf-8')

# Read the current content
with open('src/non_litigation_export.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the old right bracket class
# Current: [〕\)\]\uff3d]  (after \d{4})
# The actual bytes in file: [〕\)\]］]
# Wait, the read tool showed: [〕\)\]\uff3d]
# But \uff3d is ］ (fullwidth ])... hmm
# Let me check character by character

line52 = content.split('\n')[51]  # 0-indexed
print('Line 52:', repr(line52))

# Find the part after \d{4}
import re as re_mod
m = re_mod.search(r'\\d\{4\}(\[.*?\])\\d', line52)
if m:
    print('Right bracket class:', repr(m.group(1)))
    
# Replace \uff3d with ］】 in the right bracket class
# The file has \uff3d as literal text, not as the character ］
# So we need to replace the literal text "\uff3d" with "］】"

old = r'\uff3d]'
new = '］】]'

if old in content:
    content = content.replace(old, new)
    print('Replaced \\uff3d with ］】')
else:
    print('Literal \\uff3d not found')
    # Maybe it's the actual char ］
    old2 = '］]'
    # Check if ］ is in the right bracket class
    # Nah, let me just find the pattern and replace the whole thing

# Just do a direct regex replacement on the NOTICE_PATTERN line
old_pattern_text = "r'\\u7a57\\u516c\\u79ef\\u91d1\\u4e2d\\5fc3"
# This is getting too complicated. Let me just rebuild the line.

# Find the line with NOTICE_PATTERN
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'NOTICE_PATTERN' in line and 'compile' in line and '穗公积金中心' in line:
        print(f'Found at line {i+1}: {repr(line[:100])}...')
        # Build the new line
        new_line = "NOTICE_PATTERN = re.compile(r'\u7a57\u516c\u79ef\u91d1\u4e2d\u5fc3[^\\s\uff0c\u3002\uff1b\u3001\u300a\u300b]*?\u8d23\u5b57[\u3014\\[(\uff3b\u3010]\\d{4}[\u3015\\)\\\uff3d\u3011]\\d+(?:-\\d+)?\u53f7')"
        lines[i] = new_line
        print(f'New line: {repr(new_line[:100])}...')
        break

content = '\n'.join(lines)
with open('src/non_litigation_export.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
