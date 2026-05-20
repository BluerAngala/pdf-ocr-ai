import type { ModuleConfig, ModuleType } from "./types";

export const ALL_MODULE_TYPES: ModuleType[] = [
  "non-litigation",
  "enforcement",
  "company-query",
  "print",
];

export const MODULE_CONFIG: Record<string, ModuleConfig> = {
  "non-litigation": { title: "非诉审查", presetId: "non-litigation-batch1" },
  enforcement: { title: "强制执行提取", presetId: "enforcement-extract" },
  print: { title: "自动打印", presetId: "enforcement-print" },
  "company-query": { title: "企业信息查询", presetId: "company-query" },
};

export const PHASE_NAMES: Record<string, string> = {
  ocr: "OCR 识别",
  export: "导出文件",
  validation: "验证",
  report: "生成报告",
  company_query: "企业查询",
  printing: "打印",
};

export const LOG_LEVEL_COLORS: Record<string, string> = {
  info: "text-blue-600",
  warn: "text-yellow-600",
  error: "text-red-600",
  debug: "text-slate-400",
};
