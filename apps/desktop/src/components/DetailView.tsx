import { useState, useCallback, useRef } from "react";
import { open } from "@tauri-apps/api/shell";
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

interface AccountInfo {
  status: string;
  userid: string;
  message: string;
  [key: string]: unknown;
}

const ACCOUNT_LABELS: Record<string, string> = {
  userid: "账号",
  message: "状态信息",
  userName: "用户名",
  usedTimes: "已用次数",
  remainingTimes: "剩余次数",
  totalLimit: "总次数",
  rechargeUrl: "充值链接",
};

const SKIP_KEYS = new Set(["status", "companyInfo", "balance_depleted", "rechargeUrl"]);

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
  ocrEngineReady: boolean;
  onLoadCache: () => void;
  onClearCache: () => void;
  onCheckAccount: () => Promise<AccountInfo>;
  onRecharge: (code: string) => Promise<{ success: boolean; message: string }>;
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
  printedOrders: Set<number>;
  printingOrders: Set<number>;
  running: boolean;
  cancelling: boolean;
  taskPaused: boolean;
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
  ocrEngineReady,
  onLoadCache,
  onClearCache,
  onCheckAccount,
  onRecharge,
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
  printedOrders,
  printingOrders,
  running,
  cancelling,
  taskPaused,
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

  const [accountInfo, setAccountInfo] = useState<AccountInfo | null>(null);
  const [checking, setChecking] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);
  const [redeemCode, setRedeemCode] = useState("");
  const [redeeming, setRedeeming] = useState(false);
  const [redeemMsg, setRedeemMsg] = useState("");

  const doCheckAccount = useCallback(async () => {
    setChecking(true);
    try {
      const result = await onCheckAccount();
      setAccountInfo(result);
    } catch (e) {
      setAccountInfo({ status: "error", userid: "", message: String(e) });
    } finally {
      setChecking(false);
    }
  }, [onCheckAccount]);

  const doRecharge = useCallback(async () => {
    if (!redeemCode.trim()) return;
    setRedeeming(true);
    setRedeemMsg("");
    try {
      const res = await onRecharge(redeemCode.trim());
      if (res.success) {
        setRedeemMsg("兑换成功！已充值 " + (res as { addTimes?: number }).addTimes + " 次");
        setRedeemCode("");
        doCheckAccount();
      } else {
        setRedeemMsg(res.message || "兑换失败");
      }
    } catch (e) {
      setRedeemMsg(String(e));
    } finally {
      setRedeeming(false);
    }
  }, [onRecharge, redeemCode, doCheckAccount]);

  const statusDot = accountInfo
    ? accountInfo.status === "ok"
      ? "bg-emerald-500"
      : accountInfo.status === "depleted"
        ? "bg-amber-500"
        : "bg-red-500"
    : "bg-slate-300";

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
        <div className="relative flex items-center w-[72px] justify-end">
          {moduleType === "company-query" && (
            <>
              <button
                onClick={() => {
                  if (accountInfo?.status === "depleted" && accountInfo.rechargeUrl) {
                    open(accountInfo.rechargeUrl as string);
                    return;
                  }
                  if (!accountInfo && !checking) doCheckAccount();
                  setShowAccount((v) => !v);
                }}
                className={`inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-1 rounded transition-colors cursor-pointer ${
                  accountInfo?.status === "depleted" && accountInfo.rechargeUrl
                    ? "text-amber-700 hover:text-amber-900 hover:bg-amber-50"
                    : "text-slate-500 hover:text-slate-700 hover:bg-slate-100"
                }`}
                title={
                  accountInfo?.status === "depleted" && accountInfo.rechargeUrl
                    ? "余额不足，点击充值"
                    : "API 账号信息"
                }
              >
                <span className={`inline-block w-1.5 h-1.5 rounded-full ${statusDot}`} />
                {accountInfo?.status === "depleted" && accountInfo.rechargeUrl ? "充值" : "账号"}
              </button>
              {showAccount && (
                <div
                  ref={accountRef}
                  className="absolute right-0 top-full mt-1 z-50 w-64 bg-white rounded-lg border border-slate-200 shadow-lg p-3 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-600">API 账号信息</span>
                    <button
                      onClick={() => setShowAccount(false)}
                      className="text-slate-400 hover:text-slate-600 cursor-pointer"
                    >
                      <svg
                        className="w-3.5 h-3.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>
                  {accountInfo && (
                    <div className="space-y-1">
                      {accountInfo?.rechargeUrl && (
                        <button
                          onClick={() => open(accountInfo.rechargeUrl as string)}
                          className="w-full h-8 rounded-md text-[11px] font-semibold text-white bg-amber-600 hover:bg-amber-700 transition-colors cursor-pointer"
                        >
                          充值
                        </button>
                      )}
                      <div className="space-y-1">
                        <div className="flex gap-1">
                          <input
                            type="text"
                            value={redeemCode}
                            onChange={(e) => {
                              setRedeemCode(e.target.value);
                              setRedeemMsg("");
                            }}
                            placeholder="输入兑换码"
                            className="flex-1 h-7 px-2 rounded-md text-[11px] border border-slate-200 bg-white focus:outline-none focus:border-emerald-400"
                            onKeyDown={(e) => {
                              if (e.key === "Enter") doRecharge();
                            }}
                          />
                          <button
                            onClick={doRecharge}
                            disabled={redeeming || !redeemCode.trim()}
                            className="h-7 px-3 rounded-md text-[11px] font-medium text-white bg-emerald-600 hover:bg-emerald-700 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            {redeeming ? "兑换中…" : "兑换"}
                          </button>
                        </div>
                        {redeemMsg && (
                          <p
                            className={`text-[10px] ${redeemMsg.startsWith("兑换成功") ? "text-emerald-600" : "text-red-500"}`}
                          >
                            {redeemMsg}
                          </p>
                        )}
                      </div>
                      {Object.entries(accountInfo)
                        .filter(
                          ([k]) =>
                            !SKIP_KEYS.has(k) && accountInfo[k] != null && accountInfo[k] !== "",
                        )
                        .map(([k, v]) => (
                          <div key={k} className="flex justify-between text-[11px]">
                            <span className="text-slate-400">{ACCOUNT_LABELS[k] || k}</span>
                            <span className="text-slate-700 font-medium truncate ml-2 max-w-[160px]">
                              {String(v)}
                            </span>
                          </div>
                        ))}
                    </div>
                  )}
                  {!accountInfo && !checking && (
                    <p className="text-[10px] text-slate-400 text-center py-1">
                      点击检测查看账号信息
                    </p>
                  )}
                  {checking && (
                    <p className="text-[10px] text-slate-400 text-center py-1 animate-pulse">
                      正在检测…
                    </p>
                  )}
                  <button
                    onClick={doCheckAccount}
                    disabled={checking}
                    className="w-full h-7 rounded-md text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {checking ? "检测中…" : "检测账号"}
                  </button>
                </div>
              )}
            </>
          )}
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
            outputDir={outputDir}
            running={running}
            cancelling={cancelling}
            taskPaused={taskPaused}
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
            ocrEngineReady={ocrEngineReady}
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
              sampleRoot={sampleRoot}
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
              printedOrders={printedOrders}
              printingOrders={printingOrders}
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
