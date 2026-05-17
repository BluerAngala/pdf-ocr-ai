import { useState, useCallback, useRef, useEffect } from "react";
import type {
  ModuleType,
  LogEntry,
  PreviewState,
  ProcessingResult,
  ProgressParams,
  SystemStatus,
  DependenciesCheck,
  PrinterInfo,
  CompanyQueryItem,
  EnforcementStats,
  EnforcementExtracted,
  PrintFileItem,
} from "./types";
import { MODULE_CONFIG, PHASE_NAMES } from "./constants";
import { getPresetById, getPresets } from "./presets";
import { setupJsonRpcListeners, sendRequest, isTauri } from "./services/jsonrpc";
import { fetchSystemStatus } from "./services/system";
import { invoke } from "@tauri-apps/api/tauri";
import HomeView from "./components/HomeView";
import DetailView from "./components/DetailView";
import StatusBar from "./components/StatusBar";
import SystemStatusModal from "./components/SystemStatusModal";
import ChangelogModal from "./components/ChangelogModal";

export default function App() {
  const [currentView, setCurrentView] = useState<"home" | "detail">("home");
  const [currentModule, setCurrentModule] = useState<ModuleType>("non-litigation");
  const [sampleRoot, setSampleRoot] = useState("");
  const [excelFile, setExcelFile] = useState("");
  const [mockMode, setMockMode] = useState(false);
  const forceOcr = true;
  const [printerName, setPrinterName] = useState("");
  const [printCopies, setPrintCopies] = useState(1);
  const [printers, setPrinters] = useState<PrinterInfo[]>([]);
  const [rangeStart, setRangeStart] = useState(1);
  const [rangeEnd, setRangeEnd] = useState(99999);
  const [cacheTtlDays, setCacheTtlDays] = useState(7);
  const [liveCompanies, setLiveCompanies] = useState<CompanyQueryItem[]>([]);

  // Print module specific states
  const [printCompanyNameColumn, setPrintCompanyNameColumn] = useState("A");
  const [printMode, setPrintMode] = useState<"single" | "double">("single");
  const [printPageRange, setPrintPageRange] = useState<"all" | "custom">("all");
  const [printCustomStartPage, setPrintCustomStartPage] = useState(1);
  const [printCustomEndPage, setPrintCustomEndPage] = useState(1);

  const [previewState, setPreviewState] = useState<PreviewState>("empty");
  const [phase, setPhase] = useState("");
  const [progressCurrent, setProgressCurrent] = useState(0);
  const [progressTotal, setProgressTotal] = useState(0);
  const [progressFileCurrent, setProgressFileCurrent] = useState(0);
  const [progressFileTotal, setProgressFileTotal] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  const [result, setResult] = useState<ProcessingResult | null>(null);

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsExpanded, setLogsExpanded] = useState(true);

  const [running, setRunning] = useState(false);

  const [statusInfo, setStatusInfo] = useState<{
    status: SystemStatus | null;
    deps: DependenciesCheck | null;
  }>({ status: null, deps: null });
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [showChangelogModal, setShowChangelogModal] = useState(false);

  const logIdRef = useRef(0);
  const currentTaskIdRef = useRef<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null!);
  const pendingLogsRef = useRef<LogEntry[]>([]);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const MAX_LOGS = 500;

  const flushLogs = useCallback(() => {
    const pending = pendingLogsRef.current;
    if (pending.length === 0) return;
    pendingLogsRef.current = [];
    setLogs((prev) => {
      const merged = [...prev, ...pending];
      return merged.length > MAX_LOGS ? merged.slice(merged.length - MAX_LOGS) : merged;
    });
  }, []);

  const addLog = useCallback(
    (level: string, message: string) => {
      const time = new Date().toLocaleTimeString();
      pendingLogsRef.current.push({ id: ++logIdRef.current, level, message, time });
      if (!flushTimerRef.current) {
        flushTimerRef.current = setTimeout(() => {
          flushTimerRef.current = null;
          flushLogs();
        }, 100);
      }
    },
    [flushLogs],
  );

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  useEffect(() => {
    if (previewState === "result") {
      setLogsExpanded(false);
    }
  }, [previewState]);

  const handleProgress = useCallback(
    (params: ProgressParams) => {
      if (params.task_id !== currentTaskIdRef.current) return;
      setPreviewState("progress");
      setPhase(PHASE_NAMES[params.phase] || params.phase);
      setProgressCurrent(params.current);
      setProgressTotal(params.total);
      setProgressFileCurrent(params.file_current || 0);
      setProgressFileTotal(params.file_total || 0);
      setProgressMessage(params.message);
      if (currentModule === "company-query" && params.detail) {
        const detail = params.detail as { item?: CompanyQueryItem };
        if (detail.item) {
          setLiveCompanies((prev) => [...prev, detail.item!]);
        }
      }
    },
    [currentModule],
  );

  const handleProgressRef = useRef(handleProgress);
  const addLogRef = useRef(addLog);

  useEffect(() => {
    handleProgressRef.current = handleProgress;
  }, [handleProgress]);

  useEffect(() => {
    addLogRef.current = addLog;
  }, [addLog]);

  useEffect(() => {
    let unlistenFn: (() => void) | null = null;
    let mounted = true;
    setupJsonRpcListeners(
      (params) => handleProgressRef.current(params),
      (params) => addLogRef.current(params.level, params.message),
      (params) => {
        if (params.success && params.result) {
          setPreviewState("result");
          setResult(params.result as ProcessingResult);
        }
      },
    ).then((cleanup) => {
      if (mounted) {
        unlistenFn = cleanup;
      } else {
        cleanup();
      }
    });
    getPresets().then(() => {
      addLogRef.current("info", "应用已启动");
      sendRequest("ocr.warmup", {})
        .then((res) => {
          const r = res as { status?: string; duration_seconds?: number };
          if (r.status === "warm") {
            addLogRef.current("info", `OCR 引擎预热完成 (${r.duration_seconds}s)`);
          } else if (r.status === "already_warm") {
            addLogRef.current("debug", "OCR 引擎已预热");
          }
        })
        .catch(() => {
          addLogRef.current("warn", "OCR 引擎预热失败，首次识别可能较慢");
        });
    });
    return () => {
      mounted = false;
      if (unlistenFn) unlistenFn();
    };
  }, []);

  const navigateToModule = useCallback(
    (module: ModuleType) => {
      setCurrentModule(module);
      setCurrentView("detail");
      setPreviewState("empty");
      setResult(null);
      const config = MODULE_CONFIG[module];
      const preset = getPresetById(config.presetId);
      if (preset) {
        setSampleRoot(preset.sampleRoot);
        setExcelFile(preset.excelPath);
        setMockMode(preset.mode === "mock");
        addLog("info", `已加载预设: ${preset.name}`);
      }
      if (module === "print") {
        sendRequest("print.list_printers", {})
          .then((res) => {
            const result = res as { printers?: PrinterInfo[] };
            const list: PrinterInfo[] = result.printers || [];
            setPrinters(list);
            const defaultPrinter = list.find((p) => p.is_default);
            if (defaultPrinter) setPrinterName(defaultPrinter.name);
            else if (list.length > 0) setPrinterName(list[0].name);
          })
          .catch(() => addLog("warn", "获取打印机列表失败"));
      }
      addLog("info", `切换到模块: ${config.title}`);
    },
    [addLog],
  );

  const navigateHome = useCallback(() => {
    setCurrentView("home");
  }, []);

  const clearResult = useCallback(() => {
    setPreviewState("empty");
    setResult(null);
  }, []);

  const loadPreset = useCallback(() => {
    const config = MODULE_CONFIG[currentModule];
    const preset = getPresetById(config.presetId);
    if (preset) {
      setSampleRoot(preset.sampleRoot);
      setExcelFile(preset.excelPath);
      setMockMode(preset.mode === "mock");
      addLog("info", `已加载预设: ${preset.name}`);
    }
  }, [currentModule, addLog]);

  const selectFolder = useCallback(async () => {
    try {
      const result = (await invoke("select_folder")) as string | null;
      if (result) setSampleRoot(result);
    } catch {
      addLog("error", "选择文件夹失败");
    }
  }, [addLog]);

  const selectExcel = useCallback(async () => {
    try {
      const result = (await invoke("select_files", { multiple: false })) as string[] | null;
      if (result && result.length > 0) setExcelFile(result[0]);
    } catch {
      addLog("error", "选择文件失败");
    }
  }, [addLog]);

  const loadCache = useCallback(async () => {
    if (!excelFile) return;
    try {
      const rawResult = (await sendRequest("company_query.load_cache", {
        excel_path: excelFile,
        cache_ttl_days: cacheTtlDays,
      })) as { error?: string; companies?: CompanyQueryItem[] };
      if (rawResult.error) {
        addLog("error", `后端错误: ${rawResult.error}`);
        return;
      }
      const companies = rawResult.companies || [];
      if (companies.length === 0) {
        addLog("info", "暂无缓存记录，请先执行一次查询");
        return;
      }
      const stats = {
        total: companies.length,
        success_count: companies.filter((c) => c.status === "success").length,
        warning_count: companies.filter((c) => c.status === "warning").length,
        fail_count: companies.filter((c) => c.status === "failed").length,
      };
      setResult({
        companies,
        company_stats: stats,
        output_excel_path: "",
      });
      setPreviewState("result");
      addLog("info", `已加载 ${companies.length} 条缓存记录`);
    } catch (e) {
      const err = e as Error;
      addLog("error", `加载缓存记录失败: ${err?.message || e}`);
    }
  }, [excelFile, cacheTtlDays, addLog]);

  const clearCache = useCallback(async () => {
    if (!excelFile) return;
    try {
      const rawResult = (await sendRequest("company_query.clear_cache", {
        excel_path: excelFile,
      })) as { error?: string };
      if (rawResult.error) {
        addLog("error", `后端错误: ${rawResult.error}`);
        return;
      }
      addLog("info", "缓存已清除");
      setResult(null);
      setPreviewState("empty");
    } catch (e) {
      const err = e as Error;
      addLog("error", `清除缓存失败: ${err?.message || e}`);
    }
  }, [excelFile, addLog]);

  const cancelProcessing = useCallback(async () => {
    const taskId = currentTaskIdRef.current;
    if (!taskId) return;
    try {
      await sendRequest("task.cancel", { task_id: taskId });
      addLog("warn", "已发送取消请求...");
    } catch {
      addLog("error", "取消请求失败");
    }
  }, [addLog]);

  const startProcessing = useCallback(async () => {
    if (!sampleRoot) {
      alert("请选择样本材料文件夹");
      return;
    }
    if (!excelFile) {
      alert("请选择台账 Excel 文件");
      return;
    }

    const taskId = `${currentModule}-${Date.now()}`;
    currentTaskIdRef.current = taskId;
    flushLogs();
    setRunning(true);
    setLogsExpanded(true);
    setPreviewState("progress");
    setResult(null);
    setLiveCompanies([]);
    addLog("info", `开始${MODULE_CONFIG[currentModule].title}处理...`);

    try {
      let res: ProcessingResult = {} as ProcessingResult;
      if (currentModule === "non-litigation") {
        const rawResult = await sendRequest("non_litigation.process", {
          preset_id: null,
          sample_root: sampleRoot || null,
          excel_path: excelFile || null,
          mode: "real_ocr",
          force: false,
          task_id: taskId,
        });
        res = rawResult as ProcessingResult;
      } else if (currentModule === "enforcement") {
        const rawResult = (await sendRequest("enforcement.extract", {
          preset_id: null,
          input_dir: sampleRoot || null,
          excel_path: excelFile || null,
          force_ocr: forceOcr,
          mock_mode: mockMode,
        })) as {
          processed?: number;
          extracted?: EnforcementExtracted[];
          stats?: EnforcementStats;
          updated_excel_path?: string;
          output_dir?: string;
        };
        res = {
          processed: rawResult.processed || 0,
          extracted: rawResult.extracted || [],
          enforcement_stats: rawResult.stats,
          updated_excel_path: rawResult.updated_excel_path || "",
          html_report_path: rawResult.updated_excel_path || undefined,
          summary: {
            created_count: rawResult.processed || 0,
            result_root: rawResult.output_dir || undefined,
          },
        };
      } else if (currentModule === "company-query") {
        if (!excelFile) {
          alert("请选择企业信息数据 Excel 文件");
          setRunning(false);
          setPreviewState("empty");
          return;
        }
        const rawResult = (await sendRequest("company_query.process", {
          excel_path: excelFile,
          range_start: rangeStart,
          range_end: rangeEnd,
          cache_ttl_days: cacheTtlDays,
          task_id: taskId,
        })) as {
          companies?: CompanyQueryItem[];
          total?: number;
          success_count?: number;
          warning_count?: number;
          fail_count?: number;
          output_excel_path?: string;
        };
        res = {
          companies: rawResult.companies || [],
          company_stats:
            rawResult.total !== undefined
              ? {
                  total: rawResult.total,
                  success_count: rawResult.success_count || 0,
                  warning_count: rawResult.warning_count || 0,
                  fail_count: rawResult.fail_count || 0,
                }
              : undefined,
          output_excel_path: rawResult.output_excel_path || "",
          summary: { result_root: rawResult.output_excel_path || undefined },
        };
      } else if (currentModule === "print") {
        if (!sampleRoot) {
          alert("请选择打印文件夹");
          setRunning(false);
          setPreviewState("empty");
          return;
        }
        const rawResult = (await sendRequest("print.process", {
          folder_path: sampleRoot,
          excel_path: excelFile || undefined,
          range_start: excelFile ? rangeStart : undefined,
          range_end: excelFile ? rangeEnd : undefined,
          company_name_column: excelFile ? printCompanyNameColumn : undefined,
          printer_name: printerName,
          copies: printCopies,
          print_mode: printMode,
          page_range: printPageRange,
          custom_start_page: printPageRange === "custom" ? printCustomStartPage : undefined,
          custom_end_page: printPageRange === "custom" ? printCustomEndPage : undefined,
          task_id: taskId,
        })) as {
          files?: PrintFileItem[];
          total_files?: number;
          printed?: number;
          failed?: number;
          printer_used?: string;
        };
        res = {
          print_files: rawResult.files || [],
          print_stats:
            rawResult.total_files !== undefined
              ? {
                  total_files: rawResult.total_files,
                  printed: rawResult.printed || 0,
                  failed: rawResult.failed || 0,
                }
              : undefined,
          printer_used: rawResult.printer_used || "",
          summary: { result_root: sampleRoot },
        };
      }
      setPreviewState("result");
      setResult(res);
      addLog("info", "处理完成！");
    } catch (err) {
      const error = err as Error | string;
      const msg = typeof error === "string" ? error : (error as Error)?.message || String(error);
      addLog("error", `处理失败: ${msg}`);
      alert(`处理失败: ${msg}`);
      setPreviewState("empty");
    } finally {
      setRunning(false);
    }
  }, [
    currentModule,
    sampleRoot,
    excelFile,
    mockMode,
    forceOcr,
    printerName,
    printCopies,
    rangeStart,
    rangeEnd,
    cacheTtlDays,
    addLog,
    flushLogs,
    printCompanyNameColumn,
    printMode,
    printPageRange,
    printCustomStartPage,
    printCustomEndPage,
  ]);

  const openReport = useCallback(async () => {
    const path =
      currentModule === "company-query"
        ? result?.output_excel_path
        : result?.html_report_path || result?.summary?.result_root;
    if (!path) {
      alert("报告尚未生成");
      return;
    }
    try {
      if (isTauri()) await invoke("open_path", { path });
      else alert(`报告路径: ${path}`);
    } catch (err) {
      addLog("error", `打开报告失败: ${err}`);
    }
  }, [result, currentModule, addLog]);

  const openOutput = useCallback(async () => {
    const path =
      currentModule === "company-query" ? result?.output_excel_path : result?.summary?.result_root;
    if (!path) {
      alert("输出尚未生成");
      return;
    }
    try {
      if (isTauri()) await invoke("open_path", { path });
      else alert(`输出路径: ${path}`);
    } catch (err) {
      addLog("error", `打开输出失败: ${err}`);
    }
  }, [result, currentModule, addLog]);

  const copyLogs = useCallback(() => {
    if (logs.length === 0) {
      addLog("warn", "没有日志可复制");
      return;
    }
    const text = logs.map((l) => `${l.time} [${l.level.toUpperCase()}] ${l.message}`).join("\n");
    navigator.clipboard
      .writeText(text)
      .then(() => addLog("info", "日志已复制到剪贴板"))
      .catch(() => addLog("error", "复制日志失败"));
  }, [logs, addLog]);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const loadStatus = useCallback(async () => {
    const info = await fetchSystemStatus();
    setStatusInfo(info);
  }, []);

  const openStatusModal = useCallback(() => {
    loadStatus();
    setShowStatusModal(true);
  }, [loadStatus]);

  useEffect(() => {
    loadStatus();
    const timer = setInterval(loadStatus, 30000);
    return () => clearInterval(timer);
  }, [loadStatus]);

  const moduleTitle = MODULE_CONFIG[currentModule]?.title || "";

  return (
    <>
      {currentView === "home" ? (
        <HomeView
          onNavigate={navigateToModule}
          onOpenChangelog={() => setShowChangelogModal(true)}
        />
      ) : (
        <DetailView
          moduleType={currentModule}
          title={moduleTitle}
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          mockMode={mockMode}
          onSampleRootChange={setSampleRoot}
          onExcelFileChange={setExcelFile}
          onMockModeChange={setMockMode}
          printerName={printerName}
          printCopies={printCopies}
          printers={printers}
          onPrinterNameChange={setPrinterName}
          onPrintCopiesChange={setPrintCopies}
          onBack={navigateHome}
          onPreset={loadPreset}
          onSelectFolder={selectFolder}
          onSelectExcel={selectExcel}
          onRun={startProcessing}
          onCancel={cancelProcessing}
          onLoadCache={loadCache}
          onClearCache={clearCache}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          onRangeStartChange={setRangeStart}
          onRangeEndChange={setRangeEnd}
          cacheTtlDays={cacheTtlDays}
          onCacheTtlDaysChange={setCacheTtlDays}
          printCompanyNameColumn={printCompanyNameColumn}
          onPrintCompanyNameColumnChange={setPrintCompanyNameColumn}
          printMode={printMode}
          onPrintModeChange={setPrintMode}
          printPageRange={printPageRange}
          onPrintPageRangeChange={setPrintPageRange}
          printCustomStartPage={printCustomStartPage}
          onPrintCustomStartPageChange={setPrintCustomStartPage}
          printCustomEndPage={printCustomEndPage}
          onPrintCustomEndPageChange={setPrintCustomEndPage}
          running={running}
          previewState={previewState}
          phase={phase}
          progressCurrent={progressCurrent}
          progressTotal={progressTotal}
          progressFileCurrent={progressFileCurrent}
          progressFileTotal={progressFileTotal}
          progressMessage={progressMessage}
          result={result}
          liveCompanies={liveCompanies}
          onOpenReport={openReport}
          onOpenOutput={openOutput}
          onClearResult={clearResult}
          logs={logs}
          logsExpanded={logsExpanded}
          onToggleLogs={() => setLogsExpanded((v) => !v)}
          onCopyLogs={copyLogs}
          onClearLogs={clearLogs}
          logsEndRef={logsEndRef}
        />
      )}
      <StatusBar statusInfo={statusInfo} onClick={openStatusModal} />
      {showStatusModal && (
        <SystemStatusModal statusInfo={statusInfo} onClose={() => setShowStatusModal(false)} />
      )}
      {showChangelogModal && <ChangelogModal onClose={() => setShowChangelogModal(false)} />}
    </>
  );
}
