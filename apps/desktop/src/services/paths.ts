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
 * 通过 Tauri API 获取运行时路径（不写死仓库或安装路径）。
 * 业务样本/台账绝对路径仍由 Python `system.get_presets` 解析。
 */
export async function getRuntimePaths(forceRefresh = false): Promise<RuntimePaths | null> {
  if (!isTauri()) return null;
  if (cached && !forceRefresh) return cached;
  cached = (await invoke("get_runtime_paths")) as RuntimePaths;
  return cached;
}

export function clearRuntimePathsCache(): void {
  cached = null;
}
