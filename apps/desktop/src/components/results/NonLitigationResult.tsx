import type { ProcessingResult, ValidationDetail, TimingStats } from "../../types";

const STATUS_STYLE: Record<string, string> = {
  pass: "border-l-emerald-500 bg-emerald-50/50",
  warning: "border-l-amber-500 bg-amber-50/50",
  fail: "border-l-red-500 bg-red-50/50",
};

const METHOD_LABEL: Record<string, string> = {
  pdfplumber: "PDF提取",
  pdfplumber_sequential: "PDF提取",
  rapidocr: "OCR",
  region_first_sequential: "区域优先",
  region_first: "区域优先",
  mixed: "混合",
};

const TYPE_LABEL: Record<string, string> = {
  notice: "责催",
  application: "申请书",
  authorization: "授权书",
  letter: "所函",
};

function formatSeconds(s: number): string {
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const sec = (s % 60).toFixed(0);
  return `${m}m${sec}s`;
}

function computeTimingSummary(ts: TimingStats | undefined) {
  if (!ts) return null;
  let grandTotal = 0;
  let fileCount = 0;
  let maxTime = 0;
  let maxType = "";
  for (const [type, stats] of Object.entries(ts)) {
    grandTotal += stats.total;
    fileCount += stats.count;
    if (stats.max > maxTime) {
      maxTime = stats.max;
      maxType = type;
    }
  }
  return {
    grandTotal,
    fileCount,
    avgPerFile: fileCount > 0 ? grandTotal / fileCount : 0,
    maxTime,
    maxType,
  };
}

function DetailItem({ item }: { item: ValidationDetail }) {
  const borderStyle = STATUS_STYLE[item.status] || "border-l-slate-300";
  const parts: string[] = [];
  const d = item.details || {};

  if (d.total_pages) parts.push(`${d.total_pages}页`);
  if (d.detected_cases) parts.push(`${d.detected_cases}案件`);
  const detectedNotices = d.detected_notices as string[] | undefined;
  if (detectedNotices?.length) parts.push(detectedNotices.slice(0, 2).join(", "));

  const strategy = d.optimization_strategy as string | undefined;
  if (strategy && strategy !== "unknown") {
    parts.push(METHOD_LABEL[strategy] || strategy);
  }

  if (item.timing?.total_duration) {
    parts.push(`${formatSeconds(item.timing.total_duration)}`);
  }

  const badges: string[] = [];
  if (
    item.accuracy?.region_first_hit_rate !== undefined &&
    item.accuracy.region_first_hit_rate > 0
  ) {
    badges.push(`区域命中${Math.round(item.accuracy.region_first_hit_rate)}%`);
  }
  if (item.accuracy?.fallback_rate !== undefined && item.accuracy.fallback_rate > 0) {
    badges.push(`回退${Math.round(item.accuracy.fallback_rate)}%`);
  }
  if (
    item.accuracy?.keyword_detection_rate !== undefined &&
    item.accuracy.keyword_detection_rate > 0
  ) {
    badges.push(`关键字${Math.round(item.accuracy.keyword_detection_rate)}%`);
  }

  const sameRootRemap = d.same_root_remap as boolean | undefined;
  const suggestions = item.suggestions?.filter(Boolean).slice(0, 2) || [];

  return (
    <div className={`border-l-2 ${borderStyle} rounded px-3 py-2`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-[10px] font-medium text-slate-400 shrink-0">
            {TYPE_LABEL[item.file_type] || item.file_type}
          </span>
          <span className="text-xs font-medium text-slate-700 truncate">{item.file_name}</span>
        </div>
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
      {badges.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1">
          {badges.map((b, i) => (
            <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
              {b}
            </span>
          ))}
        </div>
      )}
      {sameRootRemap && (() => {
        const summary = d.same_root_remap_summary as { selected_notice?: string; target_notice?: string } | undefined;
        const sel = summary?.selected_notice ?? detectedNotices?.[0];
        const tgt = summary?.target_notice ?? (d.matched_target_notice as string | undefined);
        if (!sel && !tgt) return <p className="text-[10px] text-amber-600 mt-0.5">同根号重映射</p>;
        return (
          <p className="text-[10px] text-amber-600 mt-0.5">
            同根号重映射：OCR 实际识别 <span className="font-mono">{sel ?? "?"}</span>，按主号 <span className="font-mono">{tgt ?? "?"}</span> 导出
          </p>
        );
      })()}
      {suggestions.length > 0 && (
        <p className="text-[10px] text-slate-400 mt-0.5">{suggestions.join(" | ")}</p>
      )}
    </div>
  );
}

export default function NonLitigationResult({ result }: { result: ProcessingResult }) {
  const v = result?.summary?.validation;
  const ts = result?.timing_statistics;
  const timingSummary = computeTimingSummary(ts);
  const runtime = result?.summary?.runtime_seconds;
  const mode = result?.summary?.mode;

  const failedItems = result?.validation_failed || [];
  const warningItems = result?.validation_warnings || [];
  const allDetails = result?.validation_details || [];
  const passItems = allDetails.filter((d) => d.status === "pass");
  const showItems = [...failedItems, ...warningItems, ...passItems];

  return (
    <div className="flex flex-col gap-3 h-full">
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

      {timingSummary && (
        <div className="rounded-lg bg-indigo-50/50 border border-indigo-100 px-3 py-2">
          <div className="flex items-center gap-4 flex-wrap">
            <span className="text-[11px] font-medium text-indigo-600">⏱ OCR 耗时</span>
            <span className="text-[10px] text-slate-500">
              总计{" "}
              <strong className="text-slate-700">{formatSeconds(timingSummary.grandTotal)}</strong>
            </span>
            <span className="text-[10px] text-slate-500">
              均文件{" "}
              <strong className="text-slate-700">{formatSeconds(timingSummary.avgPerFile)}</strong>
            </span>
            <span className="text-[10px] text-slate-500">
              最慢{" "}
              <strong className="text-slate-700">{formatSeconds(timingSummary.maxTime)}</strong>
              <span className="text-slate-400 ml-0.5">
                ({TYPE_LABEL[timingSummary.maxType] || timingSummary.maxType})
              </span>
            </span>
            <span className="text-[10px] text-slate-400">
              含导出验证{" "}
              <strong className="text-slate-600">{runtime ? formatSeconds(runtime) : "-"}</strong>
              {mode && <span className="ml-1">{mode === "real_ocr" ? "真实OCR" : "Mock"}</span>}
            </span>
          </div>
        </div>
      )}

      {showItems.length > 0 && (
        <div className="flex-1 min-h-0 flex flex-col">
          <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2 shrink-0">
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
