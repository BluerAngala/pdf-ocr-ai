#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务状态管理器 - 基于 SQLite 的轻量级持久化

支持：
- 断点续跑（任务粒度）
- 失败重试
- 增量保存（每任务原子提交）
- 进度统计
- 结果聚合
"""

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class Task:
    """单个 OCR 任务定义"""
    task_id: str
    task_type: str          # 'notice', 'auth', 'letter', 'application'
    source_file: str        # 原始 PDF 路径
    page_start: int = 1     # 起始页（1-based）
    page_end: int = 1       # 结束页（1-based）
    company_name: Optional[str] = None  # 台账公司名称（用于匹配验证）
    notice_number: Optional[str] = None # 台账责令号
    sequence: Optional[str] = None      # 台账序号
    
    # 运行时可变字段
    status: str = 'pending'             # pending, cutting, ocr, matching, done, error
    result_json: Optional[str] = None   # OCR 结果 JSON
    output_file: Optional[str] = None   # 最终输出文件路径
    error_msg: Optional[str] = None
    attempt_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Task":
        return cls(**{k: row[k] for k in row.keys()})


class TaskStateManager:
    """
    任务状态管理器
    
    用法：
        mgr = TaskStateManager(Path("temp/ocr_state.db"))
        
        # 批量插入任务
        mgr.insert_tasks([Task(...), Task(...)])
        
        # 取一批待处理
        batch = mgr.get_pending(batch_size=50)
        
        # 更新单个任务
        mgr.update_status("task_001", "done", result={...})
        
        # 获取汇总
        summary = mgr.get_summary()
        
        # 导出所有结果
        results = mgr.get_all_results()
    """
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()
    
    def _conn(self) -> sqlite3.Connection:
        """每个线程独立的连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=FULL")
        return self._local.conn
    
    def _init_schema(self):
        """初始化表结构"""
        conn = self._conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                source_file TEXT NOT NULL,
                page_start INTEGER DEFAULT 1,
                page_end INTEGER DEFAULT 1,
                company_name TEXT,
                notice_number TEXT,
                sequence TEXT,
                status TEXT DEFAULT 'pending',
                result_json TEXT,
                output_file TEXT,
                error_msg TEXT,
                attempt_count INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            );
            
            CREATE INDEX IF NOT EXISTS idx_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_type ON tasks(task_type);
            CREATE INDEX IF NOT EXISTS idx_created ON tasks(created_at);
            
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.commit()
    
    def insert_tasks(self, tasks: List[Task]):
        """批量插入任务（忽略已存在的）"""
        if not tasks:
            return
        
        conn = self._conn()
        now = time.time()
        
        # 使用事务批量插入
        with conn:
            for task in tasks:
                task.created_at = now
                task.updated_at = now
                conn.execute(
                    """
                    INSERT OR IGNORE INTO tasks 
                    (task_id, task_type, source_file, page_start, page_end,
                     company_name, notice_number, sequence, status,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (task.task_id, task.task_type, task.source_file,
                     task.page_start, task.page_end, task.company_name,
                     task.notice_number, task.sequence, task.status,
                     task.created_at, task.updated_at)
                )
    
    def get_pending(self, batch_size: int = 50, 
                    include_error: bool = True,
                    max_attempts: int = 2) -> List[Task]:
        """
        取一批待处理任务
        
        Args:
            batch_size: 批次大小
            include_error: 是否包含之前失败的任务（重试）
            max_attempts: 最大重试次数
        """
        conn = self._conn()
        
        statuses = ["pending"]
        if include_error:
            statuses.append("error")
        
        # 构造 IN 子句
        placeholders = ",".join("?" * len(statuses))
        
        cursor = conn.execute(
            f"""
            SELECT * FROM tasks 
            WHERE status IN ({placeholders})
              AND attempt_count <= ?
            ORDER BY created_at, task_id
            LIMIT ?
            """,
            (*statuses, max_attempts, batch_size)
        )
        
        return [Task.from_row(row) for row in cursor.fetchall()]
    
    def update_status(self, task_id: str, status: str,
                      result: Optional[Dict] = None,
                      output_file: Optional[str] = None,
                      error: Optional[str] = None):
        """原子更新单个任务状态（立即写盘）"""
        conn = self._conn()
        
        # 构建动态更新字段
        updates = ["status = ?", "updated_at = ?", "attempt_count = attempt_count + 1"]
        params = [status, time.time()]
        
        if result is not None:
            updates.append("result_json = ?")
            params.append(json.dumps(result, ensure_ascii=False))
        
        if output_file is not None:
            updates.append("output_file = ?")
            params.append(output_file)
        
        if error is not None:
            updates.append("error_msg = ?")
            params.append(error)
        
        params.append(task_id)
        
        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?"
        conn.execute(sql, params)
        conn.commit()  # 每任务独立提交，确保崩溃不丢进度
    
    def get_summary(self) -> Dict[str, Any]:
        """获取整体进度统计"""
        conn = self._conn()
        
        cursor = conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor = conn.execute("SELECT COUNT(*) FROM tasks")
        total = cursor.fetchone()[0]
        
        cursor = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'error' AND attempt_count > 2"
        )
        failed = cursor.fetchone()[0]
        
        done = status_counts.get('done', 0)
        pending = status_counts.get('pending', 0)
        error = status_counts.get('error', 0)
        
        return {
            'total': total,
            'done': done,
            'pending': pending,
            'error': error,
            'failed_permanently': failed,
            'progress': round(done / total, 4) if total else 0,
        }
    
    def get_all_results(self) -> Dict[str, Dict]:
        """
        聚合所有已完成任务的结果
        
        Returns:
            {filename: {pages: [...], total_pages: N, ...}}
        """
        conn = self._conn()
        
        cursor = conn.execute(
            "SELECT task_type, source_file, result_json FROM tasks WHERE status = 'done'"
        )
        
        results: Dict[str, Dict] = {}
        for row in cursor.fetchall():
            source_file = row['source_file']
            result_json = row['result_json']
            if not result_json:
                continue
            
            try:
                result = json.loads(result_json)
                # 按原始文件名聚合（兼容现有接口）
                filename = Path(source_file).name
                if filename not in results:
                    results[filename] = {
                        'pages': [],
                        'total_pages': 0,
                        'filename': filename,
                        'method': 'streaming_batch',
                        'total_duration': 0,
                        'full_text': '',
                    }
                
                # 合并页结果
                page_results = result.get('pages', [])
                results[filename]['pages'].extend(page_results)
                results[filename]['total_pages'] += len(page_results)
                results[filename]['total_duration'] += result.get('duration', 0)
                if result.get('full_text'):
                    if results[filename]['full_text']:
                        results[filename]['full_text'] += '\n' + result['full_text']
                    else:
                        results[filename]['full_text'] = result['full_text']
            except json.JSONDecodeError:
                continue
        
        return results
    
    def get_failed_tasks(self) -> List[Task]:
        """获取永久失败的任务（超过重试次数）"""
        conn = self._conn()
        cursor = conn.execute(
            "SELECT * FROM tasks WHERE status = 'error' AND attempt_count > 2 ORDER BY created_at"
        )
        return [Task.from_row(row) for row in cursor.fetchall()]
    
    def clear_all(self):
        """清空所有任务（用于强制重跑）"""
        conn = self._conn()
        conn.execute("DELETE FROM tasks")
        conn.commit()
    
    def set_meta(self, key: str, value: str):
        """存储元数据"""
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()
    
    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """读取元数据"""
        conn = self._conn()
        cursor = conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default
    
    def close(self):
        """关闭连接"""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
