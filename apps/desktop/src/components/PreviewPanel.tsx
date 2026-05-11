import type { ModuleType, PreviewState, ProcessingResult, CompanyQueryItem } from "../types";
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
  liveCompanies: CompanyQueryItem[];
  onOpenReport: () => void;
  onOpenOutput: () => void;
  onClearResult: () => void;
}

const STATUS_BADGE: Record<PreviewState, { text: string; className: string }> = {
  empty: {
    text: "就绪",
    className: "text-[10px] font-medium text-slate-400 bg-slate-100 px-2 py-0.5 rounded",
  },
  progress: {
    text: "运行中",
    className: "text-[10px] font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded",
  },
  result: {
    text: "完成",
    className: "text-[10px] font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded",
  },
};

const RESULT_COMPONENTS: Record<ModuleType, React.ComponentType<{ result: ProcessingResult }>> = {
  "non-litigation": NonLitigationResult,
  enforcement: EnforcementResult,
  "company-query": CompanyQueryResult,
  print: PrintCardGrid,
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
  progressMessage,
  result,
  liveCompanies,
  onOpenReport,
  onOpenOutput,
  onClearResult,
}: Props) {
  const badge = STATUS_BADGE[previewState];
  const percentage = progressTotal > 0 ? Math.round((progressCurrent / progressTotal) * 100) : 0;
  const ResultComponent = RESULT_COMPONENTS[moduleType];
  const emptyHint = EMPTY_HINTS[moduleType];

  const showLiveTable =
    moduleType === "company-query" && previewState === "progress" && liveCompanies.length > 0;

  const liveStats = showLiveTable
    ? {
        total: progressTotal,
        success_count: liveCompanies.filter((c) => c.status === "success").length,
        fail_count: liveCompanies.filter((c) => c.status === "failed").length,
      }
    : null;

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

          {previewState === "progress" && (
            <div className="flex flex-col gap-3">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">
                    阶段: <span className="font-semibold text-slate-800">{phase || "-"}</span>
                  </span>
                  <span className="text-xs font-medium text-slate-500">
                    {progressCurrent} / {progressTotal}
                  </span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className="progress-bar h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full"
                    style={{ width: `${percentage}%` }}
                  />
                </div>
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
                    company_stats: liveStats as any,
                  }}
                />
              )}
            </div>
          )}

          {previewState === "result" && result && <ResultComponent result={result} />}
        </div>

        {previewState === "result" && result && (
          <div className="shrink-0 px-4 py-3 border-t border-slate-100">
            <div className="flex gap-2 justify-center">
              <button
                onClick={onOpenReport}
                className="h-9 px-5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors cursor-pointer"
              >
                📄 查看报告
              </button>
              <button
                onClick={onOpenOutput}
                className="h-9 px-5 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors cursor-pointer"
              >
                📂 打开输出
              </button>
              <button
                onClick={onClearResult}
                className="h-9 px-5 text-sm font-medium text-slate-500 bg-white border border-slate-200 rounded-md hover:text-red-600 hover:border-red-300 hover:bg-red-50 transition-colors cursor-pointer"
              >
                🗑 清空当前
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
