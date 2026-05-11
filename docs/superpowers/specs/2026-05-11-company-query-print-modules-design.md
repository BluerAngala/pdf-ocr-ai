# 企业信息查询 + 自动打印模块设计

日期: 2026-05-11

## 背景

当前前端所有模块（非诉审查、强制执行、企业查询、自动打印）共用一个 DetailView，ConfigPanel 和 PreviewPanel 通过 `moduleType` 条件分支做差异化。企业查询和自动打印模块目前仅有 mock 占位实现，需要完成完整的前后端功能。

## 设计决策

**架构方案**: 方案 A — 模块化组件拆分

保留三区域布局（ConfigPanel + PreviewPanel + LogsPanel），将 ConfigPanel 和 PreviewPanel 改为薄路由层，按 moduleType 分发到独立子组件。

选择理由：
- 保留三区域设计约束，改动最小
- 各模块差异集中在配置项和结果展示，路由层分发最直接
- 避免方案 B（模块路由化）带来的大量重复代码

## 1. 企业信息查询模块

### 1.1 前端 — CompanyQueryConfig

位置: `src/components/configs/CompanyQueryConfig.tsx`

配置项:
- Excel 文件选择器（选择企业信息数据 Excel）
- "测试示例"按钮（加载预设路径: `样本材料/企业信息查询/5月案件-被执行人信息（新）(1).xlsx`）
- "开始处理"按钮

输入 Excel 结构（已知）:
| 序号 | 被执行人 | 现用名 | 法代 | 所在地 | 社会信用代码 |
|------|----------|--------|------|--------|--------------|
| 1    | 爱玛客服务产业(中国)... | (空) | (空) | (空) | (空) |

共 353 行，"被执行人"列为查询输入，其余列为空待填充。

### 1.2 前端 — CompanyQueryResult

位置: `src/components/results/CompanyQueryResult.tsx`

布局:
- 顶部统计栏（4 格）: 总企业数 | 查询成功 | 查询失败 | 查询中
- 主区域: 结果表格
  - 列: 序号 | 被执行人 | 现用名（含曾用名） | 法代 | 所在地 | 社会信用代码 | 状态
  - 状态标签: ✅ 成功(绿) / ❌ 失败(红) / ⏳ 查询中(蓝)
- 底部操作栏: 📂 打开输出 | 📊 导出 Excel

### 1.3 后端 — company_query.process

JSON-RPC 方法: `company_query.process`

参数:
```json
{
  "excel_path": "/path/to/input.xlsx",
  "task_id": "company-query-1234567890"
}
```

流程:
1. 读取 Excel，提取"被执行人"列
2. 逐个调用 Coze API 查询企业信息
3. 每个 API 调用后通过 `notify.progress` 推送进度
4. 查询完成后将结果导出为新 Excel
5. 返回结果

返回值:
```json
{
  "total": 353,
  "success_count": 340,
  "fail_count": 13,
  "companies": [
    {
      "original_name": "爱玛客服务产业(中国)有限公司广东分公司",
      "current_name": "爱玛客服务产业（中国）有限公司广东分公司（曾用名：xxx）",
      "legal_person": "张三",
      "location": "广东省广州市天河区",
      "credit_code": "91440101XXXXXXXXXX",
      "status": "success"
    },
    {
      "original_name": "某不存在的公司",
      "current_name": "",
      "legal_person": "",
      "location": "",
      "credit_code": "",
      "status": "failed",
      "error": "未查询到企业数据"
    }
  ],
  "output_excel_path": "/output/企业查询结果_20260511.xlsx"
}
```

### 1.4 后端模块 — company_query.py

位置: `apps/server/src/company_query.py`

核心函数:
```python
def process_company_query(excel_path: Path, emitter: ProgressEmitter) -> dict:
    """
    1. 读取 Excel，提取"被执行人"列
    2. 逐个调用 Coze API 查询
    3. 通过 emitter.progress() 推送进度
    4. 返回结果字典 + 导出 Excel 路径
    """
```

从现有 `fill_company_info_from_coze.py` 提取:
- `query_company_info()` — Coze API 调用
- `get_company_data()` — 企业数据提取
- `format_current_name()` — 现用名格式化（含曾用名）
- `extract_location()` — 省市区拼接

Coze API 配置移入 `config.yaml`：
```yaml
company_query:
  coze_api_url: "https://api.coze.cn/v1/workflow/run"
  coze_api_token: "sat_xo..."
  coze_workflow_id: "763750..."
  request_delay: 0.5
  excel_column_name: "被执行人"
```

## 2. 自动打印模块

### 2.1 前端 — PrintConfig

位置: `src/components/configs/PrintConfig.tsx`

配置项:
- 打印文件夹选择器（用户指定包含 PDF 的文件夹）
- 打印机选择（下拉列表，从后端 `print.list_printers` 获取）
- 打印份数（数字输入，默认 1）
- "测试示例"按钮（加载预设路径: `样本材料/强制组-自动化/自动打印`）
- "开始打印"按钮

### 2.2 前端 — PrintCardGrid

位置: `src/components/results/PrintCardGrid.tsx`

布局:
- 顶部统计栏（4 格）: 总文件数 | 已打印 | 打印失败 | 等待中
- 主区域: 网格卡片视图
  - 每个卡片: PDF 图标（Phase 1 通用图标，Phase 2 可加缩略图） + 文件名(截断) + 状态标签
  - 状态标签: ⏳ 等待中 / 🖨 打印中(蓝) / ✅ 已完成(绿) / ❌ 失败(红)
- 底部操作栏: 📂 打开文件夹 | 🔄 重新打印失败文件

缩略图策略:
- Phase 1: 通用 PDF 图标 + 文件名 + 状态（先跑通流程）
- Phase 2: 后续可选引入 pdf.js 首页渲染缩略图

### 2.3 后端 — print.process

JSON-RPC 方法: `print.process`

参数:
```json
{
  "folder_path": "/path/to/pdf/folder",
  "printer_name": "HP LaserJet Pro",
  "copies": 1,
  "task_id": "print-1234567890"
}
```

流程:
1. 递归扫描文件夹内所有 PDF 文件
2. 逐个发送到指定打印机
3. 通过 `notify.progress` 推送进度
4. 返回结果

返回值:
```json
{
  "total_files": 12,
  "printed": 10,
  "failed": 2,
  "printer_used": "HP LaserJet Pro",
  "files": [
    {
      "filename": "裁定书-张三.pdf",
      "status": "printed",
      "pages": 3
    },
    {
      "filename": "责令-李四.pdf",
      "status": "failed",
      "error": "打印机离线"
    }
  ]
}
```

### 2.4 后端辅助方法 — print.list_printers

参数: `{}`

返回值:
```json
{
  "printers": [
    { "name": "HP LaserJet Pro", "is_default": true },
    { "name": "Microsoft Print to PDF", "is_default": false }
  ]
}
```

### 2.5 后端模块 — print_service.py

位置: `apps/server/src/print_service.py`

核心函数:
```python
def list_printers() -> list[dict]:
    """返回 Windows 系统可用打印机列表"""

def process_print(folder_path: Path, printer_name: str, copies: int, emitter: ProgressEmitter) -> dict:
    """
    1. 递归扫描文件夹内所有 PDF
    2. 逐个发送到指定打印机
    3. 通过 emitter.progress() 推送进度
    4. 返回结果字典
    """
```

打印实现: 使用 `win32print` 模块（pywin32），可指定打印机名称。

config.yaml 新增:
```yaml
print:
  default_copies: 1
  file_extensions: [".pdf"]
```

## 3. 前端组件重构

### 3.1 文件结构

```
src/components/
  ├── ConfigPanel.tsx              ← 改成路由分发层
  ├── PreviewPanel.tsx             ← 改成路由分发层
  ├── configs/
  │   ├── NonLitigationConfig.tsx  ← 从 ConfigPanel 抽出
  │   ├── EnforcementConfig.tsx    ← 从 ConfigPanel 抽出
  │   ├── CompanyQueryConfig.tsx   ← 新建
  │   └── PrintConfig.tsx          ← 新建
  ├── results/
  │   ├── NonLitigationResult.tsx  ← 从 PreviewPanel 抽出
  │   ├── EnforcementResult.tsx    ← 从 PreviewPanel 抽出
  │   ├── CompanyQueryResult.tsx   ← 新建
  │   └── PrintCardGrid.tsx        ← 新建
  ├── HomeView.tsx                 ← 不变
  ├── DetailView.tsx               ← 不变
  ├── LogsPanel.tsx                ← 不变
  ├── StatusBar.tsx                ← 不变
  └── SystemStatusModal.tsx        ← 不变
```

### 3.2 ConfigPanel 路由化

```tsx
export default function ConfigPanel({ moduleType, ...props }) {
  switch (moduleType) {
    case "non-litigation": return <NonLitigationConfig {...props} />;
    case "enforcement": return <EnforcementConfig {...props} />;
    case "company-query": return <CompanyQueryConfig {...props} />;
    case "print": return <PrintConfig {...props} />;
  }
}
```

### 3.3 PreviewPanel 路由化

```tsx
export default function PreviewPanel({ moduleType, ...props }) {
  const ResultComponent = {
    "non-litigation": NonLitigationResult,
    "enforcement": EnforcementResult,
    "company-query": CompanyQueryResult,
    "print": PrintCardGrid,
  }[moduleType];

  return (
    <div className="...">
      {/* 顶部状态栏 + 进度条 — 保持不变 */}
      {previewState === "result" && result && <ResultComponent result={result} />}
      {/* 底部操作栏 — 保持不变 */}
    </div>
  );
}
```

### 3.4 types.ts 扩展

```typescript
export interface CompanyQueryItem {
  original_name: string;
  current_name: string;
  legal_person: string;
  location: string;
  credit_code: string;
  status: "success" | "failed";
  error?: string;
}

export interface CompanyQueryStats {
  total: number;
  success_count: number;
  fail_count: number;
}

export interface PrintFileItem {
  filename: string;
  status: "printed" | "failed" | "pending" | "printing";
  pages?: number;
  error?: string;
}

// ProcessingResult 新增字段:
// companies?: CompanyQueryItem[];
// company_stats?: CompanyQueryStats;
// output_excel_path?: string;
// print_files?: PrintFileItem[];
// print_stats?: { total_files: number; printed: number; failed: number };
// printer_used?: string;

// 新增打印机类型
export interface PrinterInfo {
  name: string;
  is_default: boolean;
}
```

### 3.5 App.tsx 改动

1. 新增打印模块状态: `printerName`, `printCopies`
2. 新增 `printers` 状态（从 `print.list_printers` 获取）
3. `startProcessing` 新增两个分支:
   - `company-query` → `sendRequest("company_query.process", { excel_path, task_id })`
   - `print` → `sendRequest("print.process", { folder_path, printer_name, copies, task_id })`

### 3.6 Mock 响应扩展

`jsonrpc.ts` 的 `mockResponse` 新增:
- `company_query.process` → 返回模拟企业数据
- `print.process` → 返回模拟打印结果
- `print.list_printers` → 返回模拟打印机列表

## 4. 后端 server.py 改动

新增方法注册:
```python
self.methods['company_query.process'] = self._company_query_process
self.methods['print.process'] = self._print_process
self.methods['print.list_printers'] = self._print_list_printers
```

新增 PRESET 路径映射:
```python
PRESET_SAMPLE_PATHS["company-query"] = ["sample-data/company-query", "样本材料/企业信息查询"]
PRESET_EXCEL_PATHS["company-query"] = ["sample-data/company-query/companies.xlsx", "样本材料/企业信息查询/5月案件-被执行人信息（新）(1).xlsx"]
PRESET_SAMPLE_PATHS["enforcement-print"] = ["sample-data/enforcement/print", "样本材料/强制组-自动化/自动打印"]
```

## 5. 不涉及的范围

- 非诉审查模块: 不改动
- 强制执行模块: 不改动
- 打印缩略图 Phase 2 (pdf.js): 后续迭代
- 企业查询结果回填原 Excel: 不做（仅展示+另存）
