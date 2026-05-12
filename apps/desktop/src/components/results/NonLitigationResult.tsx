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
  const detectedNotices = d.detected_notices as string[] | undefined;
  if (detectedNotices?.length) parts.push(detectedNotices.slice(0, 2).join(", "));
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
