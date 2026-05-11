export interface PresetConfig {
  id: string;
  name: string;
  description: string;
  sampleRoot: string;
  excelPath: string;
  mode: "mock" | "real_ocr";
}

const PRESET_DEFS = [
  {
    id: "non-litigation-batch1",
    name: "非诉审查 - 第1批",
    description: "非诉组自动化样本材料（第1批）- 3个案件",
    sampleRel: "样本材料/非诉组自动化样本材料",
    excelRel: "样本材料/非诉组自动化样本材料/台账及命名规则.xlsx",
    mode: "mock" as const,
  },
  {
    id: "non-litigation-batch2",
    name: "非诉审查 - 第2批",
    description: "非诉组自动化样本材料（第2批）- 5个案件",
    sampleRel: "样本材料/非诉组自动化样本材料（第2批）",
    excelRel: "样本材料/非诉组自动化样本材料（第2批）/台账及命名规则.xlsx",
    mode: "mock" as const,
  },
  {
    id: "enforcement-extract",
    name: "强制执行 - 提取信息",
    description: "强制组-自动化/提取信息 - 裁定书信息提取",
    sampleRel: "样本材料/强制组-自动化/提取信息",
    excelRel: "样本材料/强制组-自动化/提取信息/非诉表格.xlsx",
    mode: "real_ocr" as const,
  },
  {
    id: "enforcement-print",
    name: "强制执行 - 自动打印",
    description: "强制组-自动化/自动打印 - 企业信息、裁定、责令",
    sampleRel: "样本材料/强制组-自动化/自动打印",
    excelRel: "样本材料/强制组-自动化/自动打印/AOL网上网立台账.xlsx",
    mode: "real_ocr" as const,
  },
  {
    id: "company-query",
    name: "企业信息查询",
    description: "企业工商信息、司法信息查询",
    sampleRel: "样本材料/企业信息查询",
    excelRel: "样本材料/企业信息查询/企业名单.xlsx",
    mode: "mock" as const,
  },
];

export function buildPresets(projectRoot: string): PresetConfig[] {
  const root = projectRoot.replace(/[\\/]+$/, "");
  return PRESET_DEFS.map((d) => ({
    id: d.id,
    name: d.name,
    description: d.description,
    sampleRoot: `${root}/${d.sampleRel}`,
    excelPath: `${root}/${d.excelRel}`,
    mode: d.mode,
  }));
}

let _cachedPresets: PresetConfig[] | null = null;

export async function getPresets(): Promise<PresetConfig[]> {
  if (_cachedPresets) return _cachedPresets;
  let root = ".";
  try {
    const { invoke } = await import("@tauri-apps/api/tauri");
    root = await invoke<string>("get_project_root_cmd");
  } catch {
    // not running in Tauri, use default
  }
  _cachedPresets = buildPresets(root);
  return _cachedPresets;
}

export function getPresetById(id: string): PresetConfig | undefined {
  if (_cachedPresets) return _cachedPresets.find((p) => p.id === id);
  return undefined;
}
