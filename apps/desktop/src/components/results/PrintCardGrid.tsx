import type { ProcessingResult, PrintTaskStatus } from "../../types";

interface Props {
  result: ProcessingResult;
  taskStatus: PrintTaskStatus | null;
  onCancel: () => void;
}

export default function PrintProgress({ result, taskStatus, onCancel }: Props) {
  const stats = result.print_stats;
  const isRunning = taskStatus?.status === "running" || taskStatus?.status === "pending";
  const progress = taskStatus
    ? taskStatus.total_jobs > 0
      ? Math.round(
          ((taskStatus.completed_jobs + taskStatus.failed_jobs) / taskStatus.total_jobs) * 100,
        )
      : 0
    : 0;

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="grid grid-cols-4 gap-2">
        <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
          <p className="text-lg font-bold text-slate-800">{stats?.total_jobs ?? 0}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">总任务</p>
        </div>
        <div className="rounded-lg bg-emerald-50 p-3 text-center border border-emerald-200">
          <p className="text-lg font-bold text-emerald-700">
            {taskStatus?.completed_jobs ?? stats?.submitted ?? 0}
          </p>
          <p className="text-[10px] text-emerald-600 mt-0.5">已提交</p>
        </div>
        <div className="rounded-lg bg-red-50 p-3 text-center border border-red-200">
          <p className="text-lg font-bold text-red-700">
            {taskStatus?.failed_jobs ?? stats?.failed ?? 0}
          </p>
          <p className="text-[10px] text-red-600 mt-0.5">失败</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
          <p
            className="text-lg font-bold text-slate-700 truncate"
            title={result.printer_used || taskStatus?.printer_name || ""}
          >
            {result.printer_used || taskStatus?.printer_name || "-"}
          </p>
          <p className="text-[10px] text-slate-500 mt-0.5">打印机</p>
        </div>
      </div>

      {isRunning && taskStatus && (
        <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-blue-700">正在打印...</span>
            <button
              onClick={onCancel}
              className="px-3 py-1 text-[11px] font-medium text-red-600 bg-white border border-red-200 rounded-md hover:bg-red-50 active:scale-95 transition-all cursor-pointer"
            >
              中止打印
            </button>
          </div>

          <div className="w-full bg-blue-100 rounded-full h-2 mb-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-[10px] text-slate-500">
            <span>
              {taskStatus.completed_jobs + taskStatus.failed_jobs} / {taskStatus.total_jobs}
              {taskStatus.failed_jobs > 0 && (
                <span className="text-red-500 ml-1">({taskStatus.failed_jobs} 失败)</span>
              )}
            </span>
            <span>{progress}%</span>
          </div>

          {taskStatus.current_file && (
            <div className="mt-2 px-3 py-2 rounded-md bg-white/70 border border-slate-100">
              {taskStatus.current_company && (
                <p className="text-[10px] font-medium text-slate-600 mb-0.5">
                  {taskStatus.current_company}
                </p>
              )}
              <p className="text-[11px] text-slate-700 truncate" title={taskStatus.current_file}>
                {taskStatus.current_file}
              </p>
            </div>
          )}
        </div>
      )}

      {taskStatus?.status === "cancelled" && (
        <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4 text-center">
          <p className="text-xs font-semibold text-amber-700">打印任务已中止</p>
          <p className="text-[10px] text-amber-600 mt-1">
            已提交 {taskStatus.completed_jobs} 个，失败 {taskStatus.failed_jobs} 个
          </p>
        </div>
      )}

      {taskStatus?.status === "completed" && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4 text-center">
          <p className="text-xs font-semibold text-emerald-700">
            {taskStatus.failed_jobs > 0 ? "打印完成（部分失败）" : "打印全部完成"}
          </p>
          <p className="text-[10px] text-emerald-600 mt-1">
            成功 {taskStatus.completed_jobs} 个
            {taskStatus.failed_jobs > 0 ? `，失败 ${taskStatus.failed_jobs} 个` : ""}
          </p>
        </div>
      )}

      {taskStatus?.status === "failed" && (
        <div className="rounded-lg border border-red-200 bg-red-50/50 p-4 text-center">
          <p className="text-xs font-semibold text-red-700">打印任务失败</p>
        </div>
      )}
    </div>
  );
}
