import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import type {
  ModuleType,
  LogEntry,
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
  PausedTaskSession,
  ModuleTaskUiState,
  PreviewState,
} from "./types";
import { MODULE_CONFIG, PHASE_NAMES } from "./constants";
import { createInitialModuleTaskState, resolveTaskModule } from "./moduleTaskState";
import { ensurePresetById, getPresetResolveErrors, invalidatePresetCache } from "./presets";
import { setupJsonRpcListeners, sendRequest, isTauri } from "./services/jsonrpc";
import { fetchSystemStatus, setupPoppler } from "./services/system";
import { invoke } from "@tauri-apps/api/tauri";
import { normalizePath } from "./services/paths";
import HomeView from "./components/HomeView";
import DetailView from "./components/DetailView";
import StatusBar from "./components/StatusBar";
import SystemStatusModal from "./components/SystemStatusModal";
import ChangelogModal from "./components/ChangelogModal";
import StartupOverlay from "./components/StartupOverlay";
import OcrWarmupBanner from "./components/OcrWarmupBanner";
import {
  runStartupWarmup,
  runBackgroundOcrWarmup,
  isProductionBundle,
  type StartupProgress,
} from "./services/startup";

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

  const [moduleTaskState, setModuleTaskState] = useState(createInitialModuleTaskState);

  // Print module specific states
  const [printCompanyNameColumn, setPrintCompanyNameColumn] = useState("");
  const [printMode, setPrintMode] = useState<"single" | "double">("single");
  const [printCustomStartPage, setPrintCustomStartPage] = useState(1);
  const [printCustomEndPage, setPrintCustomEndPage] = useState(0);
  const [printExcelColumns, setPrintExcelColumns] = useState<PrintExcelColumn[]>([]);
  const [printTaskStatus, setPrintTaskStatus] = useState<PrintTaskStatus | null>(null);
  const [selectedOrders, setSelectedOrders] = useState<Set<number>>(new Set());
  const [printedOrders, setPrintedOrders] = useState<Set<number>>(new Set());
  const [printingOrders, setPrintingOrders] = useState<Set<number>>(new Set());
  const autoPreviewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const justPrintedRef = useRef(false);

  const [logsByModule, setLogsByModule] = useState<Record<string, LogEntry[]>>({});
  const [logsExpanded, setLogsExpanded] = useState(true);

  const [statusInfo, setStatusInfo] = useState<{
    status: SystemStatus | null;
    deps: DependenciesCheck | null;
  }>({ status: null, deps: null });
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [showChangelogModal, setShowChangelogModal] = useState(false);
  const [appReady, setAppReady] = useState(false);
  const [ocrEngineReady, setOcrEngineReady] = useState(!isTauri());
  const [ocrWarmupDetail, setOcrWarmupDetail] = useState<string | undefined>();
  const [ocrWarmupError, setOcrWarmupError] = useState<string | undefined>();
  const [ocrGpuProbing, setOcrGpuProbing] = useState(false);
  const [startupProgress, setStartupProgress] = useState<StartupProgress>({
    phase: "waiting_backend",
    label: "正在启动…",
  });

  const logIdRef = useRef(0);
  const taskIdToModuleRef = useRef<Record<string, ModuleType>>({});
  const taskConfigRef = useRef<
    Record<string, { sampleRoot: string; excelFile: string; outputDir: string }>
  >({});
  const moduleTaskStateRef = useRef(moduleTaskState);
  const pausedSessionsRef = useRef<Partial<Record<ModuleType, PausedTaskSession>>>({});

  const currentTask = moduleTaskState[currentModule];

  useEffect(() => {
    moduleTaskStateRef.current = moduleTaskState;
  }, [moduleTaskState]);

  const patchModuleTask = useCallback(
    (
      module: ModuleType,
      patch: Partial<ModuleTaskUiState> | ((prev: ModuleTaskUiState) => Partial<ModuleTaskUiState>),
    ) => {
      setModuleTaskState((prev) => {
        const cur = prev[module];
        const nextPatch = typeof patch === "function" ? patch(cur) : patch;
        return { ...prev, [module]: { ...cur, ...nextPatch } };
      });
    },
    [],
  );
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
    (level: string, message: string, module?: ModuleType) => {
      const time = new Date().toLocaleTimeString();
      const entry = { id: ++logIdRef.current, level, message, time };
      pendingLogsRef.current.push({ module: module ?? currentModule, entry });
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

  const clearPausedSession = useCallback((module: ModuleType) => {
    delete pausedSessionsRef.current[module];
  }, []);

  const savePausedSession = useCallback(
    (module: ModuleType) => {
      const task = moduleTaskStateRef.current[module];
      if (!task.taskId) return;
      const cfg = taskConfigRef.current[task.taskId];
      pausedSessionsRef.current[module] = {
        taskId: task.taskId,
        phase: task.phase,
        progressCurrent: task.progressCurrent,
        progressTotal: task.progressTotal,
        progressFileCurrent: task.progressFileCurrent,
        progressFileTotal: task.progressFileTotal,
        progressMessage: task.progressMessage,
        sampleRoot: cfg?.sampleRoot ?? sampleRoot,
        excelFile: cfg?.excelFile ?? excelFile,
        outputDir: cfg?.outputDir ?? outputDir,
      };
    },
    [sampleRoot, excelFile, outputDir],
  );

  const restorePausedSession = useCallback(
    (module: ModuleType, session: PausedTaskSession) => {
      taskIdToModuleRef.current[session.taskId] = module;
      patchModuleTask(module, {
        taskId: session.taskId,
        previewState: "paused",
        phase: session.phase,
        progressCurrent: session.progressCurrent,
        progressTotal: session.progressTotal,
        progressFileCurrent: session.progressFileCurrent,
        progressFileTotal: session.progressFileTotal,
        progressMessage: session.progressMessage,
        result: null,
        running: false,
        cancelling: false,
      });
      setSampleRoot(session.sampleRoot);
      setExcelFile(session.excelFile);
      setOutputDir(session.outputDir);
    },
    [patchModuleTask],
  );

  const resetTaskState = useCallback(
    (module: ModuleType = currentModule) => {
      patchModuleTask(module, {
        running: false,
        cancelling: false,
        taskId: null,
        previewState: "empty",
      });
      clearPausedSession(module);
    },
    [currentModule, clearPausedSession, patchModuleTask],
  );

  const pauseTaskState = useCallback(
    (module: ModuleType) => {
      patchModuleTask(module, {
        running: false,
        cancelling: false,
        previewState: "paused",
      });
      savePausedSession(module);
    },
    [savePausedSession, patchModuleTask],
  );

  useEffect(() => {
    if (currentTask.previewState === "result") {
      setLogsExpanded(false);
    }
  }, [currentTask.previewState]);

  const handleProgress = useCallback(
    (params: ProgressParams) => {
      const module = resolveTaskModule(params.task_id, taskIdToModuleRef.current);
      if (!module) return;
      const task = moduleTaskStateRef.current[module];
      if (params.task_id !== task.taskId) return;
      patchModuleTask(module, (cur) => ({
        previewState:
          cur.previewState === "cancelling" || cur.previewState === "paused"
            ? cur.previewState
            : "progress",
        phase: PHASE_NAMES[params.phase] || params.phase,
        progressCurrent: params.current,
        progressTotal: params.total,
        progressFileCurrent: params.file_current || 0,
        progressFileTotal: params.file_total || 0,
        progressMessage: params.message,
        ...(module === "company-query" && params.detail
          ? {
              liveCompanies: (() => {
                const detail = params.detail as { item?: CompanyQueryItem };
                return detail.item ? [...cur.liveCompanies, detail.item] : cur.liveCompanies;
              })(),
            }
          : {}),
      }));
    },
    [patchModuleTask],
  );

  const handleProgressRef = useRef(handleProgress);
  const addLogRef = useRef(addLog);
  const resetTaskStateRef = useRef(resetTaskState);
  const pauseTaskStateRef = useRef(pauseTaskState);

  useEffect(() => {
    handleProgressRef.current = handleProgress;
  }, [handleProgress]);

  useEffect(() => {
    addLogRef.current = addLog;
  }, [addLog]);

  useEffect(() => {
    resetTaskStateRef.current = resetTaskState;
  }, [resetTaskState]);

  useEffect(() => {
    pauseTaskStateRef.current = pauseTaskState;
  }, [pauseTaskState]);

  const runningRef = useRef(false);
  useEffect(() => {
    runningRef.current = moduleTaskState.print.running;
  }, [moduleTaskState.print.running]);

  const autoPreviewPrint = useCallback(async () => {
    if (moduleTaskStateRef.current.print.running || !sampleRoot) return;
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
      patchModuleTask("print", {
        result: {
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
        },
        previewState: "result",
      });
    } catch {
      // auto-preview silently fails
    }
  }, [
    sampleRoot,
    excelFile,
    printCompanyNameColumn,
    rangeStart,
    rangeEnd,
    printerName,
    patchModuleTask,
  ]);

  useEffect(() => {
    if (currentModule !== "print" || !sampleRoot) return;
    if (excelFile && !printCompanyNameColumn) return;
    if (justPrintedRef.current) return; // 刚刚打印过，不触发自动预览
    if (autoPreviewTimerRef.current) clearTimeout(autoPreviewTimerRef.current);
    autoPreviewTimerRef.current = setTimeout(() => {
      if (!runningRef.current && !justPrintedRef.current) autoPreviewPrint();
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
          const module = resolveTaskModule(params.task_id, taskIdToModuleRef.current);
          if (module) {
            patchModuleTask(module, {
              previewState: "result",
              result: params.result as ProcessingResult,
              running: false,
              cancelling: false,
            });
          }
        }
      },
      (params) => {
        const module = resolveTaskModule(params.task_id, taskIdToModuleRef.current);
        if (!module) return;
        const task = moduleTaskStateRef.current[module];
        if (params.task_id !== task.taskId) return;
        pauseTaskStateRef.current(module);
        addLogRef.current("warn", `任务 ${params.task_id} 已暂停，可点击继续任务`, module);
      },
    ).then((cleanup) => {
      if (mounted) {
        unlistenFn = cleanup;
      } else {
        cleanup();
      }
    });
    const bootstrap = async () => {
      if (initialized) return;
      initialized = true;
      addLogRef.current("info", "应用已启动");
      if (isTauri()) {
        setAppReady(true);
      }
      try {
        const bundled = isTauri() && (await isProductionBundle());
        await runStartupWarmup((p) => {
          setStartupProgress(p);
          if (p.phase === "ready") {
            setAppReady(true);
          }
          if (p.phase === "error") {
            addLogRef.current("error", p.error ?? p.label);
          }
          if (p.phase === "waiting_backend" && p.detail) {
            addLogRef.current("debug", p.detail);
          }
        });
        if (bundled) {
          addLogRef.current("info", "界面已打开，服务在后台连接");
        } else {
          addLogRef.current("info", "后端已就绪，界面可用");
        }
        let ocrFastReady = false;
        void runBackgroundOcrWarmup(
          (p) => {
            setOcrWarmupDetail(p.detail);
            if (p.detail) {
              addLogRef.current("debug", p.detail, "non-litigation");
            }
          },
          () => {
            ocrFastReady = true;
            setOcrEngineReady(true);
            setOcrGpuProbing(true);
            addLogRef.current("info", "OCR 基础引擎已就绪，可先开始处理（GPU 探测进行中）");
          },
        ).then((result) => {
          setOcrGpuProbing(false);
          if (result.ok) {
            setOcrEngineReady(true);
            setOcrWarmupError(undefined);
            addLogRef.current("info", "OCR 引擎预热完成");
          } else if (!ocrFastReady) {
            setOcrWarmupError(result.error);
            addLogRef.current(
              "warn",
              `OCR 预热未完成: ${result.error ?? "未知错误"}`,
              "non-litigation",
            );
          } else {
            addLogRef.current(
              "warn",
              `GPU 完整探测未完成，将使用快速模式: ${result.error ?? "未知错误"}`,
              "non-litigation",
            );
          }
          setOcrWarmupDetail(undefined);
        });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setStartupProgress({ phase: "error", label: "启动失败", error: msg });
        addLogRef.current("error", `启动失败: ${msg}`);
      }
    };
    void bootstrap();
    return () => {
      mounted = false;
      if (unlistenFn) unlistenFn();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyModulePreset = useCallback(
    async (module: ModuleType, logModule?: ModuleType) => {
      const config = MODULE_CONFIG[module];
      const preset = await ensurePresetById(config.presetId);
      if (preset?.sampleRoot || preset?.excelPath) {
        if (preset.sampleRoot) setSampleRoot(preset.sampleRoot);
        if (preset.excelPath) setExcelFile(preset.excelPath);
        setMockMode(preset.mode === "mock");
        addLog("info", `已加载预设: ${preset.name}`, logModule ?? module);
        return true;
      }
      if (module === "company-query") {
        setExcelFile("");
        setSampleRoot("");
      }
      const presetErrors = await getPresetResolveErrors();
      const err = presetErrors.find((e) => e.id === config.presetId);
      if (err) {
        addLog(
          "warn",
          `预设「${config.presetId}」未找到样本：${err.error}（安装包需含对应 sample-data，或手动选择文件夹）`,
          logModule ?? module,
        );
      } else {
        addLog(
          "warn",
          "预设路径未就绪，请点击「测试示例」或手动选择 Excel/样本文件",
          logModule ?? module,
        );
      }
      return false;
    },
    [addLog],
  );

  const navigateToModule = useCallback(
    async (module: ModuleType) => {
      const leavingModule = currentModule;
      const leavingTask = moduleTaskStateRef.current[leavingModule];
      if (currentView === "detail" && leavingTask.previewState === "paused") {
        savePausedSession(leavingModule);
      }

      setCurrentModule(module);
      setCurrentView("detail");

      const saved = pausedSessionsRef.current[module];
      const enteringTask = moduleTaskStateRef.current[module];
      if (saved) {
        restorePausedSession(module, saved);
        addLog("info", "已恢复暂停的任务，可点击「继续处理」从断点续跑", module);
      } else if (
        enteringTask.previewState === "empty" &&
        !enteringTask.running &&
        !enteringTask.taskId
      ) {
        setOutputDir("");
        setSampleRoot("");
        setExcelFile("");
      }

      const config = MODULE_CONFIG[module];
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
      addLog("info", `切换到模块: ${config.title}`, module);
    },
    [addLog, currentView, currentModule, savePausedSession, restorePausedSession],
  );

  const navigateHome = useCallback(() => {
    const task = moduleTaskStateRef.current[currentModule];
    if (task.previewState === "paused") {
      savePausedSession(currentModule);
    }
    setCurrentView("home");
  }, [currentModule, savePausedSession]);

  const clearResult = useCallback(() => {
    patchModuleTask(currentModule, {
      previewState: "empty",
      result: null,
      taskId: null,
    });
    clearPausedSession(currentModule);
    setPrintedOrders(new Set());
  }, [currentModule, clearPausedSession, patchModuleTask]);

  const loadPreset = useCallback(async () => {
    invalidatePresetCache();
    await applyModulePreset(currentModule);
  }, [currentModule, applyModulePreset]);

  const selectFolder = useCallback(async () => {
    try {
      const result = (await invoke("select_folder")) as string | null;
      if (result) setSampleRoot(normalizePath(result));
    } catch {
      addLog("error", "选择文件夹失败");
    }
  }, [addLog]);

  const selectOutputDir = useCallback(async () => {
    try {
      const result = (await invoke("select_folder")) as string | null;
      if (result) setOutputDir(normalizePath(result));
    } catch {
      addLog("error", "选择输出文件夹失败");
    }
  }, [addLog]);

  const selectExcel = useCallback(async () => {
    try {
      const result = (await invoke("select_files", { multiple: false })) as string[] | null;
      if (result && result.length > 0) setExcelFile(normalizePath(result[0]));
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
      patchModuleTask("company-query", {
        result: {
          companies,
          company_stats: stats,
          output_excel_path: "",
        },
        previewState: "result",
      });
      addLog("info", `已加载 ${companies.length} 条缓存记录`);
    } catch (e) {
      const err = e as Error;
      addLog("error", `加载缓存记录失败: ${err?.message || e}`);
    }
  }, [excelFile, cacheTtlDays, addLog, patchModuleTask]);

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
      patchModuleTask("company-query", { result: null, previewState: "empty" });
    } catch (e) {
      const err = e as Error;
      addLog("error", `清除缓存失败: ${err?.message || e}`);
    }
  }, [excelFile, addLog, patchModuleTask]);

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
    const task = moduleTaskStateRef.current.print;
    if (!task.taskId || task.cancelling) return;
    patchModuleTask("print", { cancelling: true, previewState: "cancelling" });
    addLog("warn", `正在中止打印任务 ${task.taskId}...`, "print");
    try {
      await sendRequest("task.cancel", { task_id: task.taskId });
      addLog("warn", "取消请求已发送", "print");
    } catch (err) {
      addLog("error", `中止打印请求发送失败: ${err}`, "print");
    }
  }, [addLog, patchModuleTask]);

  const printOrders = useCallback(
    async (orders: number[]) => {
      const printTask = moduleTaskStateRef.current.print;
      if (printTask.running || !sampleRoot) return;
      justPrintedRef.current = true;
      setPrintingOrders((prev) => {
        const next = new Set(prev);
        orders.forEach((o) => next.add(o));
        return next;
      });
      const taskId = `print-${Date.now()}`;
      taskIdToModuleRef.current[taskId] = "print";
      taskConfigRef.current[taskId] = { sampleRoot, excelFile, outputDir };
      patchModuleTask("print", { taskId, running: true, cancelling: false });
      addLog("info", `开始打印 ${orders.length} 条...`, "print");
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
        if (moduleTaskStateRef.current.print.taskId !== taskId) return;
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
        setPrintingOrders((prev) => {
          const next = new Set(prev);
          orders.forEach((o) => next.delete(o));
          return next;
        });
        patchModuleTask("print", (prev) => ({
          previewState: "result" as PreviewState,
          running: false,
          result: {
            ...prev.result,
            printer_used: rawResult.printer_used || prev.result?.printer_used || "",
            print_errors: rawResult.errors || [],
            print_match_results: rawResult.match_results || prev.result?.print_match_results || [],
            summary: { result_root: sampleRoot },
          },
        }));
        const failedOrders = new Set(
          (rawResult.errors || [])
            .map((e: { company?: string; file?: string; error: string }) => {
              const mr = rawResult.match_results || [];
              const found = mr.find(
                (m: { company?: string; order?: number }) => m.company === e.company,
              );
              return found?.order;
            })
            .filter(Boolean) as number[],
        );
        const successOrders = orders.filter((o) => !failedOrders.has(o));
        setPrintedOrders((prev) => {
          const next = new Set(prev);
          successOrders.forEach((o) => next.add(o));
          return next;
        });
        addLog(
          "info",
          `打印完成: ${rawResult.submitted || 0} 成功, ${rawResult.failed || 0} 失败`,
          "print",
        );
      } catch (err) {
        if (moduleTaskStateRef.current.print.taskId !== taskId) return;
        const msg = err instanceof Error ? err.message : String(err);
        addLog("error", `打印失败: ${msg}`, "print");
        setPrintingOrders((prev) => {
          const next = new Set(prev);
          orders.forEach((o) => next.delete(o));
          return next;
        });
      } finally {
        if (moduleTaskStateRef.current.print.taskId === taskId) {
          patchModuleTask("print", { running: false, cancelling: false, previewState: "result" });
        }
        // 3秒后清除标记，允许自动预览再次触发
        setTimeout(() => {
          justPrintedRef.current = false;
        }, 3000);
      }
    },
    [
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
      patchModuleTask,
      outputDir,
    ],
  );

  const pollPrintStatusRef = useRef<((taskId: string) => Promise<void>) | null>(null);

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
    const module = currentModule;
    const task = moduleTaskStateRef.current[module];
    if (!task.taskId || task.cancelling) return;
    patchModuleTask(module, { cancelling: true, previewState: "cancelling" });
    addLog("warn", `正在取消任务 ${task.taskId}...`, module);
    try {
      await sendRequest("task.cancel", { task_id: task.taskId });
      addLog("warn", "取消信号已发送，等待后端停止...", module);
    } catch (err) {
      addLog("error", `取消请求发送失败: ${err}`, module);
    }
  }, [addLog, currentModule, patchModuleTask]);

  const startProcessing = useCallback(async () => {
    const module = currentModule;
    const task = moduleTaskStateRef.current[module];
    if (task.running) return;
    if (!sampleRoot && currentModule !== "company-query") {
      alert("请选择样本材料文件夹");
      return;
    }
    if (!excelFile && currentModule !== "print") {
      alert("请选择台账 Excel 文件");
      return;
    }
    const needsOcr =
      currentModule === "non-litigation" || (currentModule === "enforcement" && !mockMode);
    if (needsOcr && !ocrEngineReady) {
      alert("OCR 引擎正在后台准备中，请稍候片刻后再试");
      return;
    }

    const isResume = task.previewState === "paused" && !!task.taskId;
    const taskId = isResume ? task.taskId! : `${module}-${Date.now()}`;
    taskIdToModuleRef.current[taskId] = module;
    taskConfigRef.current[taskId] = { sampleRoot, excelFile, outputDir };
    flushLogs();
    patchModuleTask(module, {
      taskId,
      running: true,
      cancelling: false,
      previewState: "progress",
      result: isResume ? task.result : null,
      liveCompanies: isResume ? task.liveCompanies : [],
    });
    setLogsExpanded(true);
    if (isResume) {
      try {
        await sendRequest("task.clear_cancel", { task_id: taskId });
      } catch {
        // ignore
      }
      addLog("info", `继续${MODULE_CONFIG[module].title}处理（断点续跑）...`, module);
    } else {
      addLog("info", `开始${MODULE_CONFIG[module].title}处理...`, module);
    }

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
      } else if (module === "company-query") {
        const cqExcel = excelFile;
        if (!cqExcel) {
          alert("请选择企业信息数据 Excel 文件，或点击「测试示例」加载预设");
          patchModuleTask(module, { running: false, previewState: "empty" });
          return;
        }
        const rawResult = (await sendRequest("company_query.process", {
          preset_id: MODULE_CONFIG["company-query"]?.presetId || "company-query",
          excel_path: cqExcel,
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
      } else if (module === "print") {
        if (!sampleRoot) {
          alert("请选择材料文件夹");
          patchModuleTask(module, { running: false, previewState: "empty" });
          return;
        }
        // 如果选择了 Excel 文件但没有选择匹配列，提示用户
        if (excelFile && !printCompanyNameColumn) {
          alert(
            "已选择台账文件，请选择「匹配字段」用于关联材料文件\n\n提示：先点击「加载 Excel 列」，然后从下拉框选择对应列",
          );
          patchModuleTask(module, { running: false, previewState: "empty" });
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
        if (moduleTaskStateRef.current.print.taskId !== taskId) return;
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
        const printPrev = moduleTaskStateRef.current.print.result;
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
          print_match_results: printPrev?.print_match_results || rawResult.match_results || [],
          print_dry_run: false,
          summary: { result_root: sampleRoot },
        };
      }
      if (moduleTaskStateRef.current[module].taskId !== taskId) return;
      const cancelled =
        (res as { cancelled?: boolean }).cancelled === true ||
        ((res as { success?: boolean }).success === false &&
          String((res as { error?: string }).error || "").includes("取消"));
      if (cancelled) {
        pauseTaskState(module);
        addLog("warn", "任务已暂停，可点击继续任务", module);
        return;
      }
      patchModuleTask(module, {
        previewState: "result",
        result: res,
        taskId: null,
        running: false,
        cancelling: false,
      });
      clearPausedSession(module);
      addLog("info", "处理完成！", module);
    } catch (err) {
      const error = err as Error | string;
      const msg = typeof error === "string" ? error : (error as Error)?.message || String(error);
      if (moduleTaskStateRef.current[module].taskId === taskId) {
        if (msg.includes("已取消") || msg.includes("cancel") || msg.includes("Cancelled")) {
          pauseTaskState(module);
          addLog("warn", "任务已暂停，可点击继续任务", module);
        } else {
          addLog("error", `处理失败: ${msg}`, module);
          alert(`处理失败: ${msg}`);
          patchModuleTask(module, { previewState: "empty", taskId: null });
        }
      }
    } finally {
      if (moduleTaskStateRef.current[module].taskId === taskId) {
        patchModuleTask(module, { running: false, cancelling: false });
      }
    }
  }, [
    currentModule,
    sampleRoot,
    excelFile,
    outputDir,
    mockMode,
    ocrEngineReady,
    forceOcr,
    printerName,
    printCopies,
    rangeStart,
    rangeEnd,
    cacheTtlDays,
    pauseTaskState,
    clearPausedSession,
    patchModuleTask,
    addLog,
    flushLogs,
    printCompanyNameColumn,
    printMode,
    printCustomStartPage,
    printCustomEndPage,
    selectedOrders,
  ]);

  const openOutput = useCallback(async () => {
    const taskResult = moduleTaskStateRef.current[currentModule].result;
    const path =
      currentModule === "company-query"
        ? taskResult?.output_excel_path
        : taskResult?.summary?.result_root;
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
  }, [currentModule, addLog]);

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
    if (!appReady) return;
    loadStatus();
    const timer = setInterval(loadStatus, 30000);
    return () => clearInterval(timer);
  }, [loadStatus, appReady]);

  const moduleTitle = MODULE_CONFIG[currentModule]?.title || "";

  return (
    <>
      {!appReady && startupProgress.phase !== "ready" ? (
        <StartupOverlay
          phase={startupProgress.label}
          detail={startupProgress.detail}
          error={startupProgress.error}
        />
      ) : null}
      {appReady && startupProgress.phase === "error" ? (
        <div className="shrink-0 border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-800">
          <span className="font-medium">后端未连接：</span>
          {startupProgress.error ?? startupProgress.label}
        </div>
      ) : null}
      {appReady && isTauri() && !ocrEngineReady ? (
        <OcrWarmupBanner
          detail={
            ocrGpuProbing
              ? ocrWarmupDetail
              : (ocrWarmupDetail ?? "后端与 OCR 正在启动，打包版首次可能需 1–3 分钟")
          }
          error={ocrWarmupError}
        />
      ) : null}
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
          ocrEngineReady={ocrEngineReady}
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
          printedOrders={printedOrders}
          printingOrders={printingOrders}
          running={currentTask.running}
          cancelling={currentTask.cancelling}
          taskPaused={currentTask.previewState === "paused"}
          previewState={currentTask.previewState}
          phase={currentTask.phase}
          progressCurrent={currentTask.progressCurrent}
          progressTotal={currentTask.progressTotal}
          progressFileCurrent={currentTask.progressFileCurrent}
          progressFileTotal={currentTask.progressFileTotal}
          progressMessage={currentTask.progressMessage}
          result={currentTask.result}
          liveCompanies={currentTask.liveCompanies}
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
