import { useMemo, useState } from "react";
import type { ProcessingResult, PrintTaskStatus } from "../../types";

interface Props {
  result: ProcessingResult;
  taskStatus: PrintTaskStatus | null;
  onCancel: () => void;
  selectedOrders: Set<number>;
  onSelectedOrdersChange: (orders: Set<number>) => void;
  onPrintOrders: (orders: number[]) => void;
  printedOrders: Set<number>;
  printingOrders: Set<number>;
}

export default function PrintProgress({
  result,
  taskStatus,
  onCancel,
  selectedOrders,
  onSelectedOrdersChange,
  onPrintOrders,
  printedOrders,
  printingOrders,
}: Props) {
  const [removedOrders, setRemovedOrders] = useState<Set<number>>(new Set());

  const errors = result.print_errors || [];
  const matchResults = useMemo(
    () => (result.print_match_results || []).filter((m) => !removedOrders.has(m.order)),
    [result.print_match_results, removedOrders],
  );

  const totalMatched = matchResults.filter((m) => m.status === "matched").length;
  const totalUnmatched = matchResults.filter((m) => m.status === "no_match").length;
  const totalFiles = matchResults.reduce((sum, m) => sum + m.files.length, 0);
  const printedCount = matchResults.filter((m) => printedOrders.has(m.order)).length;

  const selectedFileCount = useMemo(() => {
    return matchResults
      .filter((m) => selectedOrders.has(m.order) && m.status === "matched")
      .reduce((sum, m) => sum + m.files.length, 0);
  }, [matchResults, selectedOrders]);

  const matchedOrders = useMemo(
    () => new Set(matchResults.filter((m) => m.status === "matched").map((m) => m.order)),
    [matchResults],
  );

  const toggleSelect = (order: number) => {
    const next = new Set(selectedOrders);
    if (next.has(order)) next.delete(order);
    else next.add(order);
    onSelectedOrdersChange(next);
  };

  const toggleAll = () => {
    if (selectedOrders.size === matchedOrders.size) {
      onSelectedOrdersChange(new Set());
    } else {
      onSelectedOrdersChange(new Set(matchedOrders));
    }
  };

  return (
    <div className="flex flex-col gap-2 h-full">
      <div className="flex items-center justify-between px-1 py-2 border-b border-slate-100">
        <span className="text-xs font-semibold text-slate-700">匹配结果</span>
        <div className="flex items-center gap-3 text-[10px] text-slate-500">
          <span>
            匹配 <b className="text-emerald-700">{totalMatched}</b>/{totalMatched + totalUnmatched}
          </span>
          <span>
            PDF <b>{totalFiles}</b>
          </span>
          {totalUnmatched > 0 && <span className="text-red-500">未匹配 {totalUnmatched}</span>}
          {printedCount > 0 && (
            <span>
              已打印 <b className="text-emerald-700">{printedCount}</b>
            </span>
          )}
          <span>
            打印机 <b className="text-slate-700">{result.printer_used || "-"}</b>
          </span>
        </div>
      </div>

      {(taskStatus?.status === "running" || taskStatus?.status === "pending") && taskStatus && (
        <div className="rounded border border-blue-200 bg-blue-50 p-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            <span className="text-[11px] text-blue-700 font-medium">
              打印中: {taskStatus.current_file || "准备中..."}
            </span>
            {taskStatus.total_jobs > 0 && (
              <span className="text-[10px] text-slate-400">
                {taskStatus.completed_jobs + taskStatus.failed_jobs}/{taskStatus.total_jobs}
              </span>
            )}
          </div>
          <button
            onClick={onCancel}
            className="px-2 py-0.5 text-[10px] font-medium text-red-600 bg-white border border-red-200 rounded hover:bg-red-50 cursor-pointer"
          >
            中止
          </button>
        </div>
      )}

      {matchResults.length > 0 && (
        <div className="flex items-center gap-3 px-1 text-[10px]">
          <label className="flex items-center gap-1 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={selectedOrders.size === matchedOrders.size && matchedOrders.size > 0}
              onChange={toggleAll}
              className="w-3 h-3 rounded border-slate-300 text-blue-600"
            />
            <span className="text-slate-500">全选</span>
          </label>
          <span className="text-slate-400">
            已选 {selectedOrders.size} 条 / {selectedFileCount} 个PDF
          </span>
        </div>
      )}

      {matchResults.length > 0 && (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <table className="w-full text-xs">
            <tbody>
              {matchResults.map((item) => {
                const isSelected = selectedOrders.has(item.order);
                const isMatched = item.status === "matched";
                const isPrinted = printedOrders.has(item.order);
                const isPrinting = printingOrders.has(item.order);
                const fileNames = item.files.map((f) => f.name.replace(/\.pdf$/i, ""));
                const companyIsInFileName =
                  item.company && fileNames.some((fn) => fn.includes(item.company));
                return (
                  <tr
                    key={item.order}
                    className={`border-b border-slate-50 ${isSelected ? "" : "opacity-35"}`}
                  >
                    <td className="w-6 py-1.5 text-center">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(item.order)}
                        className="w-3.5 h-3.5 rounded border-slate-300 text-blue-600"
                      />
                    </td>
                    <td className="w-8 py-1.5 text-right text-slate-400 font-mono">
                      {item.order}.
                    </td>
                    <td className="py-1.5">
                      {isMatched ? (
                        <span className="text-slate-600">
                          {item.company && !companyIsInFileName && (
                            <span className="text-slate-700 font-medium">{item.company} — </span>
                          )}
                          {fileNames.join("、")}
                          {isPrinted && (
                            <span className="ml-1.5 text-emerald-600 font-medium">✓</span>
                          )}
                          {isPrinting && <span className="ml-1.5 text-blue-500">打印中...</span>}
                        </span>
                      ) : (
                        <span>
                          <span className="text-slate-700">{item.company}</span>
                          <span className="text-red-400 ml-2">未匹配</span>
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {isMatched && !isPrinting && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onPrintOrders([item.order]);
                            }}
                            className={`px-1.5 py-0.5 text-[10px] rounded cursor-pointer text-center whitespace-nowrap ${
                              isPrinted
                                ? "text-emerald-600 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100"
                                : "text-blue-600 bg-blue-50 border border-blue-200 hover:bg-blue-100"
                            }`}
                          >
                            {isPrinted ? "重新打印" : "打印"}
                          </button>
                        )}
                        {isPrinting && (
                          <span className="px-1.5 py-0.5 text-[10px] text-blue-500">打印中</span>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setRemovedOrders((prev) => new Set(prev).add(item.order));
                          }}
                          className="px-1.5 py-0.5 text-[10px] text-slate-400 hover:text-red-500 cursor-pointer text-center whitespace-nowrap"
                        >
                          移除
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {errors.length > 0 && (
        <div className="rounded border border-red-200 bg-red-50 p-3 text-[10px]">
          <p className="font-semibold text-red-700 mb-1">打印失败 {errors.length} 个</p>
          {errors.map((err, i) => (
            <p key={i} className="text-red-600">
              {err.company} {err.file && <span className="text-slate-500">{err.file}</span>} —{" "}
              {err.error}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
