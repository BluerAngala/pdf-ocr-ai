import { useState, useCallback, useRef } from "react";
import type {
  ModuleType,
  PreviewState,
  ProcessingResult,
  LogEntry,
  PrinterInfo,
  CompanyQueryItem,
  PrintExcelColumn,
  PrintTaskStatus,
} from "../types";
import ConfigPanel from "./ConfigPanel";
import PreviewPanel from "./PreviewPanel";
import LogsPanel from "./LogsPanel";

interface Props {
  moduleType: ModuleType;
  title: string;
  sampleRoot: string;
  excelFile: string;
  mockMode: boolean;
  outputDir: string;

  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onMockModeChange: (v: boolean) => void;
  onOutputDirChange: (v: string) => void;

  printerName: string;
  printCopies: number;
  printers: PrinterInfo[];
  onPrinterNameChange: (v: string) => void;
  onPrintCopiesChange: (v: number) => void;
  onBack: () => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onSelectOutputDir: () => void;
  onRun: () => void;
  onCancel: () => void;
  onLoadCache: () => void;
  onClearCache: () => void;
  rangeStart: number;
  rangeEnd: number;
  onRangeStartChange: (v: number) => void;
  onRangeEndChange: (v: number) => void;
  cacheTtlDays: number;
  onCacheTtlDaysChange: (v: number) => void;
  // Print module specific
  printCompanyNameColumn: string;
  onPrintCompanyNameColumnChange: (v: string) => void;
  printMode: "single" | "double";
  onPrintModeChange: (v: "single" | "double") => void;
  printCustomStartPage: number;
  onPrintCustomStartPageChange: (v: number) => void;
  printCustomEndPage: number;
  onPrintCustomEndPageChange: (v: number) => void;
  printExcelColumns: PrintExcelColumn[];
  onLoadExcelColumns: () => void;
  printTaskStatus: PrintTaskStatus | null;
  onCancelPrint: () => void;
  selectedOrders: Set<number>;
  onSelectedOrdersChange: (orders: Set<number>) => void;
  onPrintOrders: (orders: number[]) => void;
  running: boolean;
  cancelling: boolean;
  previewState: PreviewState;
  phase: string;
  progressCurrent: number;
  progressTotal: number;
  progressFileCurrent: number;
  progressFileTotal: number;
  progressMessage: string;
  result: ProcessingResult | null;
  liveCompanies: CompanyQueryItem[];
  onOpenOutput: () => void;
  onClearResult: () => void;
  logs: LogEntry[];
  logsExpanded: boolean;
  onToggleLogs: () => void;
  onCopyLogs: () => void;
  onClearLogs: () => void;
  logsEndRef: React.RefObject<HTMLDivElement | null>;
}

export default function DetailView({
  moduleType,
  title,
  sampleRoot,
  excelFile,
  mockMode,
  onSampleRootChange,
  onExcelFileChange,
  onMockModeChange,
  outputDir,
  onOutputDirChange,
  printerName,
  printCopies,
  printers,
  onPrinterNameChange,
  onPrintCopiesChange,
  onBack,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onSelectOutputDir,
  onRun,
  onCancel,
  onLoadCache,
  onClearCache,
  rangeStart,
  rangeEnd,
  onRangeStartChange,
  onRangeEndChange,
  cacheTtlDays,
  onCacheTtlDaysChange,
  // Print module specific
  printCompanyNameColumn,
  onPrintCompanyNameColumnChange,
  printMode,
  onPrintModeChange,
  printCustomStartPage,
  onPrintCustomStartPageChange,
  printCustomEndPage,
  onPrintCustomEndPageChange,
  printExcelColumns,
  onLoadExcelColumns,
  printTaskStatus,
  onCancelPrint,
  selectedOrders,
  onSelectedOrdersChange,
  onPrintOrders,
  running,
  cancelling,
  previewState,
  phase,
  progressCurrent,
  progressTotal,
  progressFileCurrent,
  progressFileTotal,
  progressMessage,
  result,
  liveCompanies,
  onOpenOutput,
  onClearResult,
  logs,
  logsExpanded,
  onToggleLogs,
  onCopyLogs,
  onClearLogs,
  logsEndRef,
}: Props) {
  const [leftWidth, setLeftWidth] = useState(280);
  const [logsRatio, setLogsRatio] = useState(0.5);
  const containerRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const [draggingH, setDraggingH] = useState(false);
  const [draggingV, setDraggingV] = useState(false);

  const startHorizontalDrag = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setDraggingH(true);
      const startX = e.clientX;
      const startWidth = leftWidth;
      const onMove = (ev: MouseEvent) => {
        const delta = ev.clientX - startX;
        const next = Math.min(500, Math.max(200, startWidth + delta));
        setLeftWidth(next);
      };
      const onUp = () => {
        setDraggingH(false);
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [leftWidth],
  );

  const startVerticalDrag = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setDraggingV(true);
      const containerRect = rightRef.current?.getBoundingClientRect();
      if (!containerRect) return;
      const totalHeight = containerRect.height;
      const startY = e.clientY;
      const startRatio = logsRatio;
      const onMove = (ev: MouseEvent) => {
        const delta = startY - ev.clientY;
        const ratioDelta = totalHeight > 0 ? delta / totalHeight : 0;
        const next = Math.min(0.8, Math.max(0.15, startRatio + ratioDelta));
        setLogsRatio(next);
      };
      const onUp = () => {
        setDraggingV(false);
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [logsRatio],
  );

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="h-12 bg-white border-b border-slate-200 flex items-center px-4 shrink-0">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 rounded-md text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer px-2.5 py-1.5 -ml-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
          <span className="text-sm font-medium">返回</span>
        </button>
        <span className="flex-1 text-center text-sm font-semibold text-slate-800">{title}</span>
        <div className="w-[72px]" />
      </div>

      <div
        ref={containerRef}
        className={`flex-1 flex min-h-0 p-4 overflow-hidden ${draggingH || draggingV ? "select-none" : ""}`}
        style={{ gap: 0 }}
      >
        <div style={{ width: leftWidth }} className="shrink-0">
          <ConfigPanel
            moduleType={moduleType}
            sampleRoot={sampleRoot}
            excelFile={excelFile}
            mockMode={mockMode}
            outputDir={outputDir}
            running={running}
            cancelling={cancelling}
            printerName={printerName}
            printCopies={printCopies}
            printers={printers}
            onSampleRootChange={onSampleRootChange}
            onExcelFileChange={onExcelFileChange}
            onMockModeChange={onMockModeChange}
            onOutputDirChange={onOutputDirChange}
            onPrinterNameChange={onPrinterNameChange}
            onPrintCopiesChange={onPrintCopiesChange}
            onPreset={onPreset}
            onSelectFolder={onSelectFolder}
            onSelectExcel={onSelectExcel}
            onSelectOutputDir={onSelectOutputDir}
            onRun={onRun}
            onCancel={onCancel}
            onLoadCache={onLoadCache}
            onClearCache={onClearCache}
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            onRangeStartChange={onRangeStartChange}
            onRangeEndChange={onRangeEndChange}
            cacheTtlDays={cacheTtlDays}
            onCacheTtlDaysChange={onCacheTtlDaysChange}
            printCompanyNameColumn={printCompanyNameColumn}
            onPrintCompanyNameColumnChange={onPrintCompanyNameColumnChange}
            printMode={printMode}
            onPrintModeChange={onPrintModeChange}
            printCustomStartPage={printCustomStartPage}
            onPrintCustomStartPageChange={onPrintCustomStartPageChange}
            printCustomEndPage={printCustomEndPage}
            onPrintCustomEndPageChange={onPrintCustomEndPageChange}
            printExcelColumns={printExcelColumns}
            onLoadExcelColumns={onLoadExcelColumns}
            selectedPrintCount={selectedOrders.size}
          />
        </div>

        <div
          className="w-1 shrink-0 cursor-col-resize hover:bg-blue-400/30 active:bg-blue-400/50 transition-colors rounded-full mx-1"
          onMouseDown={startHorizontalDrag}
        />

        <div ref={rightRef} className="flex-1 flex flex-col min-h-0 min-w-0" style={{ gap: 0 }}>
          <div
            style={{ flex: logsExpanded ? `${1 - logsRatio} 0 0` : "1 0 0" }}
            className="min-h-0 flex flex-col"
          >
            <PreviewPanel
              moduleType={moduleType}
              previewState={previewState}
              phase={phase}
              progressCurrent={progressCurrent}
              progressTotal={progressTotal}
              progressFileCurrent={progressFileCurrent}
              progressFileTotal={progressFileTotal}
              progressMessage={progressMessage}
              result={result}
              liveCompanies={liveCompanies}
              printTaskStatus={printTaskStatus}
              onOpenOutput={onOpenOutput}
              onClearResult={onClearResult}
              onCancelPrint={onCancelPrint}
              selectedOrders={selectedOrders}
              onSelectedOrdersChange={onSelectedOrdersChange}
              onPrintOrders={onPrintOrders}
            />
          </div>

          {logsExpanded && (
            <div
              className="h-1 shrink-0 cursor-row-resize hover:bg-blue-400/30 active:bg-blue-400/50 transition-colors rounded-full my-1"
              onMouseDown={startVerticalDrag}
            />
          )}

          <div
            style={{ flex: logsExpanded ? `${logsRatio} 0 0` : "0 0 38px" }}
            className={`${logsExpanded ? "min-h-0 flex flex-col" : "h-[38px] shrink-0"}`}
          >
            <LogsPanel
              logs={logs}
              expanded={logsExpanded}
              onToggle={onToggleLogs}
              onCopy={onCopyLogs}
              onClear={onClearLogs}
              logsEndRef={logsEndRef}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
