// Tauri v2 内置自动更新服务
import { check, type Update } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

export type DownloadStatus =
  | { type: "idle" }
  | { type: "checking" }
  | { type: "available"; update: Update }
  | { type: "downloading"; progress: number; total?: number }
  | { type: "downloaded" }
  | { type: "installing" }
  | { type: "uptodate" }
  | { type: "error"; message: string };

let currentStatus: DownloadStatus = { type: "idle" };
let statusListeners: Array<(status: DownloadStatus) => void> = [];

function setStatus(status: DownloadStatus) {
  currentStatus = status;
  statusListeners.forEach((cb) => cb(status));
}

export function subscribeStatus(callback: (status: DownloadStatus) => void) {
  statusListeners.push(callback);
  callback(currentStatus);
  return () => {
    statusListeners = statusListeners.filter((cb) => cb !== callback);
  };
}

export function getCurrentStatus(): DownloadStatus {
  return currentStatus;
}

/**
 * 检查更新（使用 Tauri 内置 updater）
 */
export async function checkForUpdates(): Promise<DownloadStatus> {
  try {
    setStatus({ type: "checking" });

    const update = await check();

    if (update) {
      setStatus({ type: "available", update });
      return { type: "available", update };
    } else {
      setStatus({ type: "uptodate" });
      return { type: "uptodate" };
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "检查更新失败";
    setStatus({ type: "error", message });
    return { type: "error", message };
  }
}

/**
 * 下载并安装更新
 */
export async function downloadAndInstallUpdate(update: Update): Promise<DownloadStatus> {
  try {
    setStatus({ type: "downloading", progress: 0 });

    await update.downloadAndInstall((event) => {
      switch (event.event) {
        case "Started": {
          const data = event.data as Record<string, unknown>;
          const total = typeof data.contentLength === "number" ? data.contentLength : 0;
          setStatus({
            type: "downloading",
            progress: 0,
            total: total > 0 ? total : undefined,
          });
          break;
        }
        case "Progress": {
          const data = event.data as Record<string, unknown>;
          const chunkLength = typeof data.chunkLength === "number" ? data.chunkLength : 0;
          setStatus({
            type: "downloading",
            progress: chunkLength,
          });
          break;
        }
        case "Finished":
          setStatus({ type: "downloaded" });
          break;
      }
    });

    setStatus({ type: "installing" });

    // 重新启动应用
    await relaunch();

    return { type: "installing" };
  } catch (error) {
    const message = error instanceof Error ? error.message : "下载更新失败";
    setStatus({ type: "error", message });
    return { type: "error", message };
  }
}

/**
 * 获取版本信息（从 Update 对象）
 */
export function getUpdateInfo(update: Update) {
  return {
    version: update.version,
    notes: update.body || "暂无更新说明",
    date: update.date,
  };
}
