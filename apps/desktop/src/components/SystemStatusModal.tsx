import { useEffect } from 'react'
import type { SystemStatus, DependenciesCheck } from '../types'

interface Props {
  statusInfo: { status: SystemStatus | null; deps: DependenciesCheck | null }
  onClose: () => void
}

export default function SystemStatusModal({ statusInfo, onClose }: Props) {
  const { status, deps } = statusInfo
  const rapidOcr = deps?.dependencies?.find(d => d.name === 'RapidOCR')
  const pdfplumber = deps?.dependencies?.find(d => d.name === 'pdfplumber')

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="modal-overlay fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal-content rounded-lg border bg-white shadow-2xl w-80 overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-800">系统状态详情</h3>
          <button onClick={onClose} className="w-7 h-7 inline-flex items-center justify-center rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="p-5 space-y-3 text-sm">
          <Row label="Python 版本" value={status?.python_version || '-'} />
          <Divider />
          <Row label="OCR 引擎" value={status?.ocr_engine_ready ? '就绪' : '未就绪'} />
          <Divider />
          <Row label="Poppler" value={status?.poppler_installed ? '已安装' : '未安装'} />
          <Divider />
          <Row label="可用内存" value={status?.available_memory_gb ? `${status.available_memory_gb} GB` : '-'} />
          <Divider />
          <Row label="RapidOCR" value={rapidOcr ? (rapidOcr.version || '已安装') : '未安装'} />
          <Divider />
          <Row label="pdfplumber" value={pdfplumber ? (pdfplumber.version || '已安装') : '未安装'} />
        </div>
        <div className="px-5 py-3.5 bg-slate-50 border-t border-slate-100 flex justify-end">
          <button onClick={onClose} className="inline-flex items-center justify-center h-8 px-4 text-xs font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-all cursor-pointer">关闭</button>
        </div>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-800">{value}</span>
    </div>
  )
}

function Divider() {
  return <div className="border-t border-slate-50" />
}
