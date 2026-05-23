import { useState, type ReactNode } from "react";
import type { ProcessingResult, EnforcementExtracted } from "../../types";

function CollapsibleSection({
  title,
  count,
  totalHint,
  defaultOpen = false,
  tone = "success",
  children,
}: {
  title: string;
  count: number;
  totalHint?: string;
  defaultOpen?: boolean;
  tone?: "success" | "warning" | "error";
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  const toneStyles = {
    success: {
      border: "border-emerald-200",
      titleColor: "text-emerald-700",
      bg: "bg-emerald-50/30",
    },
    warning: { border: "border-amber-200", titleColor: "text-amber-700", bg: "bg-amber-50/30" },
    error: { border: "border-red-200", titleColor: "text-red-700", bg: "bg-red-50/30" },
  };

  const style = toneStyles[tone];

  return (
    <div className={`rounded-lg border ${style.border} bg-white overflow-hidden`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-left hover:bg-slate-50 transition-colors cursor-pointer ${style.bg}`}
      >
        <span className={`text-xs font-semibold ${style.titleColor}`}>
          {open ? "▼" : "▶"} {title}
          <span className="font-normal text-slate-500 ml-1">
            ({count}
            {totalHint ? ` / ${totalHint}` : ""})
          </span>
        </span>
        <span className="text-[10px] text-slate-400 shrink-0">{open ? "收起" : "展开"}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 pt-0 space-y-1.5 max-h-52 overflow-y-auto">{children}</div>
      )}
    </div>
  );
}

function ExtractedItem({ item, isMulti }: { item: EnforcementExtracted; isMulti?: boolean }) {
  const ledgerOk = item.ledger_matched === true;
  const parties = [...item.applicants.map((a) => a.name), ...item.respondents.map((r) => r.name)];

  // 已匹配用绿色系，未匹配用红色系，保持视觉一致性
  const itemStyles = ledgerOk
    ? { border: "border-l-emerald-400", bg: "bg-emerald-50/30", statusText: "text-emerald-700" }
    : { border: "border-l-red-400", bg: "bg-red-50/40", statusText: "text-red-700" };

  return (
    <div className={`border-l-2 rounded px-3 py-2 ${itemStyles.border} ${itemStyles.bg}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-slate-700 truncate">
          {item.court_case_number || "（未识别案号）"}
        </span>
        <div className="flex items-center gap-1.5 shrink-0">
          {isMulti && (
            <span className="text-[10px] font-medium text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded">
              多条数据
            </span>
          )}
          {!ledgerOk && (
            <span className="text-[10px] font-medium text-red-600 bg-red-100 px-1.5 py-0.5 rounded">
              未匹配
            </span>
          )}
          {/* 裁定结果颜色与匹配状态一致，已匹配=绿色，未匹配=红色 */}
          <span className={`text-[10px] font-semibold ${itemStyles.statusText}`}>
            {item.ruling_result || "准予执行"}
          </span>
        </div>
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

  const totalPdfs = stats?.total_pdfs ?? result.processed ?? extracted.length;
  const matchedCount = extracted.filter((e) => e.ledger_matched === true).length;
  const unmatchedCount = totalPdfs - matchedCount;

  // 统计哪些PDF包含多条数据（通过court_case_number分组）
  const pdfKeyGroups = extracted.reduce(
    (acc, item) => {
      const key = item.court_case_number || "unknown";
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    },
    {} as Record<string, EnforcementExtracted[]>,
  );
  const multiDataPdfs = Object.entries(pdfKeyGroups).filter(([_, items]) => items.length > 1);

  const unmatchedPdfs = stats?.unmatched_pdf_details ?? [];

  return (
    <div className="flex flex-col gap-3 h-full min-h-0">
      {/* 简化统计摘要 */}
      <div className="rounded-lg bg-slate-50 p-3 border border-slate-200">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-600">PDF 总数</span>
          <span className="text-lg font-bold text-slate-800">{totalPdfs}</span>
        </div>
        <div className="flex items-center justify-between mt-2">
          <span className="text-sm text-emerald-600">已匹配</span>
          <span className="text-base font-semibold text-emerald-700">{matchedCount}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-red-500">未匹配</span>
          <span className="text-base font-semibold text-red-600">{unmatchedCount}</span>
        </div>
        {multiDataPdfs.length > 0 && (
          <div className="mt-2 pt-2 border-t border-slate-200">
            <span className="text-xs text-amber-600">
              含多条数据的 PDF: <b>{multiDataPdfs.length}</b> 个
            </span>
          </div>
        )}
      </div>

      {/* 匹配明细 */}
      {matchedCount > 0 && (
        <CollapsibleSection
          title="已匹配明细"
          count={matchedCount}
          defaultOpen={true}
          tone="success"
        >
          {extracted
            .filter((e) => e.ledger_matched === true)
            .map((item, i) => {
              const pdfKey = item.court_case_number || "unknown";
              const isMulti = (pdfKeyGroups[pdfKey]?.length || 0) > 1;
              return <ExtractedItem key={i} item={item} isMulti={isMulti} />;
            })}
        </CollapsibleSection>
      )}

      {/* 未匹配明细 */}
      {unmatchedCount > 0 && (
        <CollapsibleSection
          title="未匹配明细"
          count={unmatchedCount}
          defaultOpen={true}
          tone="error"
        >
          {extracted
            .filter((e) => e.ledger_matched !== true)
            .map((item, i) => {
              const pdfKey = item.court_case_number || "unknown";
              const isMulti = (pdfKeyGroups[pdfKey]?.length || 0) > 1;
              return <ExtractedItem key={i} item={item} isMulti={isMulti} />;
            })}
        </CollapsibleSection>
      )}

      {/* 未匹配PDF详情（来自后端统计） */}
      {unmatchedPdfs.length > 0 && (
        <CollapsibleSection
          title="本批 PDF 未匹配台账"
          count={unmatchedPdfs.length}
          defaultOpen={false}
          tone="warning"
        >
          {unmatchedPdfs.map((item, i) => (
            <div key={i} className="border-l-2 border-l-amber-400 bg-amber-50/50 rounded px-3 py-2">
              <p className="text-xs font-medium text-amber-800 truncate">
                {item.court_case_number || item.pdf_key}
              </p>
              {item.notice_numbers && item.notice_numbers.length > 0 && (
                <p className="text-[10px] text-slate-500 mt-0.5 truncate">
                  责令号: {item.notice_numbers.join("、")}
                </p>
              )}
              <p className="text-[10px] text-amber-600 mt-0.5">{item.reason}</p>
            </div>
          ))}
        </CollapsibleSection>
      )}
    </div>
  );
}
