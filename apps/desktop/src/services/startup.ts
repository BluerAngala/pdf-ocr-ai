import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/tauri";
import { sendRequest, isTauri } from "./jsonrpc";
import { getRuntimePaths } from "./paths";
import { invalidatePresetCache, getPresets } from "../presets";

export type StartupPhase =
  | "waiting_backend"
  | "warming_ocr"
  | "loading_presets"
  | "ready"
  | "error";

export interface StartupProgress {
  phase: StartupPhase;
  label: string;
  detail?: string;
  error?: string;
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
        reject(
          new Error(
            "后端启动超时。请检查安装是否完整，或暂时关闭杀毒软件后重试。",
          ),
        ),
      );
    }, 320_000);
  });
}

export async function runStartupWarmup(
  onProgress: (p: StartupProgress) => void,
): Promise<void> {
  onProgress({
    phase: "waiting_backend",
    label: "正在启动后端服务…",
    detail: "打包版首次启动可能需 1–3 分钟",
  });
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
    phase: "warming_ocr",
    label: "正在预热 OCR 引擎…",
    detail: bundled ? "打包版首次加载模型较慢" : undefined,
  });
  try {
    const res = (await sendRequest("ocr.warmup", {})) as {
      status?: string;
      duration_seconds?: number;
    };
    if (res.status === "warm" && res.duration_seconds != null) {
      onProgress({
        phase: "warming_ocr",
        label: "OCR 引擎已就绪",
        detail: `预热耗时 ${res.duration_seconds}s`,
      });
    }
  } catch (e) {
    onProgress({
      phase: "warming_ocr",
      label: "OCR 预热未完成",
      detail: e instanceof Error ? e.message : String(e),
    });
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
  } = {};
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
    const batch1 = presets.find(
      (p) => p.id === "non-litigation-batch1" && p.sampleRoot,
    );
    if (!batch1) {
      presetError =
        diag.summary ||
        "内嵌样本 non-litigation-batch1 未找到，请重新安装或手动选择文件夹";
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
