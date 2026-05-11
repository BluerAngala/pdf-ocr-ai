import type { PrinterInfo } from "../../types";

interface Props {
  sampleRoot: string;
  printerName: string;
  printCopies: number;
  printers: PrinterInfo[];
  running: boolean;
  onSampleRootChange: (v: string) => void;
  onPrinterNameChange: (v: string) => void;
  onPrintCopiesChange: (v: number) => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onRun: () => void;
}

export default function PrintConfig({
  sampleRoot,
  printerName,
  printCopies,
  printers,
  running,
  onSampleRootChange,
  onPrinterNameChange,
  onPrintCopiesChange,
  onPreset,
  onSelectFolder,
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
              className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 hover:text-slate-700 hover:bg-slate-50 px-2 py-1 rounded transition-colors cursor-pointer"
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
              <label className="text-xs font-medium text-slate-500">🗂️ 打印文件夹</label>
              <input
                type="text"
                readOnly
                value={sampleRoot}
                onChange={(e) => onSampleRootChange(e.target.value)}
                placeholder="选择包含 PDF 的文件夹..."
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
              />
              <button
                onClick={onSelectFolder}
                className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-slate-100 hover:border-slate-300 hover:text-slate-700 transition-all cursor-pointer"
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
              <label className="text-xs font-medium text-slate-500">🖨️ 打印机</label>
              <select
                value={printerName}
                onChange={(e) => onPrinterNameChange(e.target.value)}
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all cursor-pointer"
              >
                {printers.length === 0 && <option value="">未检测到打印机</option>}
                {printers.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                    {p.is_default ? " (默认)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">🔢 打印份数</label>
              <input
                type="number"
                min={1}
                max={99}
                value={printCopies}
                onChange={(e) => onPrintCopiesChange(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
              />
            </div>
          </div>
        </div>
      </div>
      <button
        onClick={onRun}
        disabled={running}
        className="shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white bg-slate-700 hover:bg-slate-800 active:scale-[0.98] transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"
          />
        </svg>
        {running ? "打印中..." : "开始打印"}
      </button>
    </div>
  );
}
