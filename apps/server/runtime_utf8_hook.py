import sys
import os

os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

for stream_name in ('stdin', 'stdout', 'stderr'):
    stream = getattr(sys, stream_name, None)
    if stream is not None and hasattr(stream, 'reconfigure'):
        try:
            mode = 'r' if stream_name == 'stdin' else 'w'
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
