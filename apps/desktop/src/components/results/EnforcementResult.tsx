import type { ProcessingResult, EnforcementExtracted } from "../../types";

function ExtractedItem({ item }: { item: EnforcementExtracted }) {
  const isWithdraw = item.is_withdraw;
  const parties = [...item.applicants.map((a) => a.name), ...item.respondents.map((r) => r.name)];

  return (
    <div
      className={`border-l-2 rounded px-3 py-2 ${isWithdraw ? "border-l-amber-500 bg-amber-50/50" : "border-l-blue-500 bg-blue-50/30"}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-slate-700 truncate">
          {item.court_case_number || "（未识别案号）"}
        </span>
        <span
          className={`text-[10px] font-semibold shrink-0 ${isWithdraw ? "text-amber-600" : "text-emerald-600"}`}
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

export default function EnforcementResult({ result }: { result: ProcessingResult }) {
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
