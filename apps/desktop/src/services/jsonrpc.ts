import { invoke } from "@tauri-apps/api/tauri";
import { listen } from "@tauri-apps/api/event";
import type { JsonRpcResponse, JsonRpcNotification } from "../types";

let requestId = 0;
const pendingRequests = new Map<number, { resolve: Function; reject: Function }>();

export function isTauri(): boolean {
  return typeof window !== "undefined" && !!(window as any).__TAURI_IPC__;
}

export async function sendRequest(method: string, params: any): Promise<any> {
  if (!isTauri()) {
    return mockResponse(method, params);
  }
  const id = ++requestId;
  return new Promise((resolve, reject) => {
    pendingRequests.set(id, { resolve, reject });
    invoke("send_jsonrpc_request", { method, params, id }).catch((err) => {
      pendingRequests.delete(id);
      reject(err);
    });
  });
}

export function setupJsonRpcListeners(
  onProgress: (params: any) => void,
  onLog: (params: any) => void,
  onTaskComplete: (params: any) => void,
) {
  if (!isTauri()) return;

  listen("jsonrpc-response", (event: any) => {
    const response: JsonRpcResponse = event.payload;
    const id = response.id;
    if (pendingRequests.has(id)) {
      const { resolve, reject } = pendingRequests.get(id)!;
      pendingRequests.delete(id);
      if (response.error) {
        const errMsg =
          typeof response.error === "string"
            ? response.error
            : response.error?.message || JSON.stringify(response.error);
        reject(new Error(errMsg));
      } else resolve(response.result);
    }
  });

  listen("jsonrpc-notification", (event: any) => {
    const notification: JsonRpcNotification = event.payload;
    if (notification.method === "notify.progress") onProgress(notification.params);
    else if (notification.method === "notify.log") onLog(notification.params);
    else if (notification.method === "notify.task_complete") onTaskComplete(notification.params);
  });
}

function mockResponse(method: string, params: any): any {
  switch (method) {
    case "system.get_status":
      return {
        python_version: "3.12.0",
        ocr_engine_ready: true,
        ocr_version: "1.4.4",
        poppler_installed: true,
        config_loaded: true,
        available_memory_gb: 8.5,
        app_version: "1.0.0",
        developer: "陈恒律师",
      };
    case "system.check_dependencies":
      return {
        all_ready: true,
        dependencies: [
          { name: "RapidOCR", installed: true, version: "1.2.0" },
          { name: "pdfplumber", installed: true, version: "0.10.0" },
          { name: "Poppler", installed: true },
        ],
      };
    case "non_litigation.process":
      setTimeout(() => {
        console.log("[模拟] OCR 识别完成");
        console.log("[模拟] 导出文件完成: 12 个文件");
        console.log("[模拟] 验证完成: 通过率 95%");
      }, 1000);
      return {
        success: true,
        summary: {
          sample_root: params.preset_id || params.sample_root || "",
          result_root: "/output",
          runtime_seconds: 5.2,
          mode: params.mode,
          created_count: 12,
          quality: { total_files: 12, page_count_matched: 11, page_count_match_rate: 0.92 },
          validation: { total: 12, passed: 11, warnings: 1, failed: 0, pass_rate: 0.92 },
        },
        html_report_path: "/output/report.html",
      };
    case "enforcement.extract":
      return {
        processed: 3,
        extracted: [],
        updated_excel_path: "updated.xlsx",
      };
    case "ocr.get_cache_status":
      return { cached_files: [], total_cached: 0, cache_dir: "/tmp/ocr-cache" };
    case "company_query.search":
      return {
        companies: [
          { name: "示例企业有限公司", credit_code: "91110000XXXXXXXXXX", status: "存续" },
          { name: "示例科技股份有限公司", credit_code: "91110000YYYYYYYYYY", status: "存续" },
        ],
        total: 2,
      };
    case "company_query.process":
      return {
        total: 3,
        success_count: 2,
        fail_count: 1,
        companies: [
          { original_name: "爱玛客服务产业(中国)有限公司广东分公司", current_name: "爱玛客服务产业（中国）有限公司广东分公司", legal_person: "张三", location: "广东省广州市天河区", credit_code: "91440101MA5XXXXXXX", status: "success" },
          { original_name: "澳思美日用化工(广州)有限公司", current_name: "澳思美日用化工（广州）有限公司（曾用名：澳思美化工）", legal_person: "李四", location: "广东省广州市黄埔区", credit_code: "91440101MA5YYYYYYY", status: "success" },
          { original_name: "某不存在的公司", current_name: "", legal_person: "", location: "", credit_code: "", status: "failed", error: "未查询到企业数据" },
        ],
        output_excel_path: "/output/企业查询结果_mock.xlsx",
      };
    case "print.process":
      return {
        total_files: 5,
        printed: 4,
        failed: 1,
        printer_used: "Mock Printer",
        files: [
          { filename: "裁定书-张三.pdf", status: "printed", pages: 3 },
          { filename: "责令-李四.pdf", status: "printed", pages: 2 },
          { filename: "申请书-王五.pdf", status: "printed", pages: 1 },
          { filename: "授权书-赵六.pdf", status: "printed", pages: 1 },
          { filename: "所函-钱七.pdf", status: "failed", error: "模拟打印失败" },
        ],
      };
    case "print.list_printers":
      return {
        printers: [
          { name: "Mock Printer", is_default: true },
          { name: "Microsoft Print to PDF", is_default: false },
        ],
      };
    case "config.get":
      return {
        doc_types: [],
        regex_patterns: {},
        ocr_corrections: [],
        validation: { fuzzy_match_threshold: 0.85 },
      };
    default:
      throw new Error(`未实现的模拟方法: ${method}`);
  }
}
