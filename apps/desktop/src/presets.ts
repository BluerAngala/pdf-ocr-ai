import { sendRequest, isTauri } from "./services/jsonrpc";
import { normalizePath } from "./services/paths";

export interface PresetConfig {
  id: string;
  name: string;
  description: string;
  sampleRoot: string;
  excelPath: string;
  mode: "mock" | "real_ocr";
}

/** 仅用于浏览器 mock；真实路径一律由 Python system.get_presets 解析 */
const PRESET_STUBS: Omit<PresetConfig, "sampleRoot" | "excelPath">[] = [
  {
    id: "non-litigation-batch1",
    name: "非诉审查 - 第1批",
    description: "非诉组自动化样本材料（第1批）- 3个案件",
    mode: "mock",
  },
  {
    id: "non-litigation-batch2",
    name: "非诉审查 - 第2批",
    description: "非诉组自动化样本材料（第2批）- 5个案件",
    mode: "mock",
  },
  {
    id: "enforcement-extract",
    name: "强制执行 - 提取信息",
    description: "强制组-自动化/提取信息 - 裁定书信息提取",
    mode: "real_ocr",
  },
  {
    id: "enforcement-print",
    name: "强制执行 - 自动打印",
    description: "强制组-自动化/自动打印",
    mode: "real_ocr",
  },
  {
    id: "company-query",
    name: "企业信息查询",
    description: "企业工商信息、司法信息查询",
    mode: "mock",
  },
];

async function fetchPresetsFromPython(retries = 12, delayMs = 400): Promise<PresetConfig[] | null> {
  if (!isTauri()) return null;
  let lastError: unknown;
  for (let i = 0; i < retries; i++) {
    try {
      const raw = (await sendRequest("system.get_presets", {})) as {
        presets?: PresetConfig[];
        errors?: { id: string; error: string }[];
      };
      if (raw.errors?.length) {
        console.warn("[presets] 部分预设未解析:", raw.errors);
      }
      if (raw.presets?.length) {
        return raw.presets.map((p) => ({
          ...p,
          sampleRoot: normalizePath(p.sampleRoot),
          excelPath: normalizePath(p.excelPath),
        }));
      }
    } catch (e) {
      lastError = e;
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  if (lastError) {
    console.warn("[presets] system.get_presets 失败:", lastError);
  }
  return null;
}

let _cachedPresets: PresetConfig[] | null = null;

function presetIsUsable(p: PresetConfig): boolean {
  return Boolean(p.sampleRoot || p.excelPath);
}

function hasResolvedPreset(presets: PresetConfig[]): boolean {
  return presets.some(presetIsUsable);
}

export async function getPresets(forceRefresh = false): Promise<PresetConfig[]> {
  if (_cachedPresets && !forceRefresh) {
    if (!isTauri() || hasResolvedPreset(_cachedPresets)) {
      return _cachedPresets;
    }
    invalidatePresetCache();
  }

  // 在 Tauri 环境下，尝试从 Python 拉取真实路径
  // 失败时不抛错（容错），fallback 到 mock 列表
  if (isTauri()) {
    const fromPython = await fetchPresetsFromPython(
      forceRefresh ? 24 : 12,
      forceRefresh ? 500 : 400,
    );
    if (fromPython?.length) {
      _cachedPresets = fromPython;
      return fromPython;
    }
    // Python 拉取失败也不抛错，让上层走 mock fallback（无 sampleRoot）
  }

  // 浏览器 mock 或 Tauri 失败时的 fallback
  _cachedPresets = PRESET_STUBS.map((d) => ({
    ...d,
    sampleRoot: "",
    excelPath: "",
  }));
  return _cachedPresets;
}

export function invalidatePresetCache(): void {
  _cachedPresets = null;
}

export function getPresetById(id: string): PresetConfig | undefined {
  return _cachedPresets?.find((p) => p.id === id);
}

export async function getPresetResolveErrors(): Promise<{ id: string; error: string }[]> {
  if (!isTauri()) return [];
  try {
    const raw = (await sendRequest("system.get_presets", {})) as {
      errors?: { id: string; error: string }[];
    };
    return raw.errors ?? [];
  } catch {
    return [];
  }
}

export async function ensurePresetById(presetId: string): Promise<PresetConfig | undefined> {
  let preset = getPresetById(presetId);
  if (preset && presetIsUsable(preset)) return preset;
  invalidatePresetCache();
  await getPresets(true);
  preset = getPresetById(presetId);
  return preset && presetIsUsable(preset) ? preset : undefined;
}
