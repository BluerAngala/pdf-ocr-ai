# 准确度优先的大规模处理优化方案

## 核心原则

**准确度 > 速度**：法律文书识别不能出错，宁可慢也要准。

---

## 一、智能区域识别（带回退机制）

### 设计思路

```
区域识别（快） → 验证结果 → 如果失败 → 全页识别（准）
```

### 1.1 责催文件优化

**问题**：责令号通常在页眉，但扫描偏差可能导致位置变化

**方案**：
```python
def extract_notice_number_robust(pdf_path):
    """鲁棒的责令号提取 - 区域识别 + 回退机制"""
    
    # 第一步：尝试pdfplumber直接提取（最快）
    text = try_pdfplumber_extract(pdf_path, max_pages=3)
    if find_notice_number(text):
        return result
    
    # 第二步：区域OCR（页面上半部分）
    for page_num in range(1, 4):
        # 识别页面上半部分（责令号通常在页眉）
        region_text = ocr_region(pdf_path, page_num, region='top_50%')
        notice = find_notice_number(region_text)
        
        if notice:
            # 验证格式
            if validate_notice_number(notice):
                return notice
            else:
                # 格式不对，可能是OCR错误，回退到全页
                full_text = ocr_full_page(pdf_path, page_num)
                return find_notice_number(full_text)
    
    # 第三步：全页OCR（最准）
    return ocr_full_pages_until_found(pdf_path, max_pages=3)
```

**关键点**：
- ✅ 先尝试快速方法
- ✅ 验证结果格式
- ✅ 失败自动回退
- ✅ 保证准确度

---

### 1.2 申请书优化

**问题**：只需要识别标题，但扫描偏差可能导致标题位置变化

**方案**：
```python
def extract_application_info_robust(pdf_path):
    """鲁棒的申请书信息提取"""
    
    results = []
    for page_num in range(1, total_pages + 1):
        # 第一步：区域识别（页面前20%）
        title_region = ocr_region(pdf_path, page_num, region='top_20%')
        
        if '强制执行申请书' in title_region:
            # 验证：检查是否还有其他关键字
            if validate_application_title(title_region):
                results.append(page_num)
            else:
                # 验证失败，回退到全页
                full_text = ocr_full_page(pdf_path, page_num)
                if '强制执行申请书' in full_text:
                    results.append(page_num)
        
        # 如果没找到，也做全页OCR（确保不遗漏）
        elif page_num in odd_pages:  # 只检查奇数页（申请书通常是奇数页开头）
            full_text = ocr_full_page(pdf_path, page_num)
            if '强制执行申请书' in full_text:
                results.append(page_num)
    
    return results
```

**关键点**：
- ✅ 区域识别优先
- ✅ 验证关键字
- ✅ 奇数页检查（申请书通常从奇数页开始）
- ✅ 回退到全页OCR

---

### 1.3 授权书/所函优化

**问题**：公司名称位置不固定，扫描偏差影响更大

**方案**：
```python
def extract_company_name_robust(pdf_path, page_num):
    """鲁棒的公司名称提取"""
    
    # 第一步：尝试多个区域
    regions = [
        ('middle_40%', '中间区域'),
        ('top_30%', '页眉区域'),
        ('bottom_30%', '页脚区域'),
    ]
    
    for region, desc in regions:
        text = ocr_region(pdf_path, page_num, region=region)
        company = extract_company_name(text)
        
        if company:
            # 验证公司名称格式
            if validate_company_name(company):
                return company
    
    # 第二步：全页OCR（确保不遗漏）
    full_text = ocr_full_page(pdf_path, page_num)
    return extract_company_name(full_text)
```

**关键点**：
- ✅ 尝试多个区域（中间、页眉、页脚）
- ✅ 验证公司名称格式
- ✅ 回退到全页OCR

---

## 二、多线程任务队列设计

### 2.1 任务队列架构

```
任务队列（线程安全）
    ↓
任务分发器（智能调度）
    ↓
工作线程池（并发处理）
    ↓
结果收集器（线程安全）
    ↓
进度追踪器（实时更新）
```

### 2.2 核心实现

```python
from queue import PriorityQueue, Empty
from threading import Lock, Event
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import IntEnum
import time

class TaskPriority(IntEnum):
    """任务优先级"""
    HIGH = 1      # 责催文件（必须串行）
    NORMAL = 2    # 申请书
    LOW = 3       # 授权书、所函

@dataclass(order=True)
class Task:
    """处理任务"""
    priority: int
    task_id: str = field(compare=False)
    file_type: str = field(compare=False)
    file_path: Path = field(compare=False)
    retry_count: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)

class TaskQueue:
    """线程安全的任务队列"""
    
    def __init__(self, max_workers: int = 4):
        self.queue = PriorityQueue()
        self.lock = Lock()
        self.results: Dict[str, Dict] = {}
        self.results_lock = Lock()
        self.stop_event = Event()
        self.max_workers = max_workers
        
        # 统计信息
        self.stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0,
        }
        self.stats_lock = Lock()
    
    def add_task(self, task: Task):
        """添加任务"""
        with self.lock:
            self.queue.put(task)
            with self.stats_lock:
                self.stats['total'] += 1
    
    def get_task(self, timeout: float = 1.0) -> Optional[Task]:
        """获取任务（阻塞）"""
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None
    
    def task_done(self):
        """标记任务完成"""
        self.queue.task_done()
    
    def save_result(self, task_id: str, result: Dict):
        """保存结果（线程安全）"""
        with self.results_lock:
            self.results[task_id] = result
        with self.stats_lock:
            self.stats['completed'] += 1
    
    def mark_failed(self, task_id: str, error: str):
        """标记失败"""
        with self.stats_lock:
            self.stats['failed'] += 1
        print(f"❌ 任务失败: {task_id}, 错误: {error}")
    
    def get_progress(self) -> Dict:
        """获取进度"""
        with self.stats_lock:
            return {
                'total': self.stats['total'],
                'completed': self.stats['completed'],
                'failed': self.stats['failed'],
                'progress': f"{self.stats['completed']}/{self.stats['total']}",
                'percentage': f"{self.stats['completed'] / max(self.stats['total'], 1) * 100:.1f}%"
            }
```

### 2.3 工作线程

```python
class WorkerThread(threading.Thread):
    """工作线程"""
    
    def __init__(self, task_queue: TaskQueue, worker_id: int):
        super().__init__()
        self.task_queue = task_queue
        self.worker_id = worker_id
        self.daemon = True  # 守护线程
    
    def run(self):
        """线程主循环"""
        print(f"🔄 工作线程 {self.worker_id} 启动")
        
        while not self.task_queue.stop_event.is_set():
            task = self.task_queue.get_task()
            
            if task is None:
                continue
            
            try:
                # 处理任务
                result = self.process_task(task)
                
                # 保存结果
                self.task_queue.save_result(task.task_id, result)
                
                # 标记完成
                self.task_queue.task_done()
                
                # 打印进度
                progress = self.task_queue.get_progress()
                print(f"✅ [{progress['progress']}] {task.task_id} 完成")
                
            except Exception as e:
                # 重试逻辑
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    print(f"⚠️ 重试 {task.retry_count}/{task.max_retries}: {task.task_id}")
                    self.task_queue.add_task(task)
                else:
                    self.task_queue.mark_failed(task.task_id, str(e))
                
                self.task_queue.task_done()
    
    def process_task(self, task: Task) -> Dict:
        """处理单个任务"""
        if task.file_type == 'notice':
            return extract_notice_number_robust(task.file_path)
        elif task.file_type == 'application':
            return extract_application_info_robust(task.file_path)
        elif task.file_type == 'authorization':
            return extract_company_name_robust(task.file_path)
        elif task.file_type == 'letter':
            return extract_company_name_robust(task.file_path)
        else:
            raise ValueError(f"未知文件类型: {task.file_type}")
```

### 2.4 任务调度器

```python
class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, max_workers: int = 4):
        self.task_queue = TaskQueue(max_workers)
        self.workers: List[WorkerThread] = []
    
    def start(self):
        """启动工作线程"""
        for i in range(self.task_queue.max_workers):
            worker = WorkerThread(self.task_queue, i)
            worker.start()
            self.workers.append(worker)
    
    def add_tasks_from_cases(self, cases: List[Dict]):
        """从案件列表添加任务"""
        for i, case in enumerate(cases):
            # 责催文件（高优先级）
            for j in range(1, 4):
                task = Task(
                    priority=TaskPriority.HIGH,
                    task_id=f"notice_{j}",
                    file_type='notice',
                    file_path=Path(f"input/{j}.pdf")
                )
                self.task_queue.add_task(task)
            
            # 申请书（普通优先级）
            task = Task(
                priority=TaskPriority.NORMAL,
                task_id=f"application_{i}",
                file_type='application',
                file_path=Path("input/申请书.pdf")
            )
            self.task_queue.add_task(task)
            
            # 授权书、所函（低优先级）
            # ...
    
    def wait_completion(self, timeout: float = None):
        """等待所有任务完成"""
        self.task_queue.queue.join()
    
    def stop(self):
        """停止所有工作线程"""
        self.task_queue.stop_event.set()
        for worker in self.workers:
            worker.join(timeout=5.0)
```

---

## 三、断点续传机制

### 3.1 检查点设计

```python
@dataclass
class Checkpoint:
    """处理检查点"""
    timestamp: str
    total_cases: int
    processed_cases: List[str]
    failed_cases: List[Dict]
    results: Dict[str, Dict]
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'total_cases': self.total_cases,
            'processed_cases': self.processed_cases,
            'failed_cases': self.failed_cases,
            'results': self.results,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Checkpoint':
        return cls(**data)

class CheckpointManager:
    """检查点管理器"""
    
    def __init__(self, checkpoint_file: Path):
        self.checkpoint_file = checkpoint_file
        self.checkpoint: Optional[Checkpoint] = None
        self.lock = Lock()
    
    def load(self) -> Optional[Checkpoint]:
        """加载检查点"""
        if self.checkpoint_file.exists():
            try:
                data = json.loads(self.checkpoint_file.read_text(encoding='utf-8'))
                self.checkpoint = Checkpoint.from_dict(data)
                return self.checkpoint
            except Exception as e:
                print(f"⚠️ 加载检查点失败: {e}")
                return None
        return None
    
    def save(self, checkpoint: Checkpoint):
        """保存检查点（线程安全）"""
        with self.lock:
            self.checkpoint = checkpoint
            self.checkpoint_file.write_text(
                json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
    
    def update(self, case_id: str, result: Dict):
        """更新检查点（实时保存）"""
        with self.lock:
            if self.checkpoint is None:
                return
            
            self.checkpoint.processed_cases.append(case_id)
            self.checkpoint.results[case_id] = result
            
            # 实时保存
            self.save(self.checkpoint)
    
    def mark_failed(self, case_id: str, error: str):
        """标记失败案件"""
        with self.lock:
            if self.checkpoint is None:
                return
            
            self.checkpoint.failed_cases.append({
                'case_id': case_id,
                'error': error,
                'timestamp': datetime.now().isoformat(),
            })
            
            self.save(self.checkpoint)
    
    def get_pending_cases(self, all_cases: List[str]) -> List[str]:
        """获取待处理案件"""
        if self.checkpoint is None:
            return all_cases
        
        processed = set(self.checkpoint.processed_cases)
        return [case for case in all_cases if case not in processed]
```

### 3.2 断点续传流程

```python
class BatchProcessor:
    """批量处理器（支持断点续传）"""
    
    def __init__(self, checkpoint_file: Path = Path('checkpoint.json')):
        self.checkpoint_manager = CheckpointManager(checkpoint_file)
        self.task_scheduler = TaskScheduler(max_workers=4)
    
    def process_batch(self, cases: List[Dict]):
        """批量处理"""
        
        # 1. 加载检查点
        checkpoint = self.checkpoint_manager.load()
        
        if checkpoint:
            print(f"📋 发现检查点: {checkpoint.timestamp}")
            print(f"✅ 已处理: {len(checkpoint.processed_cases)}/{checkpoint.total_cases}")
            
            # 2. 获取待处理案件
            pending_cases = self.checkpoint_manager.get_pending_cases(cases)
            print(f"⏳ 待处理: {len(pending_cases)} 个案件")
            
            if not pending_cases:
                print("✅ 所有案件已处理完成！")
                return checkpoint.results
        else:
            # 3. 创建新检查点
            checkpoint = Checkpoint(
                timestamp=datetime.now().isoformat(),
                total_cases=len(cases),
                processed_cases=[],
                failed_cases=[],
                results={},
            )
            self.checkpoint_manager.save(checkpoint)
            pending_cases = cases
        
        # 4. 启动任务调度器
        self.task_scheduler.start()
        
        # 5. 添加任务
        self.task_scheduler.add_tasks_from_cases(pending_cases)
        
        # 6. 等待完成
        try:
            self.task_scheduler.wait_completion()
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断，保存进度...")
            self.task_scheduler.stop()
        
        # 7. 返回结果
        return self.task_scheduler.task_queue.results
    
    def retry_failed(self):
        """重试失败案件"""
        checkpoint = self.checkpoint_manager.load()
        
        if not checkpoint or not checkpoint.failed_cases:
            print("✅ 没有失败案件需要重试")
            return
        
        print(f"🔄 重试 {len(checkpoint.failed_cases)} 个失败案件")
        
        # 重新处理失败案件
        for failed in checkpoint.failed_cases:
            # ... 重试逻辑
            pass
```

---

## 四、完整流程

```python
def main():
    """主流程"""
    
    # 1. 初始化
    processor = BatchProcessor(checkpoint_file=Path('checkpoint.json'))
    
    # 2. 加载案件
    cases = load_non_litigation_cases(excel_path)
    print(f"📋 加载 {len(cases)} 个案件")
    
    # 3. 批量处理（支持断点续传）
    results = processor.process_batch(cases)
    
    # 4. 生成报告
    generate_report(results)
    
    # 5. 重试失败案件（如果有）
    processor.retry_failed()

if __name__ == '__main__':
    main()
```

---

## 五、预期效果

| 优化项 | 效果 | 风险控制 |
|--------|------|---------|
| 智能区域识别 | 提速40-60% | 回退机制保证准确度 |
| 多线程任务队列 | 提速3-4倍 | 任务队列避免资源竞争 |
| 断点续传 | 支持中断续传 | 实时保存进度 |

**综合效果**：
- 1000案件：24小时 → **4-6小时**
- 准确度：**99%+**（回退机制保证）

---

## 六、实施计划

### 第一阶段（1天）
- ✅ 实现智能区域识别（带回退机制）
- ✅ 测试准确度（样本验证）

### 第二阶段（1天）
- ✅ 实现多线程任务队列
- ✅ 压力测试（100案件）

### 第三阶段（半天）
- ✅ 实现断点续传
- ✅ 集成测试

---

## 七、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 区域识别遗漏信息 | 高 | 回退到全页OCR |
| 多线程资源竞争 | 中 | 线程安全设计 |
| 检查点损坏 | 中 | 定期备份 + 多版本 |
| 内存占用高 | 低 | 分批处理 |

---

## 八、下一步

你希望我：
1. 立即实施第一阶段（智能区域识别 + 回退机制）？
2. 还是先看其他部分的详细设计？
