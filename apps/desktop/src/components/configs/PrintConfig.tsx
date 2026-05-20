import { useState, useEffect } from "react";
import type { PrinterInfo, PrintExcelColumn } from "../../types";
import PathSelector from "../shared/PathSelector";
import ActionFooter from "../shared/ActionFooter";
import NumberCombo from "../shared/NumberCombo";

interface Props {
  sampleRoot: string;
  excelFile: string;
  printerName: string;
  printCopies: number;
  printers: PrinterInfo[];
  running: boolean;
  cancelling?: boolean;
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
  onCancel: () => void;
  onLoadExcelColumns: () => void;
  selectedPrintCount: number;
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
  cancelling = false,
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
  onCancel,
  onLoadExcelColumns,
  selectedPrintCount,
}: Props) {
  const [openSections, setOpenSections] = useState({ excel: true, print: true });
  const toggle = (s: keyof typeof openSections) => setOpenSections((p) => ({ ...p, [s]: !p[s] }));

  useEffect(() => {
    if (excelFile) {
      onLoadExcelColumns();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [excelFile]);

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
          <PathSelector
            label="材料文件夹"
            value={sampleRoot}
            onChange={onSampleRootChange}
            onSelect={onSelectFolder}
            placeholder="选择材料所在文件夹..."
            accent="slate"
            compact
          />
          <PathSelector
            label="台账 Excel"
            value={excelFile}
            onChange={onExcelFileChange}
            onSelect={onSelectExcel}
            placeholder="选择台账表格（可选）..."
            accent="slate"
            compact
          />

          {excelFile && (
            <>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-500">匹配字段</label>
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
                  <p className="text-[11px] text-slate-400 h-8 flex items-center">
                    正在读取列名...
                  </p>
                )}
                <p className="text-[10px] text-slate-400">
                  {columnName
                    ? `按「列${columnName}」的值匹配文件夹中文件名`
                    : "选择列后，按该列值自动匹配材料文件"}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <NumberCombo
                  label="Excel 起始行"
                  value={rangeStart}
                  onChange={onRangeStartChange}
                  min={2}
                  shortcuts={[2, 5, 10, 20]}
                />
                <NumberCombo
                  label="Excel 结束行"
                  value={rangeEnd}
                  onChange={onRangeEndChange}
                  min={0}
                  shortcuts={[5, 30, 50, 100, 200]}
                  placeholder="全部"
                />
              </div>
              <p className="text-[10px] text-slate-400">
                行范围决定打印顺序（第1行是表头，从第2行开始，结束行留空=全部）
              </p>
            </>
          )}
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
                <NumberCombo
                  label="起始页"
                  value={customStartPage}
                  onChange={onCustomStartPageChange}
                  min={0}
                  shortcuts={[1, 2, 3]}
                  placeholder="全部"
                />
                <NumberCombo
                  label="结束页"
                  value={customEndPage}
                  onChange={onCustomEndPageChange}
                  min={0}
                  shortcuts={[1, 2, 5, 10]}
                  placeholder="全部"
                />
              </div>
              <p className="text-[10px] text-slate-400">不填写则打印全部页面</p>
            </div>
          </div>
        </AccordionSection>
      </div>

      <ActionFooter
        running={running}
        cancelling={cancelling}
        onRun={onRun}
        onCancel={onCancel}
        runLabel={selectedPrintCount > 0 ? `开始打印 (${selectedPrintCount} 项)` : "开始打印"}
        runIcon={
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"
            />
          </svg>
        }
        accent="slate"
      />
    </div>
  );
}
