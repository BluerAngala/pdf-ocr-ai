import type {
  ModuleType,
  PreviewState,
  ProcessingResult,
  ValidationDetail,
  EnforcementExtracted,
} from "../types";

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
            item.status === "pass"
              ? "text-emerald-600"
              : item.status === "warning"
                ? "text-amber-600"
                : "text-red-600"
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

function ExtractedItem({ item }: { item: EnforcementExtracted }) {
  const isWithdraw = item.is_withdraw;
  const parties = [...item.applicants.map((a) => a.name), ...item.respondents.map((r) => r.name)];

  return (
    <div
      className={`border-l-2 rounded px-3 py-2 ${
        isWithdraw ? "border-l-amber-500 bg-amber-50/50" : "border-l-blue-500 bg-blue-50/30"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-slate-700 truncate">
          {item.court_case_number || "（未识别案号）"}
        </span>
        <span
          className={`text-[10px] font-semibold shrink-0 ${
            isWithdraw ? "text-amber-600" : "text-emerald-600"
          }`}
        >
          {isWithdraw ? "撤回执行" : item.ruling_result || "准予执行"}
        </span>
      </div>
      {item.notice_numbers.length > 0 && (
        <p className="text-[11px] text-slate-500 mt-0.5 truncate">
          责令号: {item.notice_numbers.slice(0, 3).join("、")}
        </p>
      )}
      {parties.length > 0 && (
        <p className="text-[10px] text-slate-400 mt-0.5 truncate">
          {parties.slice(0, 4).join(" · ")}
          {parties.length > 4 ? " ..." : ""}
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

function NonLitigationResult({ result }: { result: ProcessingResult }) {
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
          <p className="text-lg font-bold text-blue-700">
            {Math.round((v?.pass_rate || 0) * 100)}%
          </p>
          <p className="text-[10px] text-blue-600 mt-0.5">通过率</p>
        </div>
      </div>

      {result.summary?.quality && (
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-slate-50 px-3 py-2 flex items-center justify-between border border-slate-100">
            <span className="text-[11px] text-slate-500">📄 生成文件</span>
            <span className="text-sm font-bold text-slate-700">
              {result.summary.created_count ?? "-"}
            </span>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2 flex items-center justify-between border border-slate-100">
            <span className="text-[11px] text-slate-500">📊 页数匹配率</span>
            <span className="text-sm font-bold text-slate-700">
              {Math.round((result.summary.quality?.page_count_match_rate || 0) * 100)}%
            </span>
          </div>
        </div>
      )}

      {showItems.length > 0 && (
        <div>
          <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
            验证明细
          </h4>
          <div className="space-y-1.5 flex-1 min-h-0 overflow-y-auto">
            {showItems.map((item, i) => (
              <DetailItem key={i} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EnforcementResult({ result }: { result: ProcessingResult }) {
  const stats = result.enforcement_stats;
  const extracted = result.extracted || [];
  const matchRate =
    stats && stats.total_excel_rows > 0
      ? Math.round((stats.matched_rows / stats.total_excel_rows) * 100)
      : 0;

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
          <span className="text-sm font-bold text-slate-700">
            {result.processed ?? extracted.length}
          </span>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2 flex items-center justify-between border border-slate-100">
          <span className="text-[11px] text-slate-500">📊 匹配率</span>
          <span className="text-sm font-bold text-slate-700">{matchRate}%</span>
        </div>
      </div>

      {extracted.length > 0 && (
        <div>
          <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
            提取明细
          </h4>
          <div className="space-y-1.5 flex-1 min-h-0 overflow-y-auto">
            {extracted.map((item, i) => (
              <ExtractedItem key={i} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

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
  const isEnforcement = moduleType === "enforcement";

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
                <p className="text-[10px] text-slate-300">
                  {isEnforcement ? "将显示提取结果与匹配统计" : "将显示处理进度与结果"}
                </p>
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
                <div className="flex items-center gap-2.5 p-3 bg-slate-50 rounded-lg border border-slate-100">
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
            </div>
          )}

          {previewState === "result" && result && (
            <>
              {isEnforcement ? (
                <EnforcementResult result={result} />
              ) : (
                <NonLitigationResult result={result} />
              )}
            </>
          )}
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
