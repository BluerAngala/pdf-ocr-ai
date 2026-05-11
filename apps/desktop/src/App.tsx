import { useState, useCallback, useRef, useEffect } from "react";
import type {
  ModuleType,
  LogEntry,
  PreviewState,
  ProcessingResult,
  ProgressParams,
  SystemStatus,
  DependenciesCheck,
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

export default function App() {
  const [currentView, setCurrentView] = useState<"home" | "detail">("home");
  const [currentModule, setCurrentModule] = useState<ModuleType>("non-litigation");
  const [sampleRoot, setSampleRoot] = useState("");
  const [excelFile, setExcelFile] = useState("");
  const [mockMode, setMockMode] = useState(false);
  const [forceOcr, setForceOcr] = useState(false);

  const [previewState, setPreviewState] = useState<PreviewState>("empty");
  const [phase, setPhase] = useState("");
  const [progressCurrent, setProgressCurrent] = useState(0);
  const [progressTotal, setProgressTotal] = useState(0);
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
      setProgressMessage(params.message);
      addLog("info", `[${params.phase}] ${params.message}`);
    },
    [addLog],
  );

  useEffect(() => {
    setupJsonRpcListeners(
      handleProgress,
      (params: any) => addLog(params.level, params.message),
      (params: any) => {
        if (params.success && params.result) {
          setPreviewState("result");
          setResult(params.result);
        }
      },
    );
    getPresets().then(() => addLog("info", "应用已启动"));
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

  const startProcessing = useCallback(async () => {
    if (!sampleRoot) {
      alert("请选择样本材料文件夹");
      return;
    }
    if (currentModule === "enforcement" && !excelFile) {
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
    addLog("info", `开始${MODULE_CONFIG[currentModule].title}处理...`);

    try {
      let res: ProcessingResult;
      if (currentModule === "non-litigation") {
        const config = MODULE_CONFIG[currentModule];
        res = await sendRequest("non_litigation.process", {
          preset_id: config.presetId,
          mode: mockMode ? "mock" : "real_ocr",
          force: forceOcr,
          task_id: taskId,
        });
      } else if (currentModule === "enforcement") {
        const config = MODULE_CONFIG[currentModule];
        const rawResult = await sendRequest("enforcement.extract", {
          preset_id: config.presetId,
          force_ocr: forceOcr,
          mock_mode: mockMode,
        });
        res = {
          processed: rawResult.processed || 0,
          extracted: rawResult.extracted || [],
          enforcement_stats: rawResult.stats || {},
          updated_excel_path: rawResult.updated_excel_path || "",
          html_report_path: rawResult.updated_excel_path || undefined,
          summary: {
            created_count: rawResult.processed || 0,
            result_root: rawResult.output_dir || undefined,
          },
        };
      } else if (currentModule === "print") {
        addLog("info", "[模拟] 自动打印处理...");
        res = {
          summary: {
            created_count: 5,
            quality: { page_count_match_rate: 1 },
            validation: { pass_rate: 1 },
          },
        };
      } else {
        // company-query or other modules
        addLog("info", `[模拟] ${MODULE_CONFIG[currentModule].title}处理...`);
        res = {
          summary: {
            created_count: 3,
            quality: { page_count_match_rate: 1 },
            validation: { pass_rate: 1 },
          },
        };
      }
      setPreviewState("result");
      setResult(res);
      addLog("info", "处理完成！");
    } catch (err: any) {
      const msg = typeof err === "string" ? err : err?.message || err?.toString() || "未知错误";
      addLog("error", `处理失败: ${msg}`);
      alert(`处理失败: ${msg}`);
      setPreviewState("empty");
    } finally {
      setRunning(false);
    }
  }, [currentModule, sampleRoot, excelFile, mockMode, forceOcr, addLog]);

  const openReport = useCallback(async () => {
    const path = result?.html_report_path || result?.summary?.result_root;
    if (!path) {
      alert("报告尚未生成");
      return;
    }
    try {
      if (isTauri()) await invoke("open_path", { path });
      else alert(`报告路径: ${path}`);
    } catch (err: any) {
      addLog("error", `打开报告失败: ${err}`);
    }
  }, [result, addLog]);

  const openOutput = useCallback(async () => {
    const path = result?.summary?.result_root;
    if (!path) {
      alert("输出文件夹尚未创建");
      return;
    }
    try {
      if (isTauri()) await invoke("open_path", { path });
      else alert(`输出路径: ${path}`);
    } catch (err: any) {
      addLog("error", `打开输出文件夹失败: ${err}`);
    }
  }, [result, addLog]);

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
        <HomeView onNavigate={navigateToModule} />
      ) : (
        <DetailView
          moduleType={currentModule}
          title={moduleTitle}
          sampleRoot={sampleRoot}
          excelFile={excelFile}
          mockMode={mockMode}
          forceOcr={forceOcr}
          onSampleRootChange={setSampleRoot}
          onExcelFileChange={setExcelFile}
          onMockModeChange={setMockMode}
          onForceOcrChange={setForceOcr}
          onBack={navigateHome}
          onPreset={loadPreset}
          onSelectFolder={selectFolder}
          onSelectExcel={selectExcel}
          onRun={startProcessing}
          running={running}
          previewState={previewState}
          phase={phase}
          progressCurrent={progressCurrent}
          progressTotal={progressTotal}
          progressMessage={progressMessage}
          result={result}
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
    </>
  );
}
