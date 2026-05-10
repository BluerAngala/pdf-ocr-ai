import type { SystemStatus, DependenciesCheck } from '../types'

interface Props {
  statusInfo: { status: SystemStatus | null; deps: DependenciesCheck | null }
  onClick: () => void
}

export default function StatusBar({ statusInfo, onClick }: Props) {
  const { status } = statusInfo

  return (
    <footer onClick={onClick} className="h-7 bg-[#0F172A] text-slate-400 flex items-center justify-between px-5 shrink-0 cursor-pointer">
      <div className="flex items-center gap-4 text-[11px]">
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
          <span>Python {status?.python_version || '3.12'}</span>
        </span>
        <span className="text-slate-700">|</span>
        <span>{status?.ocr_engine_ready ? 'OCR 就绪' : 'OCR 未就绪'}</span>
        <span className="text-slate-700">|</span>
        <span>{status?.poppler_installed ? 'Poppler ✓' : 'Poppler ✗'}</span>
        <span className="text-slate-700">|</span>
        <span>{status?.available_memory_gb ? `${status.available_memory_gb} GB` : '- GB'}</span>
      </div>
      <span className="text-[10px] text-slate-600">点击查看详情</span>
    </footer>
  )
}
