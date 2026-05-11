interface Props {
  sampleRoot: string;
  excelFile: string;
  forceOcr: boolean;
  running: boolean;
  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onForceOcrChange: (v: boolean) => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onRun: () => void;
}

export default function EnforcementConfig({
  sampleRoot,
  excelFile,
  forceOcr,
  running,
  onSampleRootChange,
  onExcelFileChange,
  onForceOcrChange,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onRun,
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
              className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-600 hover:text-amber-700 hover:bg-amber-50 px-2 py-1 rounded transition-colors cursor-pointer"
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
              <label className="text-xs font-medium text-slate-500">🗂️ 裁定 PDF 文件夹</label>
              <input
                type="text"
                readOnly
                value={sampleRoot}
                onChange={(e) => onSampleRootChange(e.target.value)}
                placeholder="选择文件夹..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-400 transition-all"
              />
              <button
                onClick={onSelectFolder}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-amber-50 hover:border-amber-200 hover:text-amber-700 transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                  />
                </svg>
                📁 选择文件夹
              </button>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">📋 案件台账</label>
              <input
                type="text"
                readOnly
                value={excelFile}
                onChange={(e) => onExcelFileChange(e.target.value)}
                placeholder="选择文件..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-400 transition-all"
              />
              <button
                onClick={onSelectExcel}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-amber-50 hover:border-amber-200 hover:text-amber-700 transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                📊 选择文件
              </button>
            </div>
            <div className="flex items-center gap-4 pt-1">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-500 hover:text-slate-700 transition-colors">
                <input
                  type="checkbox"
                  checked={forceOcr}
                  onChange={(e) => onForceOcrChange(e.target.checked)}
                  className="rounded border-slate-300 text-amber-600 focus:ring-amber-500/30 w-3.5 h-3.5"
                />
                🔄 强制 OCR
              </label>
            </div>
          </div>
        </div>
      </div>
      <button
        onClick={onRun}
        disabled={running}
        className="shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white bg-amber-600 hover:bg-amber-700 active:scale-[0.98] transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        {running ? "提取中..." : "开始提取"}
      </button>
    </div>
  );
}
