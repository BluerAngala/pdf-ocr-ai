/**
 * 预设样本路径配置
 * 方便一键加载测试数据
 */

export interface PresetConfig {
  id: string;
  name: string;
  description: string;
  sampleRoot: string;
  excelPath: string;
  mode: 'mock' | 'real_ocr';
}

// 获取项目根目录（相对于 Python server 的 cwd，即项目根目录）
const getProjectRoot = () => {
  // Rust 侧已将 Python cwd 设为项目根目录，直接使用相对路径即可
  return '.';
};

export const PRESETS: PresetConfig[] = [
  {
    id: 'non-litigation-batch1',
    name: '非诉审查 - 第1批',
    description: '非诉组自动化样本材料（第1批）- 3个案件',
    sampleRoot: `${getProjectRoot()}/样本材料/非诉组自动化样本材料`,
    excelPath: `${getProjectRoot()}/样本材料/非诉组自动化样本材料/台账及命名规则.xlsx`,
    mode: 'mock'
  },
  {
    id: 'non-litigation-batch2',
    name: '非诉审查 - 第2批',
    description: '非诉组自动化样本材料（第2批）- 5个案件',
    sampleRoot: `${getProjectRoot()}/样本材料/非诉组自动化样本材料（第2批）`,
    excelPath: `${getProjectRoot()}/样本材料/非诉组自动化样本材料（第2批）/台账及命名规则.xlsx`,
    mode: 'mock'
  },
  {
    id: 'enforcement-extract',
    name: '强制执行 - 提取信息',
    description: '强制组-自动化/提取信息 - 裁定书信息提取',
    sampleRoot: `${getProjectRoot()}/样本材料/强制组-自动化/提取信息`,
    excelPath: `${getProjectRoot()}/样本材料/强制组-自动化/提取信息/非诉表格.xlsx`,
    mode: 'real_ocr'
  },
  {
    id: 'enforcement-print',
    name: '强制执行 - 自动打印',
    description: '强制组-自动化/自动打印 - 企业信息、裁定、责令',
    sampleRoot: `${getProjectRoot()}/样本材料/强制组-自动化/自动打印`,
    excelPath: `${getProjectRoot()}/样本材料/强制组-自动化/自动打印/AOL网上网立台账.xlsx`,
    mode: 'real_ocr'
  }
];

// 根据 ID 获取预设
export function getPresetById(id: string): PresetConfig | undefined {
  return PRESETS.find(p => p.id === id);
}

// 获取所有预设
export function getAllPresets(): PresetConfig[] {
  return PRESETS;
}
