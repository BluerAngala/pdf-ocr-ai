export interface PresetConfig {
  id: string
  name: string
  description: string
  sampleRoot: string
  excelPath: string
  mode: 'mock' | 'real_ocr'
}

const getProjectRoot = () => '.'

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
]

export function getPresetById(id: string): PresetConfig | undefined {
  return PRESETS.find(p => p.id === id)
}
