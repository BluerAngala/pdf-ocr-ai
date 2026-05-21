import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/tauri";
import { sendRequest, isTauri } from "./jsonrpc";
import { getRuntimePaths } from "./paths";
import { invalidatePresetCache, getPresets } from "../presets";

export type StartupPhase = "waiting_backend" | "loading_presets" | "ready" | "error";

export interface StartupProgress {
  phase: StartupPhase;
  label: string;
  detail?: string;
  error?: string;
}

export interface OcrWarmupProgress {
  label: string;
  detail?: string;
}

export interface OcrWarmupResult {
  ok: boolean;
  error?: string;
  durationSeconds?: number;
}

export async function isProductionBundle(): Promise<boolean> {
  if (!isTauri()) return false;
  try {
    return (await invoke("is_production_bundle")) as boolean;
  } catch {
    return false;
  }
}

async function pollPythonRpcReady(): Promise<boolean> {
  if (!isTauri()) return true;
  try {
    return (await invoke("is_python_service_ready")) as boolean;
  } catch {
    return false;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const OCR_FAST_WARMUP_TIMEOUT_MS = 60_000;
const OCR_FULL_WARMUP_TIMEOUT_MS = 120_000;

function requestWithTimeout<T>(
  method: string,
  params: Record<string, unknown>,
  timeoutMs: number,
): Promise<T> {
  return Promise.race([
    sendRequest(method, params) as Promise<T>,
    new Promise<T>((_, reject) =>
      setTimeout(
        () => reject(new Error(`${method} 超时（${Math.round(timeoutMs / 1000)}s）`)),
        timeoutMs,
      ),
    ),
  ]);
}

/** onefile 冷启动时 RPC 标志可能略早于 stdin 循环，对「未就绪」短暂重试 */
async function requestWithTimeoutWhenReady<T>(
  method: string,
  params: Record<string, unknown>,
  timeoutMs: number,
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  let lastErr: unknown;
  for (let attempt = 0; attempt < 60; attempt++) {
    const remaining = deadline - Date.now();
    if (remaining <= 0) break;
    try {
      return await requestWithTimeout<T>(method, params, Math.min(remaining, 30_000));
    } catch (e) {
      lastErr = e;
      const msg = e instanceof Error ? e.message : String(e);
      if (!msg.includes("not ready") && !msg.includes("未就绪")) {
        throw e;
      }
      await sleep(500);
    }
  }
  throw lastErr instanceof Error
    ? lastErr
    : new Error(`${method} 超时（${Math.round(timeoutMs / 1000)}s）`);
}

/**
 * 等待 Python JSON-RPC 就绪。轮询 + 事件双通道，避免事件早于前端 listen 注册而永远卡住。
 */
export function waitForPythonService(
  onProgress?: (label: string, detail?: string) => void,
): Promise<void> {
  if (!isTauri()) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      clearInterval(pollTimer);
      clearTimeout(timer);
      unlistenReady.then((u) => u());
      unlistenErr.then((u) => u());
      fn();
    };

    onProgress?.("正在启动后端服务…", "打包版首次启动可能需 1–3 分钟，请稍候");

    void (async () => {
      for (let i = 0; i < 20; i++) {
        if (await pollPythonRpcReady()) {
          finish(resolve);
          return;
        }
        await sleep(150);
      }
    })();

    const pollTimer = setInterval(() => {
      void (async () => {
        if (await pollPythonRpcReady()) {
          finish(resolve);
        }
      })();
    }, 400);

    const unlistenReady = listen("python-service-ready", () => {
      finish(resolve);
    });
    const unlistenErr = listen<string>("python-service-error", (event) => {
      finish(() => reject(new Error(event.payload || "后端启动失败")));
    });

    const timer = setTimeout(() => {
      finish(() =>
        reject(new Error("后端启动超时。请检查安装是否完整，或暂时关闭杀毒软件后重试。")),
      );
    }, 320_000);
  });
}

async function connectBackendAndPresets(onProgress: (p: StartupProgress) => void): Promise<void> {
  await waitForPythonService((label, detail) =>
    onProgress({ phase: "waiting_backend", label, detail }),
  );

  const tauriPaths = await getRuntimePaths();
  if (tauriPaths) {
    onProgress({
      phase: "waiting_backend",
      label: "路径已解析",
      detail: `RESOURCES=${tauriPaths.resourcesDir}`,
    });
  }

  const bundled = tauriPaths?.bundled ?? (await isProductionBundle());
  if (!bundled) {
    try {
      await sendRequest("ocr.clear_cache", {});
    } catch {
      /* 开发态忽略 */
    }
  }

  onProgress({
    phase: "loading_presets",
    label: "正在加载预设路径…",
  });
  invalidatePresetCache();
  let presetError: string | undefined;
  let diag: {
    summary?: string;
    configExists?: boolean;
    batch1Exists?: boolean;
    ledgerExists?: boolean;
  };
  try {
    diag = (await sendRequest("system.describe_paths", {})) as {
      summary?: string;
      configExists?: boolean;
      batch1Exists?: boolean;
      ledgerExists?: boolean;
    };
    if (!diag.configExists) {
      presetError = diag.summary || "resources/config.yaml 不存在";
      onProgress({
        phase: "loading_presets",
        label: "配置文件缺失",
        detail: presetError,
      });
    }
    const presets = await getPresets();
    const batch1 = presets.find((p) => p.id === "non-litigation-batch1" && p.sampleRoot);
    if (!batch1) {
      presetError =
        diag.summary || "内嵌样本 non-litigation-batch1 未找到，请重新安装或手动选择文件夹";
      onProgress({
        phase: "loading_presets",
        label: "预设路径未就绪",
        detail: presetError,
      });
      if (bundled) {
        onProgress({
          phase: "ready",
          label: "就绪（需手动选择样本目录）",
          detail: presetError,
        });
        return;
      }
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    presetError = msg;
    onProgress({
      phase: "loading_presets",
      label: "预设加载失败",
      detail: msg,
    });
    if (bundled) {
      onProgress({
        phase: "ready",
        label: "就绪（预设未加载）",
        detail: msg,
      });
      return;
    }
  }

  onProgress({ phase: "ready", label: "就绪", detail: presetError });
}

/**
 * 打包版：先进入主界面，后端与预设在后台连接（快装快用）。
 * 开发态：仍同步等待，便于排错。
 */
export async function runStartupWarmup(onProgress: (p: StartupProgress) => void): Promise<void> {
  // 桌面版一律先进入主界面，避免安装路径检测失败时整屏卡死
  if (isTauri()) {
    onProgress({
      phase: "ready",
      label: "就绪",
      detail: "后台正在连接服务…",
    });
    void connectBackendAndPresets(onProgress).catch((e) => {
      const msg = e instanceof Error ? e.message : String(e);
      onProgress({ phase: "error", label: "后端连接失败", error: msg });
    });
    return;
  }

  onProgress({
    phase: "waiting_backend",
    label: "正在启动后端服务…",
  });
  await connectBackendAndPresets(onProgress);
}

/**
 * Phase B：后台 OCR 预热（快速 CPU 路径 + 完整 GPU 探测）。
 */
export async function runBackgroundOcrWarmup(
  onProgress?: (p: OcrWarmupProgress) => void,
  onFastReady?: () => void,
): Promise<OcrWarmupResult> {
  if (!isTauri()) {
    return { ok: true };
  }

  try {
    await waitForPythonService((label, detail) => {
      onProgress?.({
        label,
        detail: detail ?? "打包版首次启动可能需 1–3 分钟，请稍候",
      });
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg };
  }

  onProgress?.({
    label: "正在预热 OCR 引擎…",
    detail: "先以快速模式加载，界面可先行使用",
  });

  try {
    const fast = (await requestWithTimeoutWhenReady<{
      status?: string;
      duration_seconds?: number;
      provider?: string;
    }>("ocr.warmup", { skip_gpu_probe: true }, OCR_FAST_WARMUP_TIMEOUT_MS)) as {
      status?: string;
      duration_seconds?: number;
      provider?: string;
    };

    if (fast.status === "warm" || fast.status === "already_warm") {
      onFastReady?.();
      if (fast.duration_seconds != null) {
        onProgress?.({
          label: "OCR 基础就绪",
          detail: `快速预热 ${fast.duration_seconds}s${fast.provider ? ` · ${fast.provider}` : ""}，正在探测 GPU…`,
        });
      } else {
        onProgress?.({
          label: "OCR 基础就绪",
          detail: "正在后台探测 GPU 加速…",
        });
      }
    }

    const full = (await requestWithTimeoutWhenReady<{
      status?: string;
      duration_seconds?: number;
      provider?: string;
      error?: string;
    }>("ocr.warmup", { full_probe: true }, OCR_FULL_WARMUP_TIMEOUT_MS)) as {
      status?: string;
      duration_seconds?: number;
      provider?: string;
      error?: string;
    };

    if (full.status === "error") {
      return { ok: false, error: full.error || "OCR 完整预热失败" };
    }

    onProgress?.({
      label: "OCR 引擎已就绪",
      detail:
        full.duration_seconds != null
          ? `完整预热 ${full.duration_seconds}s${full.provider ? ` · ${full.provider}` : ""}`
          : undefined,
    });
    return { ok: true, durationSeconds: full.duration_seconds };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    onProgress?.({ label: "OCR 预热未完成", detail: msg });
    return { ok: false, error: msg };
  }
}
