# 公积金 OCR 工具 - Tauri 桌面应用设计文档

## 1. 项目概述

将现有的 Python OCR 识别工具改造为 Tauri + Python 后端架构的桌面应用，提供友好的图形界面。

## 2. 架构设计

### 2.1 技术栈

- **前端**: Tauri (Rust) + React/Vue + TypeScript
- **后端**: Python + jsonrpcserver
- **通信**: JSON-RPC over Stdio (stdin/stdout/stderr)
- **UI 框架**: 推荐使用 shadcn/ui 或 Tailwind CSS

### 2.2 通信机制

```
Tauri (Rust) ←→ Python 子进程
     │              │
     │  stdin       │  stdout (响应)
     │─────────────→│
     │              │
     │  stderr      │  stderr (进度推送)
     │←─────────────│
```

## 3. API 接口设计

### 3.1 OCR 模块

#### `ocr.recognize`
单文件 OCR 识别

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "ocr.recognize",
  "params": {
    "file_path": "C:/.../document.pdf",
    "force_ocr": false,
    "doc_type": "申请书"
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "filename": "document.pdf",
    "total_pages": 5,
    "pages": [
      {
        "page": 1,
        "text": "...",
        "method": "pdfplumber",
        "duration": 0.5
      }
    ],
    "full_text": "...",
    "case_numbers": ["穗公积金中心责字〔2024〕1号"],
    "total_duration": 2.5
  },
  "id": 1
}
```

#### `ocr.recognize_batch`
批量 OCR 识别

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "ocr.recognize_batch",
  "params": {
    "file_paths": ["1.pdf", "2.pdf"],
    "parallel": true
  },
  "id": 2
}
```

### 3.2 非诉审查模块

#### `non_litigation.process`
完整处理流程

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "non_litigation.process",
  "params": {
    "sample_root": "C:/.../样本材料",
    "mode": "real_ocr",
    "force": false,
    "batch_name": "batch1"
  },
  "id": 3
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "summary": {
      "sample_root": "...",
      "result_root": "...",
      "runtime_seconds": 45.2,
      "mode": "real_ocr",
      "created_count": 100,
      "quality": {
        "total_files": 100,
        "page_count_matched": 98,
        "page_count_match_rate": 0.98
      },
      "validation": {
        "total": 100,
        "passed": 95,
        "warnings": 3,
        "failed": 2,
        "pass_rate": 0.95
      }
    },
    "html_report_path": "..."
  },
  "id": 3
}
```

#### `non_litigation.get_cases`
获取案件列表

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "non_litigation.get_cases",
  "params": {
    "sample_root": "C:/.../样本材料"
  },
  "id": 4
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "cases": [
      {
        "sequence": 1,
        "notice_number": "穗公积金中心责字〔2024〕1号",
        "company_name": "某某有限公司",
        "source_files": {
          "责催": "1.pdf",
          "申请书": "申请书.pdf",
          "授权书": "授权书.pdf",
          "所函": "所函.pdf"
        }
      }
    ]
  },
  "id": 4
}
```

#### `non_litigation.preview_split`
预览 PDF 分割结果

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "non_litigation.preview_split",
  "params": {
    "doc_type": "申请书",
    "pdf_path": "C:/.../申请书.pdf",
    "expected_count": 25
  },
  "id": 5
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "total_pages": 50,
    "expected_count": 25,
    "detected_ranges": [
      {
        "start": 1,
        "end": 3,
        "preview_text": "强制执行申请书..."
      }
    ],
    "confidence": 0.95
  },
  "id": 5
}
```

### 3.3 强制执行模块

#### `enforcement.extract`
从裁定书提取信息

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "enforcement.extract",
  "params": {
    "input_dir": "C:/.../裁定书",
    "excel_path": "C:/.../台账.xlsx"
  },
  "id": 6
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "processed": 10,
    "extracted": [
      {
        "file_name": "裁定1.pdf",
        "court_case_number": "（2024）粤01行审123号",
        "notice_number": "穗公积金中心责字〔2024〕1号",
        "amount": "50000",
        "ruling_date": "二〇二四年三月十五日",
        "judge": "张三",
        "clerk": "李四"
      }
    ],
    "updated_excel_path": "C:/.../台账_已更新.xlsx"
  },
  "id": 6
}
```

### 3.4 配置模块

#### `config.get`
获取配置

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "config.get",
  "params": {},
  "id": 7
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "doc_types": [
      {
        "key": "责催",
        "pages_per_case": null,
        "filename_pattern": "{sequence}-责催-{notice_number}.pdf"
      }
    ],
    "regex_patterns": {
      "notice_number": "..."
    },
    "ocr_corrections": [
      {"wrong": "住房公积全", "correct": "住房公积金"}
    ],
    "validation": {
      "fuzzy_match_threshold": 0.85
    }
  },
  "id": 7
}
```

#### `config.set_corrections`
设置 OCR 纠错词表

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "config.set_corrections",
  "params": {
    "corrections": [
      {"wrong": "新错误", "correct": "新正确"}
    ]
  },
  "id": 8
}
```

#### `config.reload`
重新加载配置

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "config.reload",
  "params": {},
  "id": 9
}
```

### 3.5 文件操作模块

#### `file.select_folder`
选择文件夹（Rust 实现，通过 Tauri API）

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "canceled": false,
    "folder_path": "C:/.../样本材料"
  },
  "id": 10
}
```

#### `file.select_files`
选择文件

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "file.select_files",
  "params": {
    "multiple": true,
    "filters": [
      {"name": "PDF", "extensions": ["pdf"]},
      {"name": "Excel", "extensions": ["xlsx", "xls"]}
    ]
  },
  "id": 11
}
```

#### `file.get_recent_folders`
获取最近使用的文件夹

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "file.get_recent_folders",
  "params": {},
  "id": 12
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "folders": [
      {
        "path": "C:/.../样本材料",
        "name": "样本材料",
        "last_used": "2024-01-15T10:30:00Z"
      }
    ]
  },
  "id": 12
}
```

### 3.6 系统模块

#### `system.get_status`
获取系统状态

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "system.get_status",
  "params": {},
  "id": 13
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "python_version": "3.12.0",
    "ocr_engine_ready": true,
    "poppler_installed": true,
    "config_loaded": true,
    "available_memory_gb": 8.5
  },
  "id": 13
}
```

#### `system.check_dependencies`
检查依赖

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "system.check_dependencies",
  "params": {},
  "id": 14
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "all_ready": true,
    "dependencies": [
      {
        "name": "RapidOCR",
        "installed": true,
        "version": "1.2.0"
      },
      {
        "name": "Poppler",
        "installed": true
      },
      {
        "name": "pdfplumber",
        "installed": true,
        "version": "0.10.0"
      }
    ]
  },
  "id": 14
}
```

## 4. 实时进度推送

### 4.1 进度通知（Server → Client）

Python 通过 **stderr** 推送进度消息：

```json
{
  "jsonrpc": "2.0",
  "method": "notify.progress",
  "params": {
    "task_id": "nl-2024-001",
    "phase": "ocr_cache",
    "status": "running",
    "current": 3,
    "total": 5,
    "message": "正在识别: 申请书.pdf",
    "detail": {
      "file_name": "申请书.pdf",
      "doc_type": "申请书",
      "duration_ms": 2500
    }
  }
}
```

### 4.2 日志通知

```json
{
  "jsonrpc": "2.0",
  "method": "notify.log",
  "params": {
    "level": "info",
    "message": "开始处理批次: batch1",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### 4.3 任务完成通知

```json
{
  "jsonrpc": "2.0",
  "method": "notify.task_complete",
  "params": {
    "task_id": "nl-2024-001",
    "success": true,
    "result": {
      "created_count": 100,
      "pass_rate": 0.95
    }
  }
}
```

## 5. 错误处理

### 5.1 错误响应格式

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "OCR 引擎错误",
    "data": {
      "type": "ocr_failed",
      "detail": "无法识别文件: 1.pdf",
      "suggestion": "请检查文件是否为有效的 PDF",
      "path": "C:/.../1.pdf"
    }
  },
  "id": 1
}
```

### 5.2 错误码定义

| 错误码 | 名称 | 说明 |
|--------|------|------|
| -32700 | PARSE_ERROR | JSON 解析错误 |
| -32600 | INVALID_REQUEST | 无效请求 |
| -32601 | METHOD_NOT_FOUND | 方法不存在 |
| -32602 | INVALID_PARAMS | 参数错误 |
| -32603 | INTERNAL_ERROR | 内部错误 |
| -32001 | OCR_ENGINE_ERROR | OCR 引擎错误 |
| -32002 | FILE_NOT_FOUND | 文件不存在 |
| -32003 | CONFIG_ERROR | 配置错误 |
| -32004 | DEPENDENCY_MISSING | 依赖缺失 |
| -32005 | POPPLER_NOT_INSTALLED | Poppler 未安装 |
| -32006 | EXCEL_PARSE_ERROR | Excel 解析错误 |
| -32007 | PDF_PROCESS_ERROR | PDF 处理错误 |

## 6. 数据流和状态管理

### 6.1 前端状态架构

```typescript
// stores/task.ts
interface TaskState {
  currentTask: {
    id: string;
    type: "non_litigation" | "enforcement" | "ocr";
    status: "idle" | "running" | "paused" | "completed" | "error";
    progress: {
      phase: string;
      current: number;
      total: number;
      message: string;
    };
  } | null;
  
  taskHistory: Array<{
    id: string;
    type: string;
    start_time: string;
    end_time?: string;
    success?: boolean;
    summary?: any;
  }>;
  
  logs: Array<{
    level: string;
    message: string;
    timestamp: string;
  }>;
}

// stores/config.ts
interface ConfigState {
  config: Config | null;
  loading: boolean;
  lastModified: string;
}

// stores/file.ts
interface FileState {
  recentFolders: RecentFolder[];
  selectedInputFolder: string | null;
  selectedOutputFolder: string | null;
  selectedExcelFile: string | null;
}
```

### 6.2 核心数据流

```
用户操作（选择文件夹 → 点击开始）
    ↓
前端：调用 Rust Command (invoke('start_non_litigation'))
    - 验证输入路径
    - 生成 task_id
    ↓
Rust：启动/复用 Python 子进程
    - 通过 stdin 发送 JSON-RPC 请求
    - 注册 task_id → frontend callback 映射
    ↓
Python：接收请求，开始处理
    - 启动后台线程处理任务
    - 通过 stderr 推送进度通知
    ↓
Rust：解析 stderr 中的 JSON-RPC 通知
    - 通过 Tauri Event 转发到前端
    ↓
前端：监听 Tauri Event ('progress', 'log', 'task_complete')
    - 更新 Pinia store
    - UI 自动响应式更新
```

## 7. UI 设计

### 7.1 配色方案

| 角色 | 色值 | 用途 |
|------|------|------|
| Primary | `#0D9488` | 主按钮、进度条 |
| Secondary | `#14B8A6` | 次级按钮、图标 |
| CTA | `#F97316` | 开始按钮、重要操作 |
| Background | `#F0FDFA` | 页面背景 |
| Surface | `#FFFFFF` | 卡片背景 |
| Text Primary | `#134E4A` | 主要文字 |
| Text Secondary | `#5EEAD4` | 次要文字 |
| Border | `#99F6E4` | 边框 |
| Success | `#22C55E` | 成功状态 |
| Warning | `#EAB308` | 警告状态 |
| Error | `#EF4444` | 错误状态 |

### 7.2 字体

- **字体族**: Plus Jakarta Sans
- **字重**: 300, 400, 500, 600, 700

### 7.3 页面结构

```
┌─────────────────────────────────────────────────────────────┐
│  🏠 公积金 OCR 工具                              [设置] [关于] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📁 输入设置                                         │   │
│  │                                                     │   │
│  │  样本材料文件夹:  [C:\...\样本材料    ] [浏览...]    │   │
│  │  台账 Excel:      [C:\...\台账.xlsx  ] [浏览...]    │   │
│  │                                                     │   │
│  │  [ ] 使用 Mock 模式（快速测试）                      │   │
│  │  [ ] 强制重新 OCR（忽略缓存）                        │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ▶️ 操作                                            │   │
│  │                                                     │   │
│  │  [开始非诉审查处理]  [开始强制执行提取]  [仅 OCR 识别] │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📊 处理进度                                         │   │
│  │                                                     │   │
│  │  当前阶段: OCR 识别 (3/5 文件)                       │   │
│  │  [████████████████████░░░░░░░░░░] 60%               │   │
│  │                                                     │   │
│  │  正在处理: 申请书.pdf                                │   │
│  │  预计剩余: 约 30 秒                                  │   │
│  │                                                     │   │
│  │  [详细日志 ▼]                                        │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │ [12:34:05] 开始识别: 1.pdf                  │   │   │
│  │  │ [12:34:07] 识别完成: 1.pdf (2.1s)           │   │   │
│  │  │ [12:34:07] 开始识别: 申请书.pdf             │   │   │
│  │  │ ...                                         │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ✅ 处理结果                                         │   │
│  │                                                     │   │
│  │  生成文件: 100 个                                    │   │
│  │  页数匹配: 98/100 (98%)                              │   │
│  │  验证通过: 95/100 (95%)                              │   │
│  │                                                     │   │
│  │  [查看报告] [打开输出文件夹] [导出结果]               │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 8. 项目结构

```
pdf-recognition-app/
├── apps/
│   ├── desktop/                     # Tauri 桌面应用
│   │   ├── src-tauri/               # Rust 代码
│   │   │   ├── src/
│   │   │   │   ├── main.rs          # 入口
│   │   │   │   ├── python_service.rs # Python 进程管理
│   │   │   │   ├── jsonrpc.rs       # JSON-RPC 客户端
│   │   │   │   └── commands.rs      # Tauri 命令
│   │   │   ├── Cargo.toml
│   │   │   └── tauri.conf.json
│   │   ├── src/                     # 前端代码
│   │   │   ├── components/
│   │   │   │   ├── FileSelector.tsx
│   │   │   │   ├── ProgressPanel.tsx
│   │   │   │   ├── ResultPanel.tsx
│   │   │   │   └── LogViewer.tsx
│   │   │   ├── pages/
│   │   │   │   └── Home.tsx
│   │   │   ├── stores/
│   │   │   │   ├── taskStore.ts
│   │   │   │   ├── configStore.ts
│   │   │   │   └── fileStore.ts
│   │   │   ├── App.tsx
│   │   │   └── main.tsx
│   │   ├── package.json
│   │   └── tailwind.config.js
│   │
│   └── server/                      # Python 后端服务
│       ├── pyproject.toml
│       ├── src/
│       │   ├── server.py            # JSON-RPC 服务入口
│       │   ├── methods/
│       │   │   ├── __init__.py
│       │   │   ├── ocr.py
│       │   │   ├── non_litigation.py
│       │   │   ├── enforcement.py
│       │   │   ├── config.py
│       │   │   ├── file.py
│       │   │   └── system.py
│       │   └── progress.py          # 进度推送
│       └── requirements.txt
│
├── packages/
│   └── core/                        # 核心 OCR 逻辑
│       ├── src/
│       │   ├── pdf_ocr_ultra.py
│       │   ├── non_litigation_*.py
│       │   └── ...
│       └── pyproject.toml
│
├── config.yaml                      # 业务配置
├── samples/                         # 样本材料
└── README.md
```

## 9. 实现计划

### Phase 1: 基础架构（1-2 天）
1. 创建 Tauri 项目结构
2. 实现 Python JSON-RPC 服务框架
3. 实现 Rust-Python 通信层
4. 基础 UI 布局

### Phase 2: 核心功能（2-3 天）
1. 文件选择功能
2. OCR 单文件识别
3. 非诉审查流程
4. 进度显示

### Phase 3: 完整功能（2-3 天）
1. 强制执行提取
2. 配置管理
3. 结果展示
4. 日志查看

### Phase 4: 优化（1-2 天）
1. 错误处理
2. 性能优化
3. 打包发布
