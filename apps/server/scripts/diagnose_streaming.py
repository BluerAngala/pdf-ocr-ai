#!/usr/bin/env python3
"""
流式处理器诊断脚本 - 找出为什么处理0个文件
"""
import sys
import os
import time
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.task_state import TaskStateManager, Task
from non_litigation.streaming import StreamingBatchProcessor
from core.paths import ROOT

print("="*60)
print("流式处理器诊断")
print("="*60)

# 使用第1批的样本材料
sample_root = ROOT / '样本材料' / '非诉组自动化样本材料'
input_dir = sample_root / '原始文件'

print(f"\n样本根目录: {sample_root}")
print(f"输入目录: {input_dir}")
print(f"输入目录存在: {input_dir.exists()}")

# 检查文件
auth_pdf = input_dir / '授权书.pdf'
letter_pdf = input_dir / '所函.pdf'
app_pdf = input_dir / '申请书.pdf'
evidence_dir = input_dir / '责催（证据材料）'

print(f"\n文件检查:")
print(f"  授权书.pdf: {auth_pdf.exists()} ({auth_pdf.stat().st_size / 1024 / 1024:.1f}MB)" if auth_pdf.exists() else "  授权书.pdf: 不存在")
print(f"  所函.pdf: {letter_pdf.exists()} ({letter_pdf.stat().st_size / 1024 / 1024:.1f}MB)" if letter_pdf.exists() else "  所函.pdf: 不存在")
print(f"  申请书.pdf: {app_pdf.exists()} ({app_pdf.stat().st_size / 1024 / 1024:.1f}MB)" if app_pdf.exists() else "  申请书.pdf: 不存在")
print(f"  责催目录: {evidence_dir.exists()}")

if evidence_dir.exists():
    evidence_pdfs = list(evidence_dir.glob('*.pdf'))
    print(f"  责催PDF数量: {len(evidence_pdfs)}")

# 构建几个测试任务
tasks = []
if auth_pdf.exists():
    tasks.append(Task(task_id='1081_auth', task_type='auth', source_file=str(auth_pdf), page_start=1, page_end=1, company_name='测试公司', notice_number='测试编号', sequence=1))
if letter_pdf.exists():
    tasks.append(Task(task_id='1081_letter', task_type='letter', source_file=str(letter_pdf), page_start=1, page_end=1, company_name='测试公司', notice_number='测试编号', sequence=1))
if app_pdf.exists():
    tasks.append(Task(task_id='1081_app', task_type='application', source_file=str(app_pdf), page_start=1, page_end=2, company_name='测试公司', notice_number='测试编号', sequence=1))

print(f"\n测试任务数: {len(tasks)}")

if not tasks:
    print("ERROR: 没有可用的测试任务")
    sys.exit(1)

# 创建临时数据库
db_path = Path('temp/diagnostic_state.db')
db_path.parent.mkdir(exist_ok=True)
if db_path.exists():
    db_path.unlink()

state_mgr = TaskStateManager(str(db_path))
state_mgr.insert_tasks(tasks)

print(f"\n数据库状态:")
print(f"  待处理: {len(state_mgr.get_pending(100))}")

# 创建处理器（显式打印所有日志）
from non_litigation.streaming import set_log_fn
set_log_fn(lambda m: print(f"  [STREAM] {m}"))

print("\n" + "="*60)
print("开始处理...")
print("="*60)

processor = StreamingBatchProcessor(state_mgr, max_workers=2, batch_size=10)
try:
    processor.initialize()
    print("[OK] 初始化完成")
except Exception as e:
    print(f"[FAIL] 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

start = time.perf_counter()
try:
    processor.run()
    elapsed = time.perf_counter() - start
    print(f"\n[OK] 处理完成, 耗时: {elapsed:.2f}s")
except Exception as e:
    elapsed = time.perf_counter() - start
    print(f"\n[FAIL] 处理异常, 耗时: {elapsed:.2f}s")
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()

print(f"\n处理统计:")
print(f"  处理成功: {processor._processed_count}")
print(f"  处理失败: {processor._error_count}")

print(f"\n数据库结果:")
results = state_mgr.get_all_results()
print(f"  成功结果数: {len(results)}")
for filename, data in results.items():
    print(f"  - {filename}: {data.get('total_pages', 0)} 页")

# 详细检查每个任务状态
conn = state_mgr._conn()
cursor = conn.execute("SELECT task_id, task_type, status, attempt_count, error_msg FROM tasks")
print(f"\n任务明细:")
for row in cursor.fetchall():
    status_icon = "OK" if row['status'] == 'done' else "FAIL" if row['status'] == 'error' else "PEND"
    print(f"  {status_icon} {row['task_id']} ({row['task_type']}): {row['status']} (尝试{row['attempt_count']})")
    if row['error_msg']:
        print(f"     错误: {row['error_msg']}")

# 清理
state_mgr.close()
print(f"\n诊断完成")
