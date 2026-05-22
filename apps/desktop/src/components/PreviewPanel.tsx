import { useMemo } from "react";
import type {
  ModuleType,
  PreviewState,
  ProcessingResult,
  CompanyQueryItem,
  PrintTaskStatus,
} from "../types";
import NonLitigationResult from "./results/NonLitigationResult";
import EnforcementResult from "./results/EnforcementResult";
import CompanyQueryResult from "./results/CompanyQueryResult";
import PrintProgress from "./results/PrintCardGrid";

interface Props {
  moduleType: ModuleType;
  previewState: PreviewState;
  phase: string;
  progressCurrent: number;
  progressTotal: number;
  progressFileCurrent: number;
  progressFileTotal: number;
  progressMessage: string;
  result: ProcessingResult | null;
  liveCompanies: CompanyQueryItem[];
  printTaskStatus: PrintTaskStatus | null;
  onOpenOutput: () => void;
  onClearResult: () => void;
  onCancelPrint: () => void;
  selectedOrders: Set<number>;
  onSelectedOrdersChange: (orders: Set<number>) => void;
  onPrintOrders: (orders: number[]) => void;
  printedOrders: Set<number>;
  printingOrders: Set<number>;
}

const STATUS_BADGE: Record<PreviewState, { text: string; className: string }> = {
  empty: {
    text: "就绪",
    className:
      "text-[10px] font-semibold text-slate-600 bg-slate-200 border border-slate-300 px-2.5 py-1 rounded-md shadow-sm",
  },
  progress: {
    text: "运行中",
    className:
      "text-[10px] font-semibold text-emerald-800 bg-emerald-100 border border-emerald-300 px-2.5 py-1 rounded-md shadow-sm",
  },
  cancelling: {
    text: "正在取消...",
    className:
      "text-[10px] font-semibold text-amber-800 bg-amber-100 border border-amber-300 px-2.5 py-1 rounded-md shadow-sm",
  },
  paused: {
    text: "已暂停",
    className:
      "text-[10px] font-semibold text-amber-900 bg-amber-100 border border-amber-300 px-2.5 py-1 rounded-md shadow-sm",
  },
  result: {
    text: "完成",
    className:
      "text-[10px] font-semibold text-blue-800 bg-blue-100 border border-blue-300 px-2.5 py-1 rounded-md shadow-sm",
  },
};

const RESULT_COMPONENTS: Record<
  Exclude<ModuleType, "print">,
  React.ComponentType<{ result: ProcessingResult }>
> = {
  "non-litigation": NonLitigationResult,
  enforcement: EnforcementResult,
  "company-query": CompanyQueryResult,
};

const EMPTY_HINTS: Record<ModuleType, string> = {
  "non-litigation": "将显示处理进度与结果",
  enforcement: "将显示提取结果与匹配统计",
  "company-query": "将显示企业信息查询结果",
  print: "将显示打印文件列表与状态",
};

export default function PreviewPanel({
  moduleType,
  previewState,
  phase,
  progressCurrent,
  progressTotal,
  progressFileCurrent,
  progressFileTotal,
  progressMessage,
  result,
  liveCompanies,
  printTaskStatus,
  onOpenOutput,
  onClearResult,
  onCancelPrint,
  selectedOrders,
  onSelectedOrdersChange,
  onPrintOrders,
  printedOrders,
  printingOrders,
}: Props) {
  const badge = STATUS_BADGE[previewState];
  // 是否有文件级进度
  const hasFileProgress = progressFileTotal > 0;
  // 计算整体进度百分比
  // 每个阶段占 total 分之一，阶段内根据文件进度细分
  const percentage = useMemo(() => {
    if (progressTotal <= 0) return 0;
    // 已完成阶段的进度
    const completedPhaseProgress = ((progressCurrent - 1) / progressTotal) * 100;
    // 当前阶段的进度（如果有文件进度）
    const currentPhaseProgress =
      hasFileProgress && progressFileTotal > 0
        ? (progressFileCurrent / progressFileTotal) * (100 / progressTotal)
        : 100 / progressTotal;
    return Math.round(completedPhaseProgress + currentPhaseProgress);
  }, [progressCurrent, progressTotal, progressFileCurrent, progressFileTotal, hasFileProgress]);
  const ResultComponent = moduleType !== "print" ? RESULT_COMPONENTS[moduleType] : null;
  const emptyHint = EMPTY_HINTS[moduleType];

  const showLiveTable =
    moduleType === "company-query" && previewState === "progress" && liveCompanies.length > 0;

  const liveStats = showLiveTable
    ? {
        total: progressTotal,
        success_count: liveCompanies.filter((c) => c.status === "success").length,
        warning_count: liveCompanies.filter((c) => c.status === "warning").length,
        fail_count: liveCompanies.filter((c) => c.status === "failed").length,
      }
    : null;

  return (
    <div className="flex-1 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">预览</h3>
        <div className="flex items-center gap-2">
          {previewState === "result" && result && moduleType !== "print" && (
            <button
              onClick={onOpenOutput}
              className="h-7 px-3 text-[11px] font-semibold text-white bg-blue-600 border border-blue-700 rounded-md shadow-sm hover:bg-blue-700 active:bg-blue-800 transition-colors cursor-pointer"
            >
              输出结果
            </button>
          )}
          {previewState === "result" && result && (
            <button
              onClick={onClearResult}
              className="h-7 px-3 text-[11px] font-semibold text-slate-700 bg-slate-200 border border-slate-300 rounded-md shadow-sm hover:bg-slate-300 hover:text-red-700 hover:border-red-300 active:bg-slate-300 transition-colors cursor-pointer"
            >
              清空
            </button>
          )}
          <span className={badge.className}>{badge.text}</span>
        </div>
      </div>
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto p-4 h-full">
          {previewState === "empty" && (
            <div className="h-full flex items-center justify-center">
              <div className="text-center space-y-2">
                <svg
                  className="w-10 h-10 text-slate-200 mx-auto"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <p className="text-xs text-slate-400">配置参数后点击「开始处理」</p>
                <p className="text-[10px] text-slate-300">{emptyHint}</p>
              </div>
            </div>
          )}

          {(previewState === "progress" ||
            previewState === "cancelling" ||
            previewState === "paused") && (
            <div className="flex flex-col gap-3">
              {previewState === "cancelling" && (
                <div className="flex items-center gap-2 p-2 bg-amber-50 border border-amber-200 rounded-lg">
                  <svg
                    className="w-4 h-4 text-amber-500 shrink-0 animate-spin"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                  <span className="text-xs font-medium text-amber-700">
                    正在停止任务，等待当前操作完成...
                  </span>
                </div>
              )}
              {previewState === "paused" && (
                <div className="flex items-center gap-2 p-2 bg-amber-50 border border-amber-200 rounded-lg">
                  <span className="text-xs font-medium text-amber-800">
                    任务已暂停，已完成部分已写入缓存。点击「继续任务」从断点接着处理。
                  </span>
                </div>
              )}
              <div className="space-y-2">
                {/* 第一行：阶段名 + 文件进度 */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-600 font-medium">{phase || "-"}中...</span>
                  {hasFileProgress && (
                    <span className="text-xs font-medium text-slate-500">
                      文件 {progressFileCurrent}/{progressFileTotal}
                    </span>
                  )}
                </div>
                {/* 进度条 + 百分比 */}
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="progress-bar h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-blue-600 w-12 text-right">
                    {percentage}%
                  </span>
                </div>
                {/* 当前操作 */}
                <div className="flex items-center gap-2.5 p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                  <svg
                    className="w-4 h-4 text-blue-500 shrink-0 animate-spin"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                  <p className="text-xs font-medium text-slate-700 truncate">
                    {progressMessage || "准备中..."}
                  </p>
                </div>
              </div>

              {showLiveTable && liveStats && (
                <CompanyQueryResult
                  result={{
                    companies: liveCompanies,
                    company_stats: liveStats,
                  }}
                />
              )}
            </div>
          )}

          {previewState === "result" &&
            result &&
            (moduleType === "print" ? (
              <PrintProgress
                result={result}
                taskStatus={printTaskStatus}
                onCancel={onCancelPrint}
                selectedOrders={selectedOrders}
                onSelectedOrdersChange={onSelectedOrdersChange}
                onPrintOrders={onPrintOrders}
                printedOrders={printedOrders}
                printingOrders={printingOrders}
              />
            ) : ResultComponent ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 shadow-inner">
                <ResultComponent result={result} />
              </div>
            ) : null)}
        </div>
      </div>
    </div>
  );
}
