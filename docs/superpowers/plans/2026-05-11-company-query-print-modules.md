# 企业信息查询 + 自动打印模块 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成企业信息查询和自动打印两个模块的前后端完整功能，同时将 ConfigPanel/PreviewPanel 重构为模块化组件分发层。

**Architecture:** 模块化组件拆分方案（方案 A）— 保留三区域布局，ConfigPanel/PreviewPanel 改为薄路由层按 moduleType 分发子组件。后端新增 `company_query.py` 和 `print_service.py` 模块，在 `server.py` 注册新 JSON-RPC 方法。

**Tech Stack:** React + TypeScript (前端), Python + pandas + requests (企业查询), Python + win32print (打印), JSON-RPC over stdin/stdout (通信)

---

## 文件结构

```
新增文件:
  apps/desktop/src/components/configs/NonLitigationConfig.tsx    — 非诉审查配置组件（从 ConfigPanel 抽出）
  apps/desktop/src/components/configs/EnforcementConfig.tsx      — 强制执行配置组件（从 ConfigPanel 抽出）
  apps/desktop/src/components/configs/CompanyQueryConfig.tsx     — 企业查询配置组件（新建）
  apps/desktop/src/components/configs/PrintConfig.tsx            — 自动打印配置组件（新建）
  apps/desktop/src/components/results/NonLitigationResult.tsx    — 非诉审查结果组件（从 PreviewPanel 抽出）
  apps/desktop/src/components/results/EnforcementResult.tsx      — 强制执行结果组件（从 PreviewPanel 抽出）
  apps/desktop/src/components/results/CompanyQueryResult.tsx     — 企业查询结果组件（新建）
  apps/desktop/src/components/results/PrintCardGrid.tsx          — 自动打印网格卡片组件（新建）
  apps/server/src/company_query.py                               — 企业信息查询后端模块（新建）
  apps/server/src/print_service.py                               — 自动打印后端模块（新建）

修改文件:
  apps/desktop/src/types.ts                                      — 新增类型定义
  apps/desktop/src/constants.ts                                  — 新增阶段名称映射
  apps/desktop/src/App.tsx                                       — 新增状态、RPC 调用分支
  apps/desktop/src/services/jsonrpc.ts                           — 新增 mock 响应
  apps/desktop/src/components/ConfigPanel.tsx                    — 改为路由分发层
  apps/desktop/src/components/PreviewPanel.tsx                   — 改为路由分发层
  apps/desktop/src/components/DetailView.tsx                     — 新增打印相关 props 透传
  apps/server/src/server.py                                      — 注册新 RPC 方法
  config.yaml                                                    — 新增 company_query / print 配置
```

---

### Task 1: 扩展 types.ts 和 constants.ts

**Files:**
- Modify: `apps/desktop/src/types.ts`
- Modify: `apps/desktop/src/constants.ts`

- [ ] **Step 1: 在 types.ts 中新增企业查询和打印相关类型**

在 `apps/desktop/src/types.ts` 文件末尾，`export type PreviewState` 行之前，添加以下类型：

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

export interface PrinterInfo {
  name: string;
  is_default: boolean;
}
```

在 `ProcessingResult` 接口中，在 `updated_excel_path?: string;` 之后添加：

```typescript
  companies?: CompanyQueryItem[];
  company_stats?: CompanyQueryStats;
  output_excel_path?: string;
  print_files?: PrintFileItem[];
  print_stats?: { total_files: number; printed: number; failed: number };
  printer_used?: string;
```

- [ ] **Step 2: 在 constants.ts 中新增阶段名称**

在 `apps/desktop/src/constants.ts` 的 `PHASE_NAMES` 中添加：

```typescript
export const PHASE_NAMES: Record<string, string> = {
  ocr_cache: "OCR 识别",
  export: "导出文件",
  validation: "验证",
  report: "生成报告",
  company_query: "企业查询",
  printing: "打印",
};
```

- [ ] **Step 3: 验证 lint 通过**

Run: `cd apps/desktop && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 4: Commit**

```bash
git add apps/desktop/src/types.ts apps/desktop/src/constants.ts
git commit -m "feat: add type definitions for company query and print modules"
```

---

### Task 2: 创建 configs/ 子目录 — NonLitigationConfig + EnforcementConfig + CompanyQueryConfig + PrintConfig

**Files:**
- Create: `apps/desktop/src/components/configs/NonLitigationConfig.tsx`
- Create: `apps/desktop/src/components/configs/EnforcementConfig.tsx`
- Create: `apps/desktop/src/components/configs/CompanyQueryConfig.tsx`
- Create: `apps/desktop/src/components/configs/PrintConfig.tsx`

- [ ] **Step 1: 创建 NonLitigationConfig.tsx**

`apps/desktop/src/components/configs/NonLitigationConfig.tsx`:

```tsx
interface Props {
  sampleRoot: string;
  excelFile: string;
  mockMode: boolean;
  forceOcr: boolean;
  running: boolean;
  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onMockModeChange: (v: boolean) => void;
  onForceOcrChange: (v: boolean) => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onRun: () => void;
}

export default function NonLitigationConfig({
  sampleRoot,
  excelFile,
  mockMode,
  forceOcr,
  running,
  onSampleRootChange,
  onExcelFileChange,
  onMockModeChange,
  onForceOcrChange,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onRun,
}: Props) {
  return (
    <div className="h-full flex flex-col gap-4 overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              ⚙️ 配置
            </h3>
            <button
              onClick={onPreset}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 px-2 py-1 rounded transition-colors cursor-pointer"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              测试示例
            </button>
          </div>
          <div className="p-4 space-y-3.5">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">🗂️ 样本材料文件夹</label>
              <input
                type="text"
                readOnly
                value={sampleRoot}
                onChange={(e) => onSampleRootChange(e.target.value)}
                placeholder="选择文件夹..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all"
              />
              <button
                onClick={onSelectFolder}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                📁 选择文件夹
              </button>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">📋 台账 Excel 文件</label>
              <input
                type="text"
                readOnly
                value={excelFile}
                onChange={(e) => onExcelFileChange(e.target.value)}
                placeholder="选择文件..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all"
              />
              <button
                onClick={onSelectExcel}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                📊 选择文件
              </button>
            </div>
            <div className="flex items-center gap-4 pt-1">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-500 hover:text-slate-700 transition-colors">
                <input type="checkbox" checked={mockMode} onChange={(e) => onMockModeChange(e.target.checked)} className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/30 w-3.5 h-3.5" />
                🎭 Mock 模式
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-500 hover:text-slate-700 transition-colors">
                <input type="checkbox" checked={forceOcr} onChange={(e) => onForceOcrChange(e.target.checked)} className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/30 w-3.5 h-3.5" />
                🔄 强制 OCR
              </label>
            </div>
          </div>
        </div>
      </div>
      <button
        onClick={onRun}
        disabled={running}
        className="shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 active:scale-[0.98] transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {running ? "处理中..." : "开始处理"}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: 创建 EnforcementConfig.tsx**

`apps/desktop/src/components/configs/EnforcementConfig.tsx`:

```tsx
interface Props {
  sampleRoot: string;
  excelFile: string;
  forceOcr: boolean;
  running: boolean;
  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onForceOcrChange: (v: boolean) => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onRun: () => void;
}

export default function EnforcementConfig({
  sampleRoot,
  excelFile,
  forceOcr,
  running,
  onSampleRootChange,
  onExcelFileChange,
  onForceOcrChange,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onRun,
}: Props) {
  return (
    <div className="h-full flex flex-col gap-4 overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              ⚙️ 配置
            </h3>
            <button
              onClick={onPreset}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-600 hover:text-amber-700 hover:bg-amber-50 px-2 py-1 rounded transition-colors cursor-pointer"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              测试示例
            </button>
          </div>
          <div className="p-4 space-y-3.5">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">🗂️ 裁定 PDF 文件夹</label>
              <input
                type="text"
                readOnly
                value={sampleRoot}
                onChange={(e) => onSampleRootChange(e.target.value)}
                placeholder="选择文件夹..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all"
              />
              <button
                onClick={onSelectFolder}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-amber-50 hover:border-amber-200 hover:text-amber-700 transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                📁 选择文件夹
              </button>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">📋 案件台账</label>
              <input
                type="text"
                readOnly
                value={excelFile}
                onChange={(e) => onExcelFileChange(e.target.value)}
                placeholder="选择文件..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all"
              />
              <button
                onClick={onSelectExcel}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-amber-50 hover:border-amber-200 hover:text-amber-700 transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                📊 选择文件
              </button>
            </div>
            <div className="flex items-center gap-4 pt-1">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-500 hover:text-slate-700 transition-colors">
                <input type="checkbox" checked={forceOcr} onChange={(e) => onForceOcrChange(e.target.checked)} className="rounded border-slate-300 text-amber-600 focus:ring-amber-500/30 w-3.5 h-3.5" />
                🔄 强制 OCR
              </label>
            </div>
          </div>
        </div>
      </div>
      <button
        onClick={onRun}
        disabled={running}
        className="shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white bg-amber-600 hover:bg-amber-700 active:scale-[0.98] transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {running ? "提取中..." : "开始提取"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: 创建 CompanyQueryConfig.tsx**

`apps/desktop/src/components/configs/CompanyQueryConfig.tsx`:

```tsx
interface Props {
  excelFile: string;
  running: boolean;
  onExcelFileChange: (v: string) => void;
  onPreset: () => void;
  onSelectExcel: () => void;
  onRun: () => void;
}

export default function CompanyQueryConfig({
  excelFile,
  running,
  onExcelFileChange,
  onPreset,
  onSelectExcel,
  onRun,
}: Props) {
  return (
    <div className="h-full flex flex-col gap-4 overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              ⚙️ 配置
            </h3>
            <button
              onClick={onPreset}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 px-2 py-1 rounded transition-colors cursor-pointer"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              测试示例
            </button>
          </div>
          <div className="p-4 space-y-3.5">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">📊 企业信息数据 Excel</label>
              <input
                type="text"
                readOnly
                value={excelFile}
                onChange={(e) => onExcelFileChange(e.target.value)}
                placeholder="选择包含被执行人列表的 Excel..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-400 transition-all"
              />
              <button
                onClick={onSelectExcel}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-emerald-50 hover:border-emerald-200 hover:text-emerald-700 transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                📊 选择 Excel 文件
              </button>
            </div>
            <p className="text-[10px] text-slate-400 leading-relaxed">
              Excel 需包含"被执行人"列，系统将逐个查询企业工商信息
            </p>
          </div>
        </div>
      </div>
      <button
        onClick={onRun}
        disabled={running}
        className="shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        {running ? "查询中..." : "开始查询"}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: 创建 PrintConfig.tsx**

`apps/desktop/src/components/configs/PrintConfig.tsx`:

```tsx
import type { PrinterInfo } from "../../types";

interface Props {
  sampleRoot: string;
  printerName: string;
  printCopies: number;
  printers: PrinterInfo[];
  running: boolean;
  onSampleRootChange: (v: string) => void;
  onPrinterNameChange: (v: string) => void;
  onPrintCopiesChange: (v: number) => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onRun: () => void;
}

export default function PrintConfig({
  sampleRoot,
  printerName,
  printCopies,
  printers,
  running,
  onSampleRootChange,
  onPrinterNameChange,
  onPrintCopiesChange,
  onPreset,
  onSelectFolder,
  onRun,
}: Props) {
  return (
    <div className="h-full flex flex-col gap-4 overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              ⚙️ 配置
            </h3>
            <button
              onClick={onPreset}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 hover:text-slate-700 hover:bg-slate-50 px-2 py-1 rounded transition-colors cursor-pointer"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              测试示例
            </button>
          </div>
          <div className="p-4 space-y-3.5">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">🗂️ 打印文件夹</label>
              <input
                type="text"
                readOnly
                value={sampleRoot}
                onChange={(e) => onSampleRootChange(e.target.value)}
                placeholder="选择包含 PDF 的文件夹..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
              />
              <button
                onClick={onSelectFolder}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-slate-100 hover:border-slate-300 hover:text-slate-700 transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                📁 选择文件夹
              </button>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">🖨️ 打印机</label>
              <select
                value={printerName}
                onChange={(e) => onPrinterNameChange(e.target.value)}
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all cursor-pointer"
              >
                {printers.length === 0 && (
                  <option value="">未检测到打印机</option>
                )}
                {printers.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}{p.is_default ? " (默认)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">🔢 打印份数</label>
              <input
                type="number"
                min={1}
                max={99}
                value={printCopies}
                onChange={(e) => onPrintCopiesChange(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
              />
            </div>
          </div>
        </div>
      </div>
      <button
        onClick={onRun}
        disabled={running}
        className="shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white bg-slate-700 hover:bg-slate-800 active:scale-[0.98] transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
        </svg>
        {running ? "打印中..." : "开始打印"}
      </button>
    </div>
  );
}
```

- [ ] **Step 5: 验证 lint 通过**

Run: `cd apps/desktop && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 6: Commit**

```bash
git add apps/desktop/src/components/configs/
git commit -m "feat: add module-specific config components (NonLitigation, Enforcement, CompanyQuery, Print)"
```

---

### Task 3: 创建 results/ 子目录 — NonLitigationResult + EnforcementResult + CompanyQueryResult + PrintCardGrid

**Files:**
- Create: `apps/desktop/src/components/results/NonLitigationResult.tsx`
- Create: `apps/desktop/src/components/results/EnforcementResult.tsx`
- Create: `apps/desktop/src/components/results/CompanyQueryResult.tsx`
- Create: `apps/desktop/src/components/results/PrintCardGrid.tsx`

- [ ] **Step 1: 创建 NonLitigationResult.tsx**

将 `PreviewPanel.tsx` 中的 `DetailItem` 和 `NonLitigationResult` 函数提取到 `apps/desktop/src/components/results/NonLitigationResult.tsx`。保持完全一致的代码逻辑和样式，只改变文件位置和导入。

```tsx
import type { ProcessingResult, ValidationDetail } from "../../types";

const STATUS_STYLE: Record<string, string> = {
  pass: "border-l-emerald-500 bg-emerald-50/50",
  warning: "border-l-amber-500 bg-amber-50/50",
  fail: "border-l-red-500 bg-red-50/50",
};

function DetailItem({ item }: { item: ValidationDetail }) {
  const borderStyle = STATUS_STYLE[item.status] || "border-l-slate-300";
  const parts: string[] = [];
  const d = item.details || {};
  if (d.total_pages) parts.push(`${d.total_pages}页`);
  if (d.detected_cases) parts.push(`${d.detected_cases}案件`);
  if (d.detected_notices?.length) parts.push(d.detected_notices.slice(0, 2).join(", "));
  if (item.timing?.total_duration) {
    const methodMap: Record<string, string> = { pdfplumber: "PDF提取", rapidocr: "OCR识别" };
    const method = item.timing.method || "";
    parts.push(`${methodMap[method] || method} ${item.timing.total_duration.toFixed(1)}s`);
  }

  return (
    <div className={`border-l-2 ${borderStyle} rounded px-3 py-2`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-slate-700 truncate">{item.file_name}</span>
        <span
          className={`text-[10px] font-semibold uppercase shrink-0 ${
            item.status === "pass" ? "text-emerald-600" : item.status === "warning" ? "text-amber-600" : "text-red-600"
          }`}
        >
          {item.status === "pass" ? "✓" : item.status === "warning" ? "⚠" : "✗"}{" "}
          {item.status === "pass" ? "通过" : item.status === "warning" ? "警告" : "失败"}
        </span>
      </div>
      <p className="text-[11px] text-slate-500 mt-0.5 truncate">{item.message}</p>
      {parts.length > 0 && <p className="text-[10px] text-slate-400 mt-0.5">{parts.join(" · ")}</p>}
    </div>
  );
}

export default function NonLitigationResult({ result }: { result: ProcessingResult }) {
  const v = result?.summary?.validation;
  const failedItems = result?.validation_failed || [];
  const warningItems = result?.validation_warnings || [];
  const allDetails = result?.validation_details || [];
  const passItems = allDetails.filter((d) => d.status === "pass");
  const showItems = [...failedItems, ...warningItems, ...passItems];

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="grid grid-cols-5 gap-2">
        <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
          <p className="text-lg font-bold text-slate-800">{v?.total ?? "-"}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">总文件</p>
        </div>
        <div className="rounded-lg bg-emerald-50 p-3 text-center border border-emerald-200">
          <p className="text-lg font-bold text-emerald-700">{v?.passed ?? "-"}</p>
          <p className="text-[10px] text-emerald-600 mt-0.5">✓ 通过</p>
        </div>
        <div className="rounded-lg bg-amber-50 p-3 text-center border border-amber-200">
          <p className="text-lg font-bold text-amber-700">{v?.warnings ?? "-"}</p>
          <p className="text-[10px] text-amber-600 mt-0.5">⚠ 警告</p>
        </div>
        <div className="rounded-lg bg-red-50 p-3 text-center border border-red-200">
          <p className="text-lg font-bold text-red-700">{v?.failed ?? "-"}</p>
          <p className="text-[10px] text-red-600 mt-0.5">✗ 失败</p>
        </div>
        <div className="rounded-lg bg-blue-50 p-3 text-center border border-blue-200">
          <p className="text-lg font-bold text-blue-700">{Math.round((v?.pass_rate || 0) * 100)}%</p>
          <p className="text-[10px] text-blue-600 mt-0.5">通过率</p>
        </div>
      </div>
      {result.summary?.quality && (
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-slate-50 px-3 py-2 flex items-center justify-between border border-slate-100">
            <span className="text-[11px] text-slate-500">📄 生成文件</span>
            <span className="text-sm font-bold text-slate-700">{result.summary.created_count ?? "-"}</span>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2 flex items-center justify-between border border-slate-100">
            <span className="text-[11px] text-slate-500">📊 页数匹配率</span>
            <span className="text-sm font-bold text-slate-700">{Math.round((result.summary.quality?.page_count_match_rate || 0) * 100)}%</span>
          </div>
        </div>
      )}
      {showItems.length > 0 && (
        <div>
          <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">验证明细</h4>
          <div className="space-y-1.5 flex-1 min-h-0 overflow-y-auto">
            {showItems.map((item, i) => (<DetailItem key={i} item={item} />))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 创建 EnforcementResult.tsx**

将 `PreviewPanel.tsx` 中的 `ExtractedItem` 和 `EnforcementResult` 提取到 `apps/desktop/src/components/results/EnforcementResult.tsx`，代码逻辑完全一致。

```tsx
import type { ProcessingResult, EnforcementExtracted } from "../../types";

function ExtractedItem({ item }: { item: EnforcementExtracted }) {
  const isWithdraw = item.is_withdraw;
  const parties = [...item.applicants.map((a) => a.name), ...item.respondents.map((r) => r.name)];

  return (
    <div className={`border-l-2 rounded px-3 py-2 ${isWithdraw ? "border-l-amber-500 bg-amber-50/50" : "border-l-blue-500 bg-blue-50/30"}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-slate-700 truncate">{item.court_case_number || "（未识别案号）"}</span>
        <span className={`text-[10px] font-semibold shrink-0 ${isWithdraw ? "text-amber-600" : "text-emerald-600"}`}>
          {isWithdraw ? "撤回执行" : item.ruling_result || "准予执行"}
        </span>
      </div>
      {item.notice_numbers.length > 0 && (
        <p className="text-[11px] text-slate-500 mt-0.5 truncate">责令号: {item.notice_numbers.slice(0, 3).join("、")}</p>
      )}
      {parties.length > 0 && (
        <p className="text-[10px] text-slate-400 mt-0.5 truncate">
          {parties.slice(0, 4).join(" · ")}{parties.length > 4 ? " ..." : ""}
        </p>
      )}
      {(item.judge || item.clerk || item.ruling_date) && (
        <p className="text-[10px] text-slate-400 mt-0.5 truncate">
          {[item.judge, item.clerk, item.ruling_date].filter(Boolean).join(" · ")}
        </p>
      )}
    </div>
  );
}

export default function EnforcementResult({ result }: { result: ProcessingResult }) {
  const stats = result.enforcement_stats;
  const extracted = result.extracted || [];
  const matchRate = stats && stats.total_excel_rows > 0 ? Math.round((stats.matched_rows / stats.total_excel_rows) * 100) : 0;

  return (
    <div className="flex flex-col gap-4 h-full">
      {stats && (
        <div className="grid grid-cols-5 gap-2">
          <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
            <p className="text-lg font-bold text-slate-800">{stats.total_pdfs}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">📄 PDF 数</p>
          </div>
          <div className="rounded-lg bg-blue-50 p-3 text-center border border-blue-200">
            <p className="text-lg font-bold text-blue-700">{stats.total_excel_rows}</p>
            <p className="text-[10px] text-blue-600 mt-0.5">📋 台账行</p>
          </div>
          <div className="rounded-lg bg-emerald-50 p-3 text-center border border-emerald-200">
            <p className="text-lg font-bold text-emerald-700">{stats.matched_rows}</p>
            <p className="text-[10px] text-emerald-600 mt-0.5">✓ 匹配</p>
          </div>
          <div className="rounded-lg bg-red-50 p-3 text-center border border-red-200">
            <p className="text-lg font-bold text-red-700">{stats.unmatched_rows}</p>
            <p className="text-[10px] text-red-600 mt-0.5">✗ 未匹配</p>
          </div>
          <div className="rounded-lg bg-amber-50 p-3 text-center border border-amber-200">
            <p className="text-lg font-bold text-amber-700">{stats.withdraw_count}</p>
            <p className="text-[10px] text-amber-600 mt-0.5">撤回执行</p>
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-slate-50 px-3 py-2 flex items-center justify-between border border-slate-100">
          <span className="text-[11px] text-slate-500">📄 提取文件</span>
          <span className="text-sm font-bold text-slate-700">{result.processed ?? extracted.length}</span>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2 flex items-center justify-between border border-slate-100">
          <span className="text-[11px] text-slate-500">📊 匹配率</span>
          <span className="text-sm font-bold text-slate-700">{matchRate}%</span>
        </div>
      </div>
      {extracted.length > 0 && (
        <div>
          <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">提取明细</h4>
          <div className="space-y-1.5 flex-1 min-h-0 overflow-y-auto">
            {extracted.map((item, i) => (<ExtractedItem key={i} item={item} />))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 创建 CompanyQueryResult.tsx**

`apps/desktop/src/components/results/CompanyQueryResult.tsx`:

```tsx
import type { ProcessingResult, CompanyQueryItem } from "../../types";

const STATUS_STYLES: Record<string, { badge: string; dot: string }> = {
  success: { badge: "text-emerald-700 bg-emerald-50 border-emerald-200", dot: "bg-emerald-500" },
  failed: { badge: "text-red-700 bg-red-50 border-red-200", dot: "bg-red-500" },
};

function CompanyRow({ item, index }: { item: CompanyQueryItem; index: number }) {
  const style = STATUS_STYLES[item.status] || STATUS_STYLES.failed;

  return (
    <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50/50 transition-colors">
      <td className="px-3 py-2 text-xs text-slate-400 text-center">{index + 1}</td>
      <td className="px-3 py-2 text-xs text-slate-700 max-w-[180px] truncate" title={item.original_name}>
        {item.original_name}
      </td>
      <td className="px-3 py-2 text-xs text-slate-700 max-w-[200px] truncate" title={item.current_name}>
        {item.current_name || "-"}
      </td>
      <td className="px-3 py-2 text-xs text-slate-700 truncate">{item.legal_person || "-"}</td>
      <td className="px-3 py-2 text-xs text-slate-700 truncate">{item.location || "-"}</td>
      <td className="px-3 py-2 text-xs text-slate-500 font-mono truncate">{item.credit_code || "-"}</td>
      <td className="px-3 py-2 text-center">
        <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded border ${style.badge}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          {item.status === "success" ? "成功" : "失败"}
        </span>
      </td>
    </tr>
  );
}

export default function CompanyQueryResult({ result }: { result: ProcessingResult }) {
  const stats = result.company_stats;
  const companies = result.companies || [];

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="grid grid-cols-4 gap-2">
        <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
          <p className="text-lg font-bold text-slate-800">{stats?.total ?? companies.length}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">企业总数</p>
        </div>
        <div className="rounded-lg bg-emerald-50 p-3 text-center border border-emerald-200">
          <p className="text-lg font-bold text-emerald-700">{stats?.success_count ?? "-"}</p>
          <p className="text-[10px] text-emerald-600 mt-0.5">✓ 查询成功</p>
        </div>
        <div className="rounded-lg bg-red-50 p-3 text-center border border-red-200">
          <p className="text-lg font-bold text-red-700">{stats?.fail_count ?? "-"}</p>
          <p className="text-[10px] text-red-600 mt-0.5">✗ 查询失败</p>
        </div>
        <div className="rounded-lg bg-blue-50 p-3 text-center border border-blue-200">
          <p className="text-lg font-bold text-blue-700">
            {stats && stats.total > 0 ? Math.round((stats.success_count / stats.total) * 100) : 0}%
          </p>
          <p className="text-[10px] text-blue-600 mt-0.5">成功率</p>
        </div>
      </div>

      {companies.length > 0 && (
        <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-slate-200">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-slate-50 z-10">
              <tr className="border-b border-slate-200">
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider text-center w-10">#</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">被执行人</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">现用名（含曾用名）</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">法代</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">所在地</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">信用代码</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider text-center w-16">状态</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((item, i) => (<CompanyRow key={i} item={item} index={i} />))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 创建 PrintCardGrid.tsx**

`apps/desktop/src/components/results/PrintCardGrid.tsx`:

```tsx
import type { ProcessingResult, PrintFileItem } from "../../types";

const CARD_STATUS: Record<string, { icon: string; label: string; border: string; bg: string; text: string }> = {
  pending: { icon: "⏳", label: "等待中", border: "border-slate-200", bg: "bg-white", text: "text-slate-500" },
  printing: { icon: "🖨", label: "打印中", border: "border-blue-300", bg: "bg-blue-50", text: "text-blue-600" },
  printed: { icon: "✅", label: "已完成", border: "border-emerald-200", bg: "bg-emerald-50/50", text: "text-emerald-600" },
  failed: { icon: "❌", label: "失败", border: "border-red-200", bg: "bg-red-50/50", text: "text-red-600" },
};

function PrintCard({ item }: { item: PrintFileItem }) {
  const s = CARD_STATUS[item.status] || CARD_STATUS.pending;

  return (
    <div className={`rounded-lg border ${s.border} ${s.bg} p-3 flex flex-col items-center gap-2 transition-colors`}>
      <svg className="w-8 h-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <p className="text-[11px] text-slate-700 truncate w-full text-center" title={item.filename}>
        {item.filename}
      </p>
      <span className={`text-[10px] font-medium ${s.text}`}>
        {s.icon} {s.label}
      </span>
      {item.status === "failed" && item.error && (
        <p className="text-[9px] text-red-400 truncate w-full text-center" title={item.error}>{item.error}</p>
      )}
    </div>
  );
}

export default function PrintCardGrid({ result }: { result: ProcessingResult }) {
  const stats = result.print_stats;
  const files = result.print_files || [];

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="grid grid-cols-4 gap-2">
        <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
          <p className="text-lg font-bold text-slate-800">{stats?.total_files ?? files.length}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">总文件</p>
        </div>
        <div className="rounded-lg bg-emerald-50 p-3 text-center border border-emerald-200">
          <p className="text-lg font-bold text-emerald-700">{stats?.printed ?? "-"}</p>
          <p className="text-[10px] text-emerald-600 mt-0.5">✅ 已打印</p>
        </div>
        <div className="rounded-lg bg-red-50 p-3 text-center border border-red-200">
          <p className="text-lg font-bold text-red-700">{stats?.failed ?? "-"}</p>
          <p className="text-[10px] text-red-600 mt-0.5">❌ 失败</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
          <p className="text-lg font-bold text-slate-700">{result.printer_used || "-"}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">🖨️ 打印机</p>
        </div>
      </div>

      {files.length > 0 && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="grid grid-cols-3 gap-2">
            {files.map((item, i) => (<PrintCard key={i} item={item} />))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: 验证 lint 通过**

Run: `cd apps/desktop && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 6: Commit**

```bash
git add apps/desktop/src/components/results/
git commit -m "feat: add module-specific result components (NonLitigation, Enforcement, CompanyQuery, Print)"
```

---

### Task 4: 重构 ConfigPanel.tsx 为路由分发层

**Files:**
- Modify: `apps/desktop/src/components/ConfigPanel.tsx`

- [ ] **Step 1: 替换 ConfigPanel.tsx 内容为路由分发层**

将 `apps/desktop/src/components/ConfigPanel.tsx` 的全部内容替换为：

```tsx
import type { ModuleType, PrinterInfo } from "../types";
import NonLitigationConfig from "./configs/NonLitigationConfig";
import EnforcementConfig from "./configs/EnforcementConfig";
import CompanyQueryConfig from "./configs/CompanyQueryConfig";
import PrintConfig from "./configs/PrintConfig";

interface Props {
  moduleType: ModuleType;
  sampleRoot: string;
  excelFile: string;
  mockMode: boolean;
  forceOcr: boolean;
  running: boolean;
  printerName: string;
  printCopies: number;
  printers: PrinterInfo[];
  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onMockModeChange: (v: boolean) => void;
  onForceOcrChange: (v: boolean) => void;
  onPrinterNameChange: (v: string) => void;
  onPrintCopiesChange: (v: number) => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onRun: () => void;
}

export default function ConfigPanel({
  moduleType,
  sampleRoot,
  excelFile,
  mockMode,
  forceOcr,
  running,
  printerName,
  printCopies,
  printers,
  onSampleRootChange,
  onExcelFileChange,
  onMockModeChange,
  onForceOcrChange,
  onPrinterNameChange,
  onPrintCopiesChange,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onRun,
}: Props) {
  switch (moduleType) {
    case "non-litigation":
      return (
        <NonLitigationConfig
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          mockMode={mockMode}
          forceOcr={forceOcr}
          running={running}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onMockModeChange={onMockModeChange}
          onForceOcrChange={onForceOcrChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onSelectExcel={onSelectExcel}
          onRun={onRun}
        />
      );
    case "enforcement":
      return (
        <EnforcementConfig
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          forceOcr={forceOcr}
          running={running}
          onSampleRootChange={onSampleRootChange}
          onExcelFileChange={onExcelFileChange}
          onForceOcrChange={onForceOcrChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onSelectExcel={onSelectExcel}
          onRun={onRun}
        />
      );
    case "company-query":
      return (
        <CompanyQueryConfig
          excelFile={excelFile}
          running={running}
          onExcelFileChange={onExcelFileChange}
          onPreset={onPreset}
          onSelectExcel={onSelectExcel}
          onRun={onRun}
        />
      );
    case "print":
      return (
        <PrintConfig
          sampleRoot={sampleRoot}
          printerName={printerName}
          printCopies={printCopies}
          printers={printers}
          running={running}
          onSampleRootChange={onSampleRootChange}
          onPrinterNameChange={onPrinterNameChange}
          onPrintCopiesChange={onPrintCopiesChange}
          onPreset={onPreset}
          onSelectFolder={onSelectFolder}
          onRun={onRun}
        />
      );
  }
}
```

- [ ] **Step 2: 验证 lint 通过**

Run: `cd apps/desktop && npx tsc --noEmit`
Expected: 类型错误——DetailView 传给 ConfigPanel 的 props 缺少新字段。这将在 Task 6 修复。

- [ ] **Step 3: Commit**

```bash
git add apps/desktop/src/components/ConfigPanel.tsx
git commit -m "refactor: ConfigPanel becomes routing layer, delegates to module-specific configs"
```

---

### Task 5: 重构 PreviewPanel.tsx 为路由分发层

**Files:**
- Modify: `apps/desktop/src/components/PreviewPanel.tsx`

- [ ] **Step 1: 替换 PreviewPanel.tsx 内容为路由分发层**

将 `apps/desktop/src/components/PreviewPanel.tsx` 的全部内容替换为：

```tsx
import type { ModuleType, PreviewState, ProcessingResult } from "../types";
import NonLitigationResult from "./results/NonLitigationResult";
import EnforcementResult from "./results/EnforcementResult";
import CompanyQueryResult from "./results/CompanyQueryResult";
import PrintCardGrid from "./results/PrintCardGrid";

interface Props {
  moduleType: ModuleType;
  previewState: PreviewState;
  phase: string;
  progressCurrent: number;
  progressTotal: number;
  progressMessage: string;
  result: ProcessingResult | null;
  onOpenReport: () => void;
  onOpenOutput: () => void;
  onClearResult: () => void;
}

const STATUS_BADGE: Record<PreviewState, { text: string; className: string }> = {
  empty: { text: "就绪", className: "text-[10px] font-medium text-slate-400 bg-slate-100 px-2 py-0.5 rounded" },
  progress: { text: "运行中", className: "text-[10px] font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded" },
  result: { text: "完成", className: "text-[10px] font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded" },
};

const RESULT_COMPONENTS: Record<ModuleType, React.ComponentType<{ result: ProcessingResult }>> = {
  "non-litigation": NonLitigationResult,
  "enforcement": EnforcementResult,
  "company-query": CompanyQueryResult,
  "print": PrintCardGrid,
};

const EMPTY_HINTS: Record<ModuleType, string> = {
  "non-litigation": "将显示处理进度与结果",
  "enforcement": "将显示提取结果与匹配统计",
  "company-query": "将显示企业信息查询结果",
  "print": "将显示打印文件列表与状态",
};

export default function PreviewPanel({
  moduleType,
  previewState,
  phase,
  progressCurrent,
  progressTotal,
  progressMessage,
  result,
  onOpenReport,
  onOpenOutput,
  onClearResult,
}: Props) {
  const badge = STATUS_BADGE[previewState];
  const percentage = progressTotal > 0 ? Math.round((progressCurrent / progressTotal) * 100) : 0;
  const ResultComponent = RESULT_COMPONENTS[moduleType];
  const emptyHint = EMPTY_HINTS[moduleType];

  return (
    <div className="flex-1 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">预览</h3>
        <span className={badge.className}>{badge.text}</span>
      </div>
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto p-4">
          {previewState === "empty" && (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-2">
                <svg className="w-10 h-10 text-slate-200 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-xs text-slate-400">配置参数后点击「开始处理」</p>
                <p className="text-[10px] text-slate-300">{emptyHint}</p>
              </div>
            </div>
          )}

          {previewState === "progress" && (
            <div className="flex-1 flex items-center">
              <div className="w-full space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">
                    阶段: <span className="font-semibold text-slate-800">{phase || "-"}</span>
                  </span>
                  <span className="text-xs font-medium text-slate-500">{progressCurrent} / {progressTotal}</span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div className="progress-bar h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full" style={{ width: `${percentage}%` }} />
                </div>
                <div className="flex items-center gap-2.5 p-3 bg-slate-50 rounded-lg border border-slate-100">
                  <svg className="w-4 h-4 text-blue-500 shrink-0 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <p className="text-xs font-medium text-slate-700 truncate">{progressMessage || "准备中..."}</p>
                </div>
              </div>
            </div>
          )}

          {previewState === "result" && result && <ResultComponent result={result} />}
        </div>

        {previewState === "result" && result && (
          <div className="shrink-0 px-4 py-3 border-t border-slate-100">
            <div className="flex gap-2 justify-center">
              <button onClick={onOpenReport} className="h-9 px-5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors cursor-pointer">
                📄 查看报告
              </button>
              <button onClick={onOpenOutput} className="h-9 px-5 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors cursor-pointer">
                📂 打开输出
              </button>
              <button onClick={onClearResult} className="h-9 px-5 text-sm font-medium text-slate-500 bg-white border border-slate-200 rounded-md hover:text-red-600 hover:border-red-300 hover:bg-red-50 transition-colors cursor-pointer">
                🗑 清空当前
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/desktop/src/components/PreviewPanel.tsx
git commit -m "refactor: PreviewPanel becomes routing layer, delegates to module-specific results"
```

---

### Task 6: 更新 DetailView + App.tsx — 透传新 props 和状态

**Files:**
- Modify: `apps/desktop/src/components/DetailView.tsx`
- Modify: `apps/desktop/src/App.tsx`
- Modify: `apps/desktop/src/services/jsonrpc.ts`

- [ ] **Step 1: 在 DetailView.tsx 中添加打印相关 props 透传**

在 DetailView 的 Props 接口中，在 `onForceOcrChange: (v: boolean) => void;` 之后添加：

```typescript
  printerName: string;
  printCopies: number;
  printers: PrinterInfo[];
  onPrinterNameChange: (v: string) => void;
  onPrintCopiesChange: (v: number) => void;
```

在 import 中添加 `PrinterInfo`：

```typescript
import type { ModuleType, PreviewState, ProcessingResult, LogEntry, PrinterInfo } from "../types";
```

在 DetailView 的解构参数中添加对应字段，并透传给 ConfigPanel：

```typescript
  const configPanelProps = {
    moduleType,
    sampleRoot,
    excelFile,
    mockMode,
    forceOcr,
    running,
    printerName,
    printCopies,
    printers,
    onSampleRootChange,
    onExcelFileChange,
    onMockModeChange,
    onForceOcrChange,
    onPrinterNameChange,
    onPrintCopiesChange,
    onPreset,
    onSelectFolder,
    onSelectExcel,
    onRun,
  };
```

ConfigPanel 调用处改为 `<ConfigPanel {...configPanelProps} />`。

- [ ] **Step 2: 在 App.tsx 中添加打印状态和新 RPC 调用分支**

在 App.tsx 的状态声明区（`const [forceOcr, setForceOcr]` 之后）添加：

```typescript
  const [printerName, setPrinterName] = useState("");
  const [printCopies, setPrintCopies] = useState(1);
  const [printers, setPrinters] = useState<PrinterInfo[]>([]);
```

在 import 中添加 `PrinterInfo`：

```typescript
import type { ModuleType, LogEntry, PreviewState, ProcessingResult, ProgressParams, SystemStatus, DependenciesCheck, PrinterInfo } from "./types";
```

在 `navigateToModule` 回调中，切换到 print 模块时加载打印机列表：

在 `addLog("info", \`切换到模块: ${config.title}\`);` 之前添加：

```typescript
      if (module === "print") {
        sendRequest("print.list_printers", {}).then((res: any) => {
          const list: PrinterInfo[] = res.printers || [];
          setPrinters(list);
          const defaultPrinter = list.find((p) => p.is_default);
          if (defaultPrinter) setPrinterName(defaultPrinter.name);
          else if (list.length > 0) setPrinterName(list[0].name);
        }).catch(() => addLog("warn", "获取打印机列表失败"));
      }
```

在 `startProcessing` 中替换 `print` 和 `company-query` 的模拟分支：

将：
```typescript
      } else if (currentModule === "print") {
        addLog("info", "[模拟] 自动打印处理...");
        res = {
          summary: {
            created_count: 5,
            quality: { page_count_match_rate: 1 },
            validation: { pass_rate: 1 },
          },
        };
      } else {
        // company-query or other modules
        addLog("info", `[模拟] ${MODULE_CONFIG[currentModule].title}处理...`);
        res = {
          summary: {
            created_count: 3,
            quality: { page_count_match_rate: 1 },
            validation: { pass_rate: 1 },
          },
        };
      }
```

替换为：

```typescript
      } else if (currentModule === "company-query") {
        if (!excelFile) {
          alert("请选择企业信息数据 Excel 文件");
          setRunning(false);
          setPreviewState("empty");
          return;
        }
        const rawResult = await sendRequest("company_query.process", {
          excel_path: excelFile,
          task_id: taskId,
        });
        res = {
          companies: rawResult.companies || [],
          company_stats: rawResult.total !== undefined
            ? { total: rawResult.total, success_count: rawResult.success_count, fail_count: rawResult.fail_count }
            : undefined,
          output_excel_path: rawResult.output_excel_path || "",
          summary: { result_root: rawResult.output_excel_path || undefined },
        };
      } else if (currentModule === "print") {
        if (!sampleRoot) {
          alert("请选择打印文件夹");
          setRunning(false);
          setPreviewState("empty");
          return;
        }
        const rawResult = await sendRequest("print.process", {
          folder_path: sampleRoot,
          printer_name: printerName,
          copies: printCopies,
          task_id: taskId,
        });
        res = {
          print_files: rawResult.files || [],
          print_stats: rawResult.total_files !== undefined
            ? { total_files: rawResult.total_files, printed: rawResult.printed, failed: rawResult.failed }
            : undefined,
          printer_used: rawResult.printer_used || "",
          summary: { result_root: sampleRoot },
        };
      }
```

同时更新 `startProcessing` 的依赖数组，加入 `printerName` 和 `printCopies`：

```typescript
  }, [currentModule, sampleRoot, excelFile, mockMode, forceOcr, printerName, printCopies, addLog]);
```

更新 DetailView 的 props 传递（在 JSX 中），在 `onForceOcrChange={setForceOcr}` 之后添加：

```typescript
          printerName={printerName}
          printCopies={printCopies}
          printers={printers}
          onPrinterNameChange={setPrinterName}
          onPrintCopiesChange={setPrintCopies}
```

- [ ] **Step 3: 在 jsonrpc.ts 中添加 mock 响应**

在 `mockResponse` 的 switch 中，在 `default` 之前添加：

```typescript
    case "company_query.process":
      return {
        total: 3,
        success_count: 2,
        fail_count: 1,
        companies: [
          { original_name: "爱玛客服务产业(中国)有限公司广东分公司", current_name: "爱玛客服务产业（中国）有限公司广东分公司", legal_person: "张三", location: "广东省广州市天河区", credit_code: "91440101MA5XXXXXXX", status: "success" },
          { original_name: "澳思美日用化工(广州)有限公司", current_name: "澳思美日用化工（广州）有限公司（曾用名：澳思美化工）", legal_person: "李四", location: "广东省广州市黄埔区", credit_code: "91440101MA5YYYYYYY", status: "success" },
          { original_name: "某不存在的公司", current_name: "", legal_person: "", location: "", credit_code: "", status: "failed", error: "未查询到企业数据" },
        ],
        output_excel_path: "/output/企业查询结果_mock.xlsx",
      };
    case "print.process":
      return {
        total_files: 5,
        printed: 4,
        failed: 1,
        printer_used: "Mock Printer",
        files: [
          { filename: "裁定书-张三.pdf", status: "printed", pages: 3 },
          { filename: "责令-李四.pdf", status: "printed", pages: 2 },
          { filename: "申请书-王五.pdf", status: "printed", pages: 1 },
          { filename: "授权书-赵六.pdf", status: "printed", pages: 1 },
          { filename: "所函-钱七.pdf", status: "failed", error: "模拟打印失败" },
        ],
      };
    case "print.list_printers":
      return {
        printers: [
          { name: "Mock Printer", is_default: true },
          { name: "Microsoft Print to PDF", is_default: false },
        ],
      };
```

- [ ] **Step 4: 验证 lint 通过**

Run: `cd apps/desktop && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 5: Commit**

```bash
git add apps/desktop/src/components/DetailView.tsx apps/desktop/src/App.tsx apps/desktop/src/services/jsonrpc.ts
git commit -m "feat: wire up company-query and print modules in App, DetailView, and mock RPC"
```

---

### Task 7: 后端 — 创建 company_query.py 模块

**Files:**
- Create: `apps/server/src/company_query.py`

- [ ] **Step 1: 创建 company_query.py**

`apps/server/src/company_query.py`:

```python
#!/usr/bin/env python3

import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

from config_loader import _load_config


class CompanyQueryError(Exception):
    def __init__(self, message: str, raw_response: dict = None):
        self.message = message
        self.raw_response = raw_response
        super().__init__(self.message)


def _get_coze_config() -> dict:
    raw = _load_config()
    cq = raw.get("company_query", {})
    return {
        "api_url": cq.get("coze_api_url", "https://api.coze.cn/v1/workflow/run"),
        "api_token": cq.get("coze_api_token", ""),
        "workflow_id": cq.get("coze_workflow_id", ""),
        "request_delay": cq.get("request_delay", 0.5),
        "excel_column_name": cq.get("excel_column_name", "被执行人"),
    }


def query_company_info(company_name: str, config: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {config['api_token']}",
        "Content-Type": "application/json",
    }
    payload = {
        "workflow_id": config["workflow_id"],
        "parameters": {"companyName": company_name},
        "is_async": False,
    }
    response = requests.post(
        config["api_url"],
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("code") == 0 and "data" in result and isinstance(result["data"], str):
        try:
            result["data"] = json.loads(result["data"])
        except json.JSONDecodeError:
            pass
    return result


def get_company_data(company_name: str, config: dict) -> dict:
    result = query_company_info(company_name, config)
    if result.get("code") != 0:
        raise CompanyQueryError(
            f"API 返回错误: {result.get('msg', '未知错误')}",
            raw_response=result,
        )
    data = result.get("data", {})
    company_data = data.get("data") if isinstance(data, dict) else None
    if not company_data:
        raise CompanyQueryError("未查询到企业数据", raw_response=result)
    return company_data


def format_current_name(company_data: dict) -> str:
    current_name = company_data.get("CompanyName", "")
    history_names = company_data.get("HistoryNames", "")
    if history_names and history_names != current_name:
        return f"{current_name}（曾用名：{history_names}）"
    return current_name


def extract_location(company_data: dict) -> str:
    province = company_data.get("Province", "")
    city = company_data.get("City", "")
    district = company_data.get("District", "")
    return "".join(p for p in [province, city, district] if p)


def process_single_company(company_name: str, config: dict) -> dict:
    try:
        company_data = get_company_data(company_name, config)
        return {
            "original_name": company_name,
            "current_name": format_current_name(company_data),
            "legal_person": company_data.get("LegalPerson", ""),
            "location": extract_location(company_data),
            "credit_code": company_data.get("CreditNo", ""),
            "status": "success",
        }
    except CompanyQueryError as e:
        return {
            "original_name": company_name,
            "current_name": "",
            "legal_person": "",
            "location": "",
            "credit_code": "",
            "status": "failed",
            "error": e.message,
        }
    except Exception as e:
        return {
            "original_name": company_name,
            "current_name": "",
            "legal_person": "",
            "location": "",
            "credit_code": "",
            "status": "failed",
            "error": str(e),
        }


def process_company_query(excel_path: Path, emitter=None) -> dict:
    config = _get_coze_config()
    column_name = config["excel_column_name"]

    df = pd.read_excel(excel_path, dtype=str)
    if column_name not in df.columns:
        raise ValueError(f"Excel 中缺少 '{column_name}' 列，可用列: {list(df.columns)}")

    company_names = df[column_name].dropna().tolist()
    total = len(company_names)
    results: List[dict] = []

    for i, name in enumerate(company_names):
        if emitter:
            emitter.progress("company_query", i + 1, total, f"查询: {name}")
        result = process_single_company(name, config)
        results.append(result)
        if config["request_delay"] > 0:
            time.sleep(config["request_delay"])

    success_count = sum(1 for r in results if r["status"] == "success")
    fail_count = total - success_count

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_excel_path = output_dir / f"企业查询结果_{timestamp}.xlsx"

    result_df = df.copy()
    result_df["现用名"] = [r.get("current_name", "") for r in results] + [""] * (len(result_df) - len(results))
    result_df["法代"] = [r.get("legal_person", "") for r in results] + [""] * (len(result_df) - len(results))
    result_df["所在地"] = [r.get("location", "") for r in results] + [""] * (len(result_df) - len(results))
    result_df["社会信用代码"] = [r.get("credit_code", "") for r in results] + [""] * (len(result_df) - len(results))

    result_df.to_excel(str(output_excel_path), index=False)

    return {
        "total": total,
        "success_count": success_count,
        "fail_count": fail_count,
        "companies": results,
        "output_excel_path": str(output_excel_path),
    }
```

- [ ] **Step 2: Commit**

```bash
git add apps/server/src/company_query.py
git commit -m "feat: add company_query.py backend module"
```

---

### Task 8: 后端 — 创建 print_service.py 模块

**Files:**
- Create: `apps/server/src/print_service.py`

- [ ] **Step 1: 创建 print_service.py**

`apps/server/src/print_service.py`:

```python
#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path
from typing import Dict, List


def list_printers() -> List[dict]:
    try:
        import win32print
    except ImportError:
        return [{"name": "默认打印机", "is_default": True}]

    printers = []
    default_printer = None
    try:
        default_printer = win32print.GetDefaultPrinter()
    except Exception:
        pass

    try:
        for printer_info in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
            name = printer_info[2]
            printers.append({
                "name": name,
                "is_default": name == default_printer,
            })
    except Exception:
        pass

    if not printers and default_printer:
        printers.append({"name": default_printer, "is_default": True})

    return printers


def _print_pdf(pdf_path: Path, printer_name: str, copies: int = 1) -> dict:
    try:
        import win32print
        import win32api

        win32api.ShellExecute(
            0,
            "print",
            str(pdf_path),
            f'/d:"{printer_name}"',
            ".",
            0,
        )
        return {"filename": pdf_path.name, "status": "printed"}
    except ImportError:
        pass
    except Exception as e:
        return {"filename": pdf_path.name, "status": "failed", "error": str(e)}

    try:
        cmd = [
            sys.executable, "-m", "win32api_shell",
            "print", str(pdf_path),
            "--printer", printer_name,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return {"filename": pdf_path.name, "status": "printed"}
        else:
            return {"filename": pdf_path.name, "status": "failed", "error": result.stderr.strip() or "打印命令失败"}
    except Exception as e:
        return {"filename": pdf_path.name, "status": "failed", "error": str(e)}


def process_print(folder_path: Path, printer_name: str, copies: int = 1, emitter=None) -> dict:
    config_exts = {".pdf"}

    all_files = [p for p in folder_path.rglob("*") if p.is_file() and p.suffix.lower() in config_exts]
    all_files.sort(key=lambda p: p.name)

    total = len(all_files)
    results: List[dict] = []
    printed_count = 0
    failed_count = 0

    for i, pdf_path in enumerate(all_files):
        if emitter:
            emitter.progress("printing", i + 1, total, f"打印: {pdf_path.name}")

        result = _print_pdf(pdf_path, printer_name, copies)
        results.append(result)

        if result["status"] == "printed":
            printed_count += 1
        else:
            failed_count += 1

    return {
        "total_files": total,
        "printed": printed_count,
        "failed": failed_count,
        "printer_used": printer_name,
        "files": results,
    }
```

- [ ] **Step 2: Commit**

```bash
git add apps/server/src/print_service.py
git commit -m "feat: add print_service.py backend module"
```

---

### Task 9: 后端 — 在 server.py 中注册新 RPC 方法

**Files:**
- Modify: `apps/server/src/server.py`
- Modify: `config.yaml`

- [ ] **Step 1: 在 server.py 的 _register_methods 中注册新方法**

在 `self.methods['enforcement.fill_excel'] = self._enforcement_fill_excel` 之后添加：

```python
        # 企业信息查询模块
        self.methods['company_query.process'] = self._company_query_process

        # 自动打印模块
        self.methods['print.process'] = self._print_process
        self.methods['print.list_printers'] = self._print_list_printers
```

- [ ] **Step 2: 在 server.py 中添加 PRESET 路径映射**

在 `PRESET_EXCEL_PATHS` 字典中已有 `"enforcement-print"` 之后，确认 `"company-query"` 的路径映射存在。当前不存在，需添加：

在 `PRESET_SAMPLE_PATHS` 字典末尾（`"enforcement-print"` 条目之后）添加：

```python
    "company-query": ["sample-data/company-query", "样本材料/企业信息查询"],
```

在 `PRESET_EXCEL_PATHS` 字典末尾添加：

```python
    "company-query": ["sample-data/company-query/companies.xlsx", "样本材料/企业信息查询/5月案件-被执行人信息（新）(1).xlsx"],
```

- [ ] **Step 3: 在 server.py 中实现 RPC 处理方法**

在 `server.py` 的 `_enforcement_fill_excel` 方法之后，`_config_get` 方法之前（即 `# ============ 配置模块 ============` 注释之前）添加：

```python
    # ============ 企业信息查询模块 ============

    def _company_query_process(self, params: Dict, id: Any) -> Dict:
        """企业信息查询"""
        preset_id = params.get('preset_id')
        excel_path = params.get('excel_path')
        task_id = params.get('task_id', f"cq-{id}")
        emitter = ProgressEmitter(task_id)

        try:
            from company_query import process_company_query
            if preset_id and preset_id in PRESET_EXCEL_PATHS:
                excel_path = _resolve_preset_path(PRESET_EXCEL_PATHS[preset_id])
            else:
                excel_path = Path(excel_path) if excel_path else Path('.')

            if not excel_path.exists():
                raise FileNotFoundError(f"Excel 文件不存在: {excel_path}")

            emitter.log("info", f"开始企业信息查询: {excel_path.name}")
            result = process_company_query(excel_path, emitter=emitter)
            emitter.log("info", f"查询完成: 成功 {result['success_count']}/{result['total']}")
            return result
        except Exception as e:
            raise Exception(f"企业查询失败: {str(e)}")

    # ============ 自动打印模块 ============

    def _print_process(self, params: Dict, id: Any) -> Dict:
        """自动打印"""
        folder_path = params.get('folder_path')
        printer_name = params.get('printer_name', '')
        copies = params.get('copies', 1)
        task_id = params.get('task_id', f"print-{id}")
        emitter = ProgressEmitter(task_id)

        try:
            from print_service import process_print
            folder = Path(folder_path) if folder_path else Path('.')
            if not folder.exists():
                raise FileNotFoundError(f"文件夹不存在: {folder}")

            if not printer_name:
                from print_service import list_printers
                printers = list_printers()
                default = next((p for p in printers if p["is_default"]), None)
                if default:
                    printer_name = default["name"]
                elif printers:
                    printer_name = printers[0]["name"]
                else:
                    raise Exception("未找到可用打印机")

            emitter.log("info", f"开始打印: {folder} → {printer_name}")
            result = process_print(folder, printer_name, copies, emitter=emitter)
            emitter.log("info", f"打印完成: {result['printed']}/{result['total_files']}")
            return result
        except Exception as e:
            raise Exception(f"打印失败: {str(e)}")

    def _print_list_printers(self, params: Dict, id: Any) -> Dict:
        """获取打印机列表"""
        try:
            from print_service import list_printers
            return {"printers": list_printers()}
        except Exception as e:
            raise Exception(f"获取打印机列表失败: {str(e)}")
```

- [ ] **Step 4: 在 config.yaml 中添加 company_query 和 print 配置**

在 `config.yaml` 末尾添加：

```yaml
# ============================================
# 企业信息查询配置
# ============================================
company_query:
  coze_api_url: "https://api.coze.cn/v1/workflow/run"
  coze_api_token: "sat_xo6jKTKmaerCALRXHE7ZrRowHOvHARoplcU0HiYQtARY3QMr4C1MXqUO3FAJFuHA"
  coze_workflow_id: "7637504045536428084"
  request_delay: 0.5
  excel_column_name: "被执行人"

# ============================================
# 自动打印配置
# ============================================
print:
  default_copies: 1
  file_extensions:
    - ".pdf"
```

- [ ] **Step 5: Commit**

```bash
git add apps/server/src/server.py config.yaml
git commit -m "feat: register company_query and print RPC methods in server, add config.yaml sections"
```

---

### Task 10: 前端 lint 检查 + 全流程验证

**Files:**
- No new files

- [ ] **Step 1: 运行前端 TypeScript 检查**

Run: `cd apps/desktop && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 2: 运行前端 lint**

Run: `cd apps/desktop && npm run lint`
Expected: 无错误

- [ ] **Step 3: 验证后端模块可导入**

Run (在项目根目录，虚拟环境激活):
```bash
cd /path/to/project && python -c "import sys; sys.path.insert(0, 'apps/server/src'); from company_query import process_company_query; print('company_query OK')"
```

Run:
```bash
cd /path/to/project && python -c "import sys; sys.path.insert(0, 'apps/server/src'); from print_service import list_printers, process_print; print('print_service OK')"
```

Expected: 两个模块均可正常导入

- [ ] **Step 4: Commit (如有 lint 修复)**

```bash
git add -A
git commit -m "fix: lint fixes after module integration"
```
