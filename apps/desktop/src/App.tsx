import { useState, useCallback, useRef, useEffect, useMemo } from "react";
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
  PrintExcelColumn,
  PrintTaskStatus,
} from "./types";
import { MODULE_CONFIG, PHASE_NAMES } from "./constants";
import { getPresetById, getPresets } from "./presets";
import { setupJsonRpcListeners, sendRequest, isTauri } from "./services/jsonrpc";
import { fetchSystemStatus, setupPoppler } from "./services/system";
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
  const [outputDir, setOutputDir] = useState("");
  const [mockMode, setMockMode] = useState(false);
  const forceOcr = true;
  const [printerName, setPrinterName] = useState("");
  const [printCopies, setPrintCopies] = useState(1);
  const [printers, setPrinters] = useState<PrinterInfo[]>([]);
  const [rangeStart, setRangeStart] = useState(2);
  const [rangeEnd, setRangeEnd] = useState(0);
  const [cacheTtlDays, setCacheTtlDays] = useState(7);
  const [liveCompanies, setLiveCompanies] = useState<CompanyQueryItem[]>([]);

  // Print module specific states
  const [printCompanyNameColumn, setPrintCompanyNameColumn] = useState("");
  const [printMode, setPrintMode] = useState<"single" | "double">("single");
  const [printCustomStartPage, setPrintCustomStartPage] = useState(0);
  const [printCustomEndPage, setPrintCustomEndPage] = useState(0);
  const [printExcelColumns, setPrintExcelColumns] = useState<PrintExcelColumn[]>([]);
  const [printTaskStatus, setPrintTaskStatus] = useState<PrintTaskStatus | null>(null);
  const [selectedOrders, setSelectedOrders] = useState<Set<number>>(new Set());
  const autoPreviewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [previewState, setPreviewState] = useState<PreviewState>("empty");
  const [phase, setPhase] = useState("");
  const [progressCurrent, setProgressCurrent] = useState(0);
  const [progressTotal, setProgressTotal] = useState(0);
  const [progressFileCurrent, setProgressFileCurrent] = useState(0);
  const [progressFileTotal, setProgressFileTotal] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  const [result, setResult] = useState<ProcessingResult | null>(null);

  const [logsByModule, setLogsByModule] = useState<Record<string, LogEntry[]>>({});
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
  const pendingLogsRef = useRef<{ module: string; entry: LogEntry }[]>([]);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const MAX_LOGS = 500;

  const flushLogs = useCallback(() => {
    const pending = pendingLogsRef.current;
    if (pending.length === 0) return;
    pendingLogsRef.current = [];
    setLogsByModule((prev) => {
      const next = { ...prev };
      for (const { module, entry } of pending) {
        const arr = next[module] ? [...next[module], entry] : [entry];
        next[module] = arr.length > MAX_LOGS ? arr.slice(arr.length - MAX_LOGS) : arr;
      }
      return next;
    });
  }, []);

  const addLog = useCallback(
    (level: string, message: string) => {
      const time = new Date().toLocaleTimeString();
      const entry = { id: ++logIdRef.current, level, message, time };
      pendingLogsRef.current.push({ module: currentModule, entry });
      if (!flushTimerRef.current) {
        flushTimerRef.current = setTimeout(() => {
          flushTimerRef.current = null;
          flushLogs();
        }, 100);
      }
    },
    [currentModule, flushLogs],
  );

  const logs = useMemo(() => logsByModule[currentModule] || [], [logsByModule, currentModule]);

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

  const runningRef = useRef(false);
  useEffect(() => {
    runningRef.current = running;
  }, [running]);

  const autoPreviewPrint = useCallback(async () => {
    if (runningRef.current || !sampleRoot) return;
    if (excelFile && !printCompanyNameColumn) return;
    try {
      const rawResult = (await sendRequest("print.start", {
        folder_path: sampleRoot,
        excel_path: excelFile || undefined,
        column_name: printCompanyNameColumn || undefined,
        range_start: excelFile ? rangeStart : undefined,
        range_end: excelFile ? rangeEnd : undefined,
        printer_name: printerName,
        dry_run: true,
        task_id: `preview-${Date.now()}`,
      })) as {
        task_id?: string;
        dry_run?: boolean;
        total_jobs?: number;
        submitted?: number;
        failed?: number;
        printer_used?: string;
        errors?: { company: string; error: string }[];
        match_results?: {
          order: number;
          company: string;
          row: number;
          files: { name: string; path: string }[];
          status: "matched" | "no_match";
        }[];
      };
      const mr = rawResult.match_results || [];
      setSelectedOrders(new Set(mr.map((m) => m.order)));
      setPrintTaskStatus({
        task_id: rawResult.task_id || "",
        status: "completed",
        total_jobs: rawResult.total_jobs || 0,
        completed_jobs: rawResult.submitted || 0,
        failed_jobs: rawResult.failed || 0,
        current_file: "",
        current_company: "",
        printer_name: rawResult.printer_used || printerName,
        started_at: null,
        finished_at: null,
        error_count: (rawResult.errors || []).length,
      });
      setResult({
        print_stats: rawResult.total_jobs
          ? {
              total_jobs: rawResult.total_jobs,
              submitted: rawResult.submitted || 0,
              failed: rawResult.failed || 0,
            }
          : undefined,
        printer_used: rawResult.printer_used || "",
        print_dry_run: true,
        print_errors: rawResult.errors || [],
        print_match_results: mr,
        summary: { result_root: sampleRoot },
      });
      setPreviewState("result");
    } catch {
      // auto-preview silently fails
    }
  }, [sampleRoot, excelFile, printCompanyNameColumn, rangeStart, rangeEnd, printerName]);

  useEffect(() => {
    if (currentModule !== "print" || !sampleRoot) return;
    if (excelFile && !printCompanyNameColumn) return;
    if (autoPreviewTimerRef.current) clearTimeout(autoPreviewTimerRef.current);
    autoPreviewTimerRef.current = setTimeout(() => {
      if (!runningRef.current) autoPreviewPrint();
    }, 800);
    return () => {
      if (autoPreviewTimerRef.current) clearTimeout(autoPreviewTimerRef.current);
    };
  }, [
    currentModule,
    sampleRoot,
    excelFile,
    printCompanyNameColumn,
    rangeStart,
    rangeEnd,
    printerName,
    autoPreviewPrint,
  ]);

  useEffect(() => {
    let unlistenFn: (() => void) | null = null;
    let mounted = true;
    let initialized = false;
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
      if (initialized) return;
      initialized = true;
      addLogRef.current("info", "应用已启动");
      sendRequest("ocr.clear_cache", {})
        .then(() => {
          addLogRef.current("debug", "OCR 缓存已清除");
        })
        .catch(() => {});
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
      setOutputDir("");
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

  const selectOutputDir = useCallback(async () => {
    try {
      const result = (await invoke("select_folder")) as string | null;
      if (result) setOutputDir(result);
    } catch {
      addLog("error", "选择输出文件夹失败");
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

  const loadExcelColumns = useCallback(async () => {
    if (!excelFile) return;
    try {
      const rawResult = (await sendRequest("print.excel_columns", {
        excel_path: excelFile,
      })) as { columns?: PrintExcelColumn[]; error?: string };
      if (rawResult.error) {
        addLog("error", `读取Excel列失败: ${rawResult.error}`);
        return;
      }
      const cols = rawResult.columns || [];
      setPrintExcelColumns(cols);
      addLog("info", `已读取 ${cols.length} 列`);
    } catch (e) {
      const err = e as Error;
      addLog("error", `读取Excel列失败: ${err?.message || e}`);
    }
  }, [excelFile, addLog]);

  const cancelPrintProcessing = useCallback(async () => {
    const taskId = currentTaskIdRef.current;
    if (!taskId) return;
    addLog("warn", `正在中止打印任务 ${taskId}...`);
    setRunning(false);
    currentTaskIdRef.current = null;
    try {
      await sendRequest("print.cancel", { task_id: taskId });
      addLog("warn", "打印已中止");
    } catch (err) {
      addLog("error", `中止打印请求发送失败: ${err}`);
    }
  }, [addLog]);

  const printOrders = useCallback(
    async (orders: number[]) => {
      if (running || !sampleRoot) return;
      const taskId = `print-${Date.now()}`;
      currentTaskIdRef.current = taskId;
      setRunning(true);
      setPreviewState("progress");
      setResult(null);
      addLog("info", `开始打印 ${orders.length} 条...`);
      try {
        const rawResult = (await sendRequest("print.start", {
          folder_path: sampleRoot,
          excel_path: excelFile || undefined,
          column_name: printCompanyNameColumn || undefined,
          range_start: excelFile ? rangeStart : undefined,
          range_end: excelFile && rangeEnd ? rangeEnd : undefined,
          printer_name: printerName,
          copies: printCopies,
          print_mode: printMode,
          page_start: printCustomStartPage || undefined,
          page_end: printCustomEndPage || undefined,
          dry_run: false,
          selected_orders: orders,
          task_id: taskId,
        })) as {
          task_id?: string;
          status?: string;
          dry_run?: boolean;
          total_jobs?: number;
          submitted?: number;
          failed?: number;
          printer_used?: string;
          errors?: { company: string; file?: string; error: string }[];
          match_results?: {
            order: number;
            company: string;
            row: number;
            files: { name: string; path: string }[];
            status: "matched" | "no_match";
          }[];
        };
        const printTaskId = rawResult.task_id || taskId;
        setPrintTaskStatus({
          task_id: printTaskId,
          status: "completed",
          total_jobs: rawResult.total_jobs || 0,
          completed_jobs: rawResult.submitted || 0,
          failed_jobs: rawResult.failed || 0,
          current_file: "",
          current_company: "",
          printer_name: rawResult.printer_used || printerName,
          started_at: null,
          finished_at: null,
          error_count: (rawResult.errors || []).length,
        });
        setResult((prev) => ({
          ...prev,
          print_stats: rawResult.total_jobs
            ? {
                total_jobs: rawResult.total_jobs,
                submitted: rawResult.submitted || 0,
                failed: rawResult.failed || 0,
              }
            : undefined,
          printer_used: rawResult.printer_used || "",
          print_dry_run: false,
          print_errors: rawResult.errors || [],
          print_match_results: prev?.print_match_results || rawResult.match_results || [],
          summary: { result_root: sampleRoot },
        }));
        setPreviewState("result");
        addLog("info", `打印完成: ${rawResult.submitted || 0} 成功, ${rawResult.failed || 0} 失败`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        addLog("error", `打印失败: ${msg}`);
      } finally {
        setRunning(false);
      }
    },
    [
      running,
      sampleRoot,
      excelFile,
      printCompanyNameColumn,
      rangeStart,
      rangeEnd,
      printerName,
      printCopies,
      printMode,
      printCustomStartPage,
      printCustomEndPage,
      addLog,
    ],
  );

  const pollPrintStatusRef = useRef<((taskId: string) => Promise<void>) | null>(null);
  const resultRef = useRef(result);
  useEffect(() => {
    resultRef.current = result;
  }, [result]);

  const pollPrintStatus = useCallback(async (taskId: string) => {
    try {
      const rawResult = (await sendRequest("print.status", {
        task_id: taskId,
      })) as PrintTaskStatus;
      setPrintTaskStatus(rawResult);
      if (rawResult.status === "running" || rawResult.status === "pending") {
        setTimeout(() => pollPrintStatusRef.current?.(taskId), 1000);
      }
    } catch {
      // ignore poll errors
    }
  }, []);

  useEffect(() => {
    pollPrintStatusRef.current = pollPrintStatus;
  }, [pollPrintStatus]);

  const cancelProcessing = useCallback(async () => {
    const taskId = currentTaskIdRef.current;
    if (!taskId) return;
    addLog("warn", `正在取消任务 ${taskId}...`);
    setRunning(false);
    setPreviewState("empty");
    currentTaskIdRef.current = null;
    try {
      await sendRequest("task.cancel", { task_id: taskId });
      addLog("warn", "任务已取消");
    } catch (err) {
      addLog("error", `取消请求发送失败: ${err}`);
    }
  }, [addLog]);

  const startProcessing = useCallback(async () => {
    if (!sampleRoot && currentModule !== "company-query") {
      alert("请选择样本材料文件夹");
      return;
    }
    if (!excelFile && currentModule !== "print") {
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
          preset_id: MODULE_CONFIG[currentModule]?.presetId || null,
          sample_root: sampleRoot || null,
          excel_path: excelFile || null,
          mode: "real_ocr",
          force: false,
          task_id: taskId,
          output_dir: outputDir || null,
        });
        res = rawResult as ProcessingResult;
      } else if (currentModule === "enforcement") {
        const rawResult = (await sendRequest("enforcement.extract", {
          preset_id: MODULE_CONFIG[currentModule]?.presetId || null,
          input_dir: sampleRoot || null,
          excel_path: excelFile || null,
          force_ocr: forceOcr,
          mock_mode: mockMode,
          task_id: taskId,
          output_dir: outputDir || null,
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
          preset_id: MODULE_CONFIG["company-query"]?.presetId || null,
          excel_path: excelFile,
          range_start: rangeStart,
          range_end: rangeEnd || undefined,
          cache_ttl_days: cacheTtlDays,
          task_id: taskId,
          output_dir: outputDir || null,
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
          alert("请选择材料文件夹");
          setRunning(false);
          setPreviewState("empty");
          return;
        }
        const rawResult = (await sendRequest("print.start", {
          folder_path: sampleRoot,
          excel_path: excelFile || undefined,
          range_start: excelFile ? rangeStart : undefined,
          range_end: excelFile && rangeEnd ? rangeEnd : undefined,
          column_name: printCompanyNameColumn || undefined,
          printer_name: printerName,
          copies: printCopies,
          print_mode: printMode,
          page_start: printCustomStartPage || undefined,
          page_end: printCustomEndPage || undefined,
          dry_run: false,
          selected_orders: selectedOrders.size > 0 ? Array.from(selectedOrders) : undefined,
          task_id: taskId,
        })) as {
          task_id?: string;
          status?: string;
          dry_run?: boolean;
          total_jobs?: number;
          submitted?: number;
          failed?: number;
          printer_used?: string;
          errors?: { company: string; file?: string; error: string }[];
          match_results?: {
            order: number;
            company: string;
            row: number;
            files: { name: string; path: string }[];
            status: "matched" | "no_match";
          }[];
        };
        const printTaskId = rawResult.task_id || taskId;
        setPrintTaskStatus({
          task_id: printTaskId,
          status:
            rawResult.status === "cancelled"
              ? "cancelled"
              : rawResult.status === "failed"
                ? "failed"
                : "completed",
          total_jobs: rawResult.total_jobs || 0,
          completed_jobs: rawResult.submitted || 0,
          failed_jobs: rawResult.failed || 0,
          current_file: "",
          current_company: "",
          printer_name: rawResult.printer_used || printerName,
          started_at: null,
          finished_at: null,
          error_count: (rawResult.errors || []).length,
        });
        res = {
          print_stats:
            rawResult.total_jobs !== undefined
              ? {
                  total_jobs: rawResult.total_jobs,
                  submitted: rawResult.submitted || 0,
                  failed: rawResult.failed || 0,
                }
              : undefined,
          printer_used: rawResult.printer_used || "",
          print_task_id: printTaskId,
          print_errors: rawResult.errors || [],
          print_match_results:
            resultRef.current?.print_match_results || rawResult.match_results || [],
          print_dry_run: rawResult.dry_run || false,
          summary: { result_root: sampleRoot },
        };
      }
      if (!currentTaskIdRef.current) {
        addLog("warn", "任务已取消，忽略后续结果");
        return;
      }
      setPreviewState("result");
      setResult(res);
      addLog("info", "处理完成！");
    } catch (err) {
      if (!currentTaskIdRef.current) {
        addLog("warn", "任务已取消，忽略后续响应");
        return;
      }
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
    outputDir,
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
    printCustomStartPage,
    printCustomEndPage,
    selectedOrders,
  ]);

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
    const currentLogs = logsByModule[currentModule] || [];
    if (currentLogs.length === 0) {
      addLog("warn", "没有日志可复制");
      return;
    }
    const text = currentLogs
      .map((l) => `${l.time} [${l.level.toUpperCase()}] ${l.message}`)
      .join("\n");
    navigator.clipboard
      .writeText(text)
      .then(() => addLog("info", "日志已复制到剪贴板"))
      .catch(() => addLog("error", "复制日志失败"));
  }, [logsByModule, currentModule, addLog]);

  const clearLogs = useCallback(() => {
    setLogsByModule((prev) => {
      const next = { ...prev };
      delete next[currentModule];
      return next;
    });
  }, [currentModule]);

  const loadStatus = useCallback(async () => {
    const info = await fetchSystemStatus();
    setStatusInfo(info);

    if (info.deps && !info.deps.all_ready) {
      const popplerDep = info.deps.dependencies.find((d) => d.name === "Poppler" && !d.installed);
      if (popplerDep) {
        addLog("info", "检测到 Poppler 未安装，正在自动安装...");
        try {
          const result = await setupPoppler();
          if (result.installed) {
            addLog("info", result.message);
            const updated = await fetchSystemStatus();
            setStatusInfo(updated);
          } else {
            addLog("error", result.message);
          }
        } catch (e) {
          addLog("error", `Poppler 自动安装失败: ${e}`);
        }
      }
    }
  }, [addLog]);

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
          outputDir={outputDir}
          onOutputDirChange={setOutputDir}
          printerName={printerName}
          printCopies={printCopies}
          printers={printers}
          onPrinterNameChange={setPrinterName}
          onPrintCopiesChange={setPrintCopies}
          onBack={navigateHome}
          onPreset={loadPreset}
          onSelectFolder={selectFolder}
          onSelectExcel={selectExcel}
          onSelectOutputDir={selectOutputDir}
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
          printCustomStartPage={printCustomStartPage}
          onPrintCustomStartPageChange={setPrintCustomStartPage}
          printCustomEndPage={printCustomEndPage}
          onPrintCustomEndPageChange={setPrintCustomEndPage}
          printExcelColumns={printExcelColumns}
          onLoadExcelColumns={loadExcelColumns}
          printTaskStatus={printTaskStatus}
          onCancelPrint={cancelPrintProcessing}
          selectedOrders={selectedOrders}
          onSelectedOrdersChange={setSelectedOrders}
          onPrintOrders={printOrders}
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
