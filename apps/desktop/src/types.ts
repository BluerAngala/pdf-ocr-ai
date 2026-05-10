export type ModuleType = 'non-litigation' | 'enforcement' | 'print'

export interface ModuleConfig {
  title: string
  presetId: string
}

export interface ProgressParams {
  task_id: string
  phase: string
  current: number
  total: number
  message: string
}

export interface LogEntry {
  id: number
  level: string
  message: string
  time: string
}

export interface ProcessingResult {
  summary?: {
    sample_root?: string
    result_root?: string
    runtime_seconds?: number
    mode?: string
    created_count?: number
    quality?: {
      total_files?: number
      page_count_matched?: number
      page_count_match_rate?: number
    }
    validation?: {
      total?: number
      passed?: number
      warnings?: number
      failed?: number
      pass_rate?: number
    }
  }
  html_report_path?: string
  processed?: number
}

export interface SystemStatus {
  python_version?: string
  ocr_engine_ready?: boolean
  poppler_installed?: boolean
  config_loaded?: boolean
  available_memory_gb?: number
}

export interface DependencyInfo {
  name: string
  installed: boolean
  version?: string
}

export interface DependenciesCheck {
  all_ready: boolean
  dependencies: DependencyInfo[]
}

export interface JsonRpcResponse {
  id: number
  result?: any
  error?: { message: string }
}

export interface JsonRpcNotification {
  method: string
  params: any
}

export type PreviewState = 'empty' | 'progress' | 'result'
