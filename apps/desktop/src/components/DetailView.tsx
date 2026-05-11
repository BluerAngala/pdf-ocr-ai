import { useState, useCallback, useRef } from "react";
import type { ModuleType, PreviewState, ProcessingResult, LogEntry } from "../types";
import ConfigPanel from "./ConfigPanel";
import PreviewPanel from "./PreviewPanel";
import LogsPanel from "./LogsPanel";

interface Props {
  moduleType: ModuleType;
  title: string;
  sampleRoot: string;
  excelFile: string;
  mockMode: boolean;
  forceOcr: boolean;
  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onMockModeChange: (v: boolean) => void;
  onForceOcrChange: (v: boolean) => void;
  onBack: () => void;
  onPreset: () => void;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onRun: () => void;
  running: boolean;
  previewState: PreviewState;
  phase: string;
  progressCurrent: number;
  progressTotal: number;
  progressMessage: string;
  result: ProcessingResult | null;
  onOpenReport: () => void;
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
  forceOcr,
  onSampleRootChange,
  onExcelFileChange,
  onMockModeChange,
  onForceOcrChange,
  onBack,
  onPreset,
  onSelectFolder,
  onSelectExcel,
  onRun,
  running,
  previewState,
  phase,
  progressCurrent,
  progressTotal,
  progressMessage,
  result,
  onOpenReport,
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
  const [logsHeight, setLogsHeight] = useState(140);
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
      const startY = e.clientY;
      const startHeight = logsHeight;
      const onMove = (ev: MouseEvent) => {
        const delta = startY - ev.clientY;
        const next = Math.min(400, Math.max(60, startHeight + delta));
        setLogsHeight(next);
      };
      const onUp = () => {
        setDraggingV(false);
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [logsHeight],
  );

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="h-10 bg-white border-b border-slate-200 flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="inline-flex items-center justify-center w-7 h-7 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
          <span className="text-sm font-semibold text-slate-800">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onRun}
            disabled={running}
            className="px-4 py-1.5 text-xs font-semibold text-white bg-blue-600 rounded-md hover:bg-blue-700 active:scale-[0.97] transition-all shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            开始处理
          </button>
        </div>
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
            forceOcr={forceOcr}
            onSampleRootChange={onSampleRootChange}
            onExcelFileChange={onExcelFileChange}
            onMockModeChange={onMockModeChange}
            onForceOcrChange={onForceOcrChange}
            onPreset={onPreset}
            onSelectFolder={onSelectFolder}
            onSelectExcel={onSelectExcel}
          />
        </div>

        <div
          className="w-1 shrink-0 cursor-col-resize hover:bg-blue-400/30 active:bg-blue-400/50 transition-colors rounded-full mx-1"
          onMouseDown={startHorizontalDrag}
        />

        <div ref={rightRef} className="flex-1 flex flex-col min-h-0 min-w-0" style={{ gap: 0 }}>
          <PreviewPanel
            moduleType={moduleType}
            previewState={previewState}
            phase={phase}
            progressCurrent={progressCurrent}
            progressTotal={progressTotal}
            progressMessage={progressMessage}
            result={result}
            onOpenReport={onOpenReport}
            onOpenOutput={onOpenOutput}
            onClearResult={onClearResult}
          />

          {logsExpanded && (
            <div
              className="h-1 shrink-0 cursor-row-resize hover:bg-blue-400/30 active:bg-blue-400/50 transition-colors rounded-full my-1"
              onMouseDown={startVerticalDrag}
            />
          )}

          <div style={{ height: logsExpanded ? logsHeight : 38 }} className="shrink-0">
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
