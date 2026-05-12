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
}

export interface EnforcementStats {
  total_pdfs: number;
  total_excel_rows: number;
  matched_rows: number;
  unmatched_rows: number;
  withdraw_count: number;
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

export interface PrintFileItem {
  filename: string;
  status: "printed" | "failed" | "pending" | "printing";
  pages?: number;
  error?: string;
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
  html_report_path?: string;
  processed?: number;
  extracted?: EnforcementExtracted[];
  enforcement_stats?: EnforcementStats;
  updated_excel_path?: string;
  companies?: CompanyQueryItem[];
  company_stats?: CompanyQueryStats;
  output_excel_path?: string;
  print_files?: PrintFileItem[];
  print_stats?: { total_files: number; printed: number; failed: number };
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

export type PreviewState = "empty" | "progress" | "result";
