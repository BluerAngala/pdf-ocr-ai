import { useEffect } from "react";
import type { SystemStatus, DependenciesCheck } from "../types";

interface Props {
  statusInfo: { status: SystemStatus | null; deps: DependenciesCheck | null };
  onClose: () => void;
}

interface DepRow {
  label: string;
  value: string;
  url?: string;
  ok: boolean;
}

function buildRows(status: SystemStatus | null, deps: DependenciesCheck | null): DepRow[] {
  const rows: DepRow[] = [];

  rows.push({
    label: "Python",
    value: status?.python_version || "-",
    url: "https://github.com/python/cpython",
    ok: true,
  });

  const ocrReady = status?.ocr_engine_ready;
  const ocrVer = status?.ocr_version;
  rows.push({
    label: "OCR 引擎",
    value: ocrReady ? (ocrVer ? `RapidOCR ${ocrVer}` : "RapidOCR") : "未安装",
    url: "https://github.com/RapidAI/RapidOCR",
    ok: !!ocrReady,
  });

  rows.push({
    label: "Poppler",
    value: status?.poppler_installed ? "已安装" : "未安装",
    url: "https://github.com/oschwartz10612/poppler-windows",
    ok: !!status?.poppler_installed,
  });

  const pdfplumber = deps?.dependencies?.find((d) => d.name === "pdfplumber");
  rows.push({
    label: "pdfplumber",
    value: pdfplumber?.installed ? pdfplumber.version || "已安装" : "未安装",
    url: "https://github.com/jsvine/pdfplumber",
    ok: !!pdfplumber?.installed,
  });

  rows.push({
    label: "可用内存",
    value: status?.available_memory_gb ? `${status.available_memory_gb} GB` : "-",
    ok: (status?.available_memory_gb ?? 0) > 0,
  });

  return rows;
}

function openUrl(url: string) {
  if ((window as any).__TAURI_IPC__) {
    import("@tauri-apps/api/tauri").then(({ invoke }) => {
      invoke("open_path", { path: url });
    });
  } else {
    window.open(url, "_blank");
  }
}

export default function SystemStatusModal({ statusInfo, onClose }: Props) {
  const { status, deps } = statusInfo;
  const rows = buildRows(status, deps);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="modal-overlay fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-content rounded-lg border bg-white shadow-2xl w-[400px] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-800">系统状态详情</h3>
          <button
            onClick={onClose}
            className="w-7 h-7 inline-flex items-center justify-center rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        <div className="py-3">
          {rows.map((row, i) => (
            <div key={i}>
              <div
                className={`flex justify-between items-center px-5 py-2.5 text-sm ${row.url ? "cursor-pointer hover:bg-slate-50 transition-colors group" : ""}`}
                onClick={() => row.url && openUrl(row.url)}
              >
                <span className="text-slate-500">{row.label}</span>
                <div className="flex items-center gap-1.5">
                  <span className={`font-medium ${row.ok ? "text-slate-800" : "text-red-500"}`}>
                    {row.value}
                  </span>
                  {row.url && (
                    <svg
                      className="w-3 h-3 text-slate-300 group-hover:text-blue-500 transition-colors"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                      />
                    </svg>
                  )}
                </div>
              </div>
              {i < rows.length - 1 && <div className="mx-5 border-t border-slate-50" />}
            </div>
          ))}
        </div>
        <div className="px-5 py-3 bg-slate-50 border-t border-slate-100">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>开发者：{status?.developer || "陈恒律师"}</span>
            <span>v{status?.app_version || "1.0.0"}</span>
          </div>
        </div>
        <div className="px-5 py-3 bg-slate-50 border-t border-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="inline-flex items-center justify-center h-8 px-4 text-xs font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-all cursor-pointer"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
