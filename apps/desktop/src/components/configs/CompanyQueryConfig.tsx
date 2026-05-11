interface Props {
  excelFile: string;
  running: boolean;
  rangeStart: number;
  rangeEnd: number;
  onExcelFileChange: (v: string) => void;
  onRangeStartChange: (v: number) => void;
  onRangeEndChange: (v: number) => void;
  onPreset: () => void;
  onSelectExcel: () => void;
  onRun: () => void;
  onCancel: () => void;
}

export default function CompanyQueryConfig({
  excelFile,
  running,
  rangeStart,
  rangeEnd,
  onExcelFileChange,
  onRangeStartChange,
  onRangeEndChange,
  onPreset,
  onSelectExcel,
  onRun,
  onCancel,
}: Props) {
  return (
    <div className="h-full flex flex-col gap-4 overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              ⚙️ 配置
            </h3>
            <button
              onClick={onPreset}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 px-2 py-1 rounded transition-colors cursor-pointer"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
              测试示例
            </button>
          </div>
          <div className="p-4 space-y-3.5">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">📊 企业信息数据 Excel</label>
              <input
                type="text"
                readOnly
                value={excelFile}
                onChange={(e) => onExcelFileChange(e.target.value)}
                placeholder="选择包含被执行人列表的 Excel..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-400 transition-all"
              />
              <button
                onClick={onSelectExcel}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-emerald-50 hover:border-emerald-200 hover:text-emerald-700 transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                📊 选择 Excel 文件
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">📋 查询范围（行号）</label>
              <div className="flex items-center gap-2">
                <div className="flex-1">
                  <div className="text-[10px] text-slate-400 mb-1">从第</div>
                  <input
                    type="number"
                    min={1}
                    value={rangeStart}
                    onChange={(e) => onRangeStartChange(Math.max(1, parseInt(e.target.value) || 1))}
                    disabled={running}
                    className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  />
                </div>
                <span className="text-slate-300 mt-4">—</span>
                <div className="flex-1">
                  <div className="text-[10px] text-slate-400 mb-1">到第</div>
                  <input
                    type="number"
                    min={0}
                    value={rangeEnd}
                    onChange={(e) => onRangeEndChange(parseInt(e.target.value) || 0)}
                    disabled={running}
                    placeholder="0=全部"
                    className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  />
                </div>
              </div>
              <p className="text-[10px] text-slate-400">填 0 表示到末尾，支持断点续查</p>
            </div>

            <p className="text-[10px] text-slate-400 leading-relaxed">
              Excel
              需包含"被执行人"列，系统将逐个查询企业工商信息。已查询过的条目会自动跳过（缓存）。
            </p>
          </div>
        </div>
      </div>

      {running ? (
        <button
          onClick={onCancel}
          className="shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white bg-red-500 hover:bg-red-600 active:scale-[0.98] transition-all shadow-sm cursor-pointer flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
          取消查询
        </button>
      ) : (
        <button
          onClick={onRun}
          className="shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] transition-all shadow-sm cursor-pointer flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          开始查询
        </button>
      )}
    </div>
  );
}
