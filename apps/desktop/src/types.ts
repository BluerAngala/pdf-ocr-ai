export type ModuleType = "non-litigation" | "enforcement" | "print" | "company-query";

export interface ModuleConfig {
  title: string;
  presetId: string;
}

export interface ProgressParams {
  task_id: string;
  phase: string;
  current: number;
  total: number;
  file_current: number;
  file_total: number;
  message: string;
  detail?: Record<string, unknown>;
}

export interface LogEntry {
  id: number;
  level: string;
  message: string;
  time: string;
}

export interface ValidationDetail {
  file_name: string;
  file_type: string;
  status: "pass" | "warning" | "fail";
  message: string;
  details?: Record<string, unknown>;
  suggestions?: string[];
  timing?: {
    total_duration?: number;
    method?: string;
    avg_time_per_page?: number;
  };
  accuracy?: {
    fallback_rate?: number;
    region_first_hit_rate?: number;
    keyword_detection_rate?: number;
    text_quality?: string;
    extraction_success?: boolean;
    match_confidence?: number;
  };
}

export interface TimingStats {
  [fileType: string]: {
    count: number;
    total: number;
    avg: number;
    min: number;
    max: number;
  };
}

export interface EnforcementExtracted {
  court_case_number: string;
  notice_numbers: string[];
  applicants: { name: string; type: string; confidence: number }[];
  respondents: { name: string; type: string; confidence: number }[];
  execution_amount: number | null;
  ruling_date: string | null;
  judge: string;
  clerk: string;
  court_name: string;
  ruling_result: string;
  is_withdraw: boolean;
  /** 本批裁定是否匹配到台账 */
  ledger_matched?: boolean;
}

export interface EnforcementUnmatchedExcel {
  notice_number: string;
  respondent?: string;
  employee?: string;
  region?: string;
  reason: string;
}

export interface EnforcementUnmatchedPdf {
  pdf_key: string;
  court_case_number?: string;
  notice_numbers?: string[];
  reason: string;
}

export interface EnforcementStats {
  total_pdfs: number;
  total_excel_rows: number;
  matched_rows: number;
  unmatched_rows: number;
  withdraw_count: number;
  matched_excel_rows?: number;
  unmatched_excel_rows?: number;
  matched_pdf_count?: number;
  unmatched_pdf_count?: number;
  pdf_match_rate?: number;
  excel_coverage_rate?: number;
  unmatched_details_total?: number;
  unmatched_details?: EnforcementUnmatchedExcel[];
  unmatched_pdf_details?: EnforcementUnmatchedPdf[];
}

export interface CompanyQueryItem {
  original_name: string;
  current_name: string;
  legal_person: string;
  location: string;
  credit_code: string;
  status: "success" | "warning" | "failed";
  error?: string;
  recharge_url?: string;
}

export interface CompanyQueryStats {
  total: number;
  success_count: number;
  warning_count: number;
  fail_count: number;
}

export interface PrintMatchItem {
  order: number;
  company: string;
  row: number;
  files: { name: string; path: string }[];
  status: "matched" | "no_match";
}

export interface PrintFileItem {
  filename: string;
  status: "printed" | "failed" | "pending" | "printing" | "submitted";
  company?: string;
  pages?: number;
  error?: string;
}

export interface PrintTaskStatus {
  task_id: string;
  status: "pending" | "running" | "completed" | "cancelled" | "failed";
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  current_file: string;
  current_company: string;
  printer_name: string;
  started_at: number | null;
  finished_at: number | null;
  error_count: number;
}

export interface PrintExcelColumn {
  column: string;
  name: string;
}

export interface PrinterInfo {
  name: string;
  is_default: boolean;
}

export interface ProcessingResult {
  summary?: {
    sample_root?: string;
    result_root?: string;
    runtime_seconds?: number;
    mode?: string;
    created_count?: number;
    quality?: {
      total_files?: number;
      page_count_matched?: number;
      page_count_match_rate?: number;
    };
    validation?: {
      total?: number;
      passed?: number;
      warnings?: number;
      failed?: number;
      pass_rate?: number;
    };
  };
  validation_details?: ValidationDetail[];
  validation_failed?: ValidationDetail[];
  validation_warnings?: ValidationDetail[];
  timing_statistics?: TimingStats;
  processed?: number;
  extracted?: EnforcementExtracted[];
  enforcement_stats?: EnforcementStats;
  updated_excel_path?: string;
  companies?: CompanyQueryItem[];
  company_stats?: CompanyQueryStats;
  output_excel_path?: string;
  print_files?: PrintFileItem[];
  print_stats?: { total_jobs: number; submitted: number; failed: number };
  print_task_id?: string;
  print_errors?: { company: string; file?: string; error: string }[];
  print_match_results?: PrintMatchItem[];
  print_dry_run?: boolean;
  printer_used?: string;
}

export interface SystemStatus {
  python_version?: string;
  ocr_engine_ready?: boolean;
  ocr_version?: string;
  poppler_installed?: boolean;
  config_loaded?: boolean;
  available_memory_gb?: number;
  app_version?: string;
  developer?: string;
}

export interface DependencyInfo {
  name: string;
  installed: boolean;
  version?: string;
}

export interface DependenciesCheck {
  all_ready: boolean;
  dependencies: DependencyInfo[];
}

export interface JsonRpcResponse {
  id: number;
  result?: unknown;
  error?: { message: string };
}

export interface JsonRpcNotification {
  method: string;
  params: unknown;
}

export type PreviewState = "empty" | "progress" | "cancelling" | "paused" | "result";

/** 各功能模块独立的任务 UI 状态（运行/取消/进度/结果互不串台） */
export interface ModuleTaskUiState {
  previewState: PreviewState;
  phase: string;
  progressCurrent: number;
  progressTotal: number;
  progressFileCurrent: number;
  progressFileTotal: number;
  progressMessage: string;
  result: ProcessingResult | null;
  running: boolean;
  cancelling: boolean;
  taskId: string | null;
  liveCompanies: CompanyQueryItem[];
}

/** 暂停任务会话：离开模块/返回主页后仍可恢复 */
export interface PausedTaskSession {
  taskId: string;
  phase: string;
  progressCurrent: number;
  progressTotal: number;
  progressFileCurrent: number;
  progressFileTotal: number;
  progressMessage: string;
  sampleRoot: string;
  excelFile: string;
  outputDir: string;
}
