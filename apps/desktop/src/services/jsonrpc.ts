import { invoke } from '@tauri-apps/api/tauri'
import { listen } from '@tauri-apps/api/event'
import type { JsonRpcResponse, JsonRpcNotification } from '../types'

let requestId = 0
const pendingRequests = new Map<number, { resolve: Function; reject: Function }>()

export function isTauri(): boolean {
  return typeof window !== 'undefined' && !!(window as any).__TAURI_IPC__
}

export async function sendRequest(method: string, params: any): Promise<any> {
  if (!isTauri()) {
    return mockResponse(method, params)
  }
  const id = ++requestId
  return new Promise((resolve, reject) => {
    pendingRequests.set(id, { resolve, reject })
    invoke('send_jsonrpc_request', { method, params, id }).catch(err => {
      pendingRequests.delete(id)
      reject(err)
    })
  })
}

export function setupJsonRpcListeners(
  onProgress: (params: any) => void,
  onLog: (params: any) => void,
  onTaskComplete: (params: any) => void
) {
  if (!isTauri()) return

  listen('jsonrpc-response', (event: any) => {
    const response: JsonRpcResponse = event.payload
    const id = response.id
    if (pendingRequests.has(id)) {
      const { resolve, reject } = pendingRequests.get(id)!
      pendingRequests.delete(id)
      if (response.error) reject(new Error(response.error.message))
      else resolve(response.result)
    }
  })

  listen('jsonrpc-notification', (event: any) => {
    const notification: JsonRpcNotification = event.payload
    if (notification.method === 'notify.progress') onProgress(notification.params)
    else if (notification.method === 'notify.log') onLog(notification.params)
    else if (notification.method === 'notify.task_complete') onTaskComplete(notification.params)
  })
}

function mockResponse(method: string, params: any): any {
  switch (method) {
    case 'system.get_status':
      return {
        python_version: '3.12.0',
        ocr_engine_ready: true,
        poppler_installed: true,
        config_loaded: true,
        available_memory_gb: 8.5
      }
    case 'system.check_dependencies':
      return {
        all_ready: true,
        dependencies: [
          { name: 'RapidOCR', installed: true, version: '1.2.0' },
          { name: 'pdfplumber', installed: true, version: '0.10.0' },
          { name: 'Poppler', installed: true }
        ]
      }
    case 'non_litigation.process':
      setTimeout(() => {
        console.log('[模拟] OCR 识别完成')
        console.log('[模拟] 导出文件完成: 12 个文件')
        console.log('[模拟] 验证完成: 通过率 95%')
      }, 1000)
      return {
        success: true,
        summary: {
          sample_root: params.sample_root,
          result_root: params.sample_root + '/output',
          runtime_seconds: 5.2,
          mode: params.mode,
          created_count: 12,
          quality: { total_files: 12, page_count_matched: 11, page_count_match_rate: 0.92 },
          validation: { total: 12, passed: 11, warnings: 1, failed: 0, pass_rate: 0.92 }
        },
        html_report_path: params.sample_root + '/output/report.html'
      }
    case 'enforcement.extract':
      return {
        processed: 3,
        extracted: [],
        updated_excel_path: params.excel_path + '.updated.xlsx'
      }
    case 'ocr.get_cache_status':
      return { cached_files: [], total_cached: 0, cache_dir: '/tmp/ocr-cache' }
    case 'config.get':
      return {
        doc_types: [],
        regex_patterns: {},
        ocr_corrections: [],
        validation: { fuzzy_match_threshold: 0.85 }
      }
    default:
      throw new Error(`未实现的模拟方法: ${method}`)
  }
}
