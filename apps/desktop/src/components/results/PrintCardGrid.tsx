import type { ProcessingResult, PrintFileItem } from "../../types";

const CARD_STATUS: Record<
  string,
  { icon: string; label: string; border: string; bg: string; text: string }
> = {
  pending: {
    icon: "⏳",
    label: "等待中",
    border: "border-slate-200",
    bg: "bg-white",
    text: "text-slate-500",
  },
  printing: {
    icon: "🖨",
    label: "打印中",
    border: "border-blue-300",
    bg: "bg-blue-50",
    text: "text-blue-600",
  },
  printed: {
    icon: "✅",
    label: "已完成",
    border: "border-emerald-200",
    bg: "bg-emerald-50/50",
    text: "text-emerald-600",
  },
  failed: {
    icon: "❌",
    label: "失败",
    border: "border-red-200",
    bg: "bg-red-50/50",
    text: "text-red-600",
  },
};

function PrintCard({ item }: { item: PrintFileItem }) {
  const s = CARD_STATUS[item.status] || CARD_STATUS.pending;

  return (
    <div
      className={`rounded-lg border ${s.border} ${s.bg} p-3 flex flex-col items-center gap-2 transition-colors`}
    >
      <svg className="w-8 h-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <p className="text-[11px] text-slate-700 truncate w-full text-center" title={item.filename}>
        {item.filename}
      </p>
      <span className={`text-[10px] font-medium ${s.text}`}>
        {s.icon} {s.label}
      </span>
      {item.status === "failed" && item.error && (
        <p className="text-[9px] text-red-400 truncate w-full text-center" title={item.error}>
          {item.error}
        </p>
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
            {files.map((item, i) => (
              <PrintCard key={i} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
