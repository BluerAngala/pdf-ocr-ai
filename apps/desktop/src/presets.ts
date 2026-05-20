import { sendRequest, isTauri } from "./services/jsonrpc";

export interface PresetConfig {
  id: string;
  name: string;
  description: string;
  sampleRoot: string;
  excelPath: string;
  mode: "mock" | "real_ocr";
}

const PRESET_DEFS: Omit<PresetConfig, "sampleRoot" | "excelPath">[] = [
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

async function fetchPresetsFromPython(retries = 8, delayMs = 400): Promise<PresetConfig[] | null> {
  if (!isTauri()) return null;
  for (let i = 0; i < retries; i++) {
    try {
      const raw = (await sendRequest("system.get_presets", {})) as {
        presets?: PresetConfig[];
      };
      if (raw.presets?.length) {
        return raw.presets;
      }
    } catch {
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  return null;
}

let _cachedPresets: PresetConfig[] | null = null;

export async function getPresets(): Promise<PresetConfig[]> {
  if (_cachedPresets) return _cachedPresets;

  const fromPython = await fetchPresetsFromPython();
  if (fromPython) {
    _cachedPresets = fromPython;
    return fromPython;
  }

  // 非 Tauri 或 Python 尚未就绪时的占位（浏览器 mock）
  _cachedPresets = PRESET_DEFS.map((d) => ({
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
  if (_cachedPresets) return _cachedPresets.find((p) => p.id === id);
  return undefined;
}
