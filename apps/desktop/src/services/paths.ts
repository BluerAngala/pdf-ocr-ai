import { invoke } from "@tauri-apps/api/tauri";
import { isTauri } from "./jsonrpc";

/** 与 Rust `get_runtime_paths` / Python `describe_runtime_paths` 对齐 */
export interface RuntimePaths {
  appRoot: string;
  resourcesDir: string;
  userDataDir: string;
  bundled: boolean;
}

let cached: RuntimePaths | null = null;

/**
 * 去掉 Windows 长路径前缀 `\\?\`，仅用于界面展示与状态存储。
 * 传给后端的普通 `C:\...` 路径在 Windows 上仍可正常访问。
 */
export function formatDisplayPath(path: string): string {
  if (!path) return path;
  const p = path.trim().replace(/\//g, "\\");
  if (p.startsWith("\\\\?\\UNC\\")) {
    return `\\\\${p.slice(8)}`;
  }
  if (p.startsWith("\\\\?\\")) {
    return p.slice(4);
  }
  return path.trim();
}

export function normalizePath(path: string): string {
  return formatDisplayPath(path);
}

/**
 * 通过 Tauri API 获取运行时路径（不写死仓库或安装路径）。
 * 业务样本/台账绝对路径仍由 Python `system.get_presets` 解析。
 */
export async function getRuntimePaths(forceRefresh = false): Promise<RuntimePaths | null> {
  if (!isTauri()) return null;
  if (cached && !forceRefresh) return cached;
  const raw = (await invoke("get_runtime_paths")) as RuntimePaths;
  cached = {
    ...raw,
    appRoot: normalizePath(raw.appRoot),
    resourcesDir: normalizePath(raw.resourcesDir),
    userDataDir: normalizePath(raw.userDataDir),
  };
  return cached;
}

export function clearRuntimePathsCache(): void {
  cached = null;
}
