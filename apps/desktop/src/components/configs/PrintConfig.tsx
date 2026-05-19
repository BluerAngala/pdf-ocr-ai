import { useState, useCallback } from "react";
import type { PrinterInfo, PrintExcelColumn } from "../../types";

interface Props {
  sampleRoot: string;
  excelFile: string;
  printerName: string;
  printCopies: number;
  printers: PrinterInfo[];
  running: boolean;
  rangeStart: number;
  rangeEnd: number;
  columnName: string;
  excelColumns: PrintExcelColumn[];
  printMode: "single" | "double";
  customStartPage: number;
  customEndPage: number;
  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onPrinterNameChange: (v: string) => void;
  onPrintCopiesChange: (v: number) => void;
  onRangeStartChange: (v: number) => void;
  onRangeEndChange: (v: number) => void;
  onColumnNameChange: (v: string) => void;
  onPrintModeChange: (v: "single" | "double") => void;
  onCustomStartPageChange: (v: number) => void;
  onCustomEndPageChange: (v: number) => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onRun: () => void;
  onLoadExcelColumns: () => void;
}

function AccordionSection({
  title,
  icon,
  isOpen,
  onToggle,
  children,
  extra,
}: {
  title: string;
  icon: string;
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  extra?: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
      <div
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between bg-slate-50 hover:bg-slate-100 transition-colors cursor-pointer"
      >
        <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wider flex items-center gap-2">
          <span>{icon}</span>
          {title}
        </h3>
        <div className="flex items-center gap-2">
          {extra}
          <svg
            className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
      <div
        className={`transition-all duration-200 ease-in-out overflow-hidden ${
          isOpen ? "max-h-[800px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="p-4 space-y-3.5">{children}</div>
      </div>
    </div>
  );
}

export default function PrintConfig({
  sampleRoot,
  excelFile,
  printerName,
  printCopies,
  printers,
  running,
  rangeStart,
  rangeEnd,
  columnName,
  excelColumns,
  printMode,
  customStartPage,
  customEndPage,
  onSampleRootChange,
  onExcelFileChange,
  onPrinterNameChange,
  onPrintCopiesChange,
  onRangeStartChange,
  onRangeEndChange,
  onColumnNameChange,
  onPrintModeChange,
  onCustomStartPageChange,
  onCustomEndPageChange,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onRun,
  onLoadExcelColumns,
}: Props) {
  const [openSections, setOpenSections] = useState({ excel: true, print: true });
  const toggle = (s: keyof typeof openSections) => setOpenSections((p) => ({ ...p, [s]: !p[s] }));

  const handleExcelSelect = useCallback(() => {
    onSelectExcel();
  }, [onSelectExcel]);

  const handleExcelChange = useCallback(
    (v: string) => {
      onExcelFileChange(v);
    },
    [onExcelFileChange],
  );

  return (
    <div className="h-full flex flex-col gap-3 overflow-hidden">
      <div className="flex-1 overflow-y-auto space-y-3">
        <AccordionSection
          title="台账与材料"
          icon="📊"
          isOpen={openSections.excel}
          onToggle={() => toggle("excel")}
          extra={
            <button
              onClick={(e) => {
                e.stopPropagation();
                onPreset();
              }}
              className="text-[10px] text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
            >
              测试示例
            </button>
          }
        >
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">材料文件夹</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={sampleRoot}
                  onChange={(e) => onSampleRootChange(e.target.value)}
                  placeholder="选择材料所在文件夹..."
                  className="flex-1 h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
                />
                <button
                  onClick={onSelectFolder}
                  className="h-8 w-8 flex items-center justify-center rounded-md text-slate-600 bg-slate-50 border border-slate-200 hover:bg-slate-100 hover:border-slate-300 hover:text-slate-700 transition-all cursor-pointer"
                  title="选择文件夹"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                    />
                  </svg>
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">台账 Excel</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={excelFile}
                  onChange={(e) => handleExcelChange(e.target.value)}
                  placeholder="选择台账表格（可选）..."
                  className="flex-1 h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
                />
                <button
                  onClick={handleExcelSelect}
                  className="h-8 w-8 flex items-center justify-center rounded-md text-slate-600 bg-slate-50 border border-slate-200 hover:bg-slate-100 hover:border-slate-300 hover:text-slate-700 transition-all cursor-pointer"
                  title="选择Excel文件"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                </button>
              </div>
            </div>

            {excelFile && (
              <>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-slate-500">匹配字段</label>
                    <button
                      onClick={onLoadExcelColumns}
                      className="text-[10px] text-blue-500 hover:text-blue-600 cursor-pointer"
                    >
                      读取列名
                    </button>
                  </div>
                  {excelColumns.length > 0 ? (
                    <select
                      value={columnName}
                      onChange={(e) => onColumnNameChange(e.target.value)}
                      className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all cursor-pointer"
                    >
                      <option value="">-- 选择匹配列 --</option>
                      {excelColumns.map((col) => (
                        <option key={col.column} value={col.column}>
                          {col.column} - {col.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={columnName}
                      onChange={(e) => onColumnNameChange(e.target.value.toUpperCase())}
                      placeholder="输入列字母，如 A、B、C..."
                      maxLength={3}
                      className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
                    />
                  )}
                  <p className="text-[10px] text-slate-400">
                    {columnName
                      ? `按「列${columnName}」的值匹配文件夹中文件名`
                      : "选择列后，按该列值自动匹配材料文件"}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-500">Excel 起始行</label>
                    <input
                      type="number"
                      min={2}
                      value={rangeStart}
                      onChange={(e) =>
                        onRangeStartChange(Math.max(2, parseInt(e.target.value) || 2))
                      }
                      className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-500">Excel 结束行</label>
                    <input
                      type="number"
                      min={2}
                      value={rangeEnd}
                      onChange={(e) => onRangeEndChange(Math.max(2, parseInt(e.target.value) || 2))}
                      className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
                    />
                  </div>
                </div>
                <p className="text-[10px] text-slate-400">
                  行范围决定打印顺序（第1行是表头，从第2行开始）
                </p>
              </>
            )}
          </div>
        </AccordionSection>

        <AccordionSection
          title="打印设置"
          icon="🖨️"
          isOpen={openSections.print}
          onToggle={() => toggle("print")}
        >
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">打印机</label>
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

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-500">份数</label>
                <input
                  type="number"
                  min={1}
                  max={99}
                  value={printCopies}
                  onChange={(e) => onPrintCopiesChange(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-500">打印方式</label>
                <select
                  value={printMode}
                  onChange={(e) => onPrintModeChange(e.target.value as "single" | "double")}
                  className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all cursor-pointer"
                >
                  <option value="single">单面</option>
                  <option value="double">双面</option>
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">打印页码范围（材料页码）</label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <input
                    type="number"
                    min={1}
                    value={customStartPage}
                    onChange={(e) =>
                      onCustomStartPageChange(Math.max(1, parseInt(e.target.value) || 1))
                    }
                    placeholder="起始页"
                    className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
                  />
                </div>
                <div>
                  <input
                    type="number"
                    min={1}
                    value={customEndPage}
                    onChange={(e) =>
                      onCustomEndPageChange(Math.max(1, parseInt(e.target.value) || 1))
                    }
                    placeholder="结束页"
                    className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all"
                  />
                </div>
              </div>
              <p className="text-[10px] text-slate-400">留 1 表示打印全部页面</p>
            </div>
          </div>
        </AccordionSection>
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
