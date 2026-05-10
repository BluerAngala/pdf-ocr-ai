import type { PreviewState, ProcessingResult } from '../types'

interface Props {
  previewState: PreviewState
  phase: string
  progressCurrent: number
  progressTotal: number
  progressMessage: string
  result: ProcessingResult | null
  onOpenReport: () => void
  onOpenOutput: () => void
}

const STATUS_BADGE: Record<PreviewState, { text: string; className: string }> = {
  empty: { text: '就绪', className: 'text-[10px] font-medium text-slate-400 bg-slate-100 px-2 py-0.5 rounded' },
  progress: { text: '运行中', className: 'text-[10px] font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded' },
  result: { text: '完成', className: 'text-[10px] font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded' },
}

export default function PreviewPanel({
  previewState, phase, progressCurrent, progressTotal, progressMessage,
  result, onOpenReport, onOpenOutput,
}: Props) {
  const badge = STATUS_BADGE[previewState]
  const percentage = progressTotal > 0 ? Math.round((progressCurrent / progressTotal) * 100) : 0

  return (
    <div className="flex-1 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">预览</h3>
        <span className={badge.className}>{badge.text}</span>
      </div>
      <div className="flex-1 flex items-center justify-center p-6">
        {previewState === 'empty' && (
          <div className="text-center space-y-2">
            <svg className="w-10 h-10 text-slate-200 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-xs text-slate-400">配置参数后点击「开始处理」</p>
            <p className="text-[10px] text-slate-300">将显示处理进度与结果</p>
          </div>
        )}

        {previewState === 'progress' && (
          <div className="w-full">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">阶段: <span className="font-semibold text-slate-800">{phase || '-'}</span></span>
                <span className="text-xs font-medium text-slate-500">{progressCurrent} / {progressTotal}</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="progress-bar h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full" style={{ width: `${percentage}%` }} />
              </div>
              <div className="flex items-center gap-2.5 p-3 bg-slate-50 rounded-lg border border-slate-100">
                <svg className="w-4 h-4 text-blue-500 shrink-0 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <p className="text-xs font-medium text-slate-700 truncate">{progressMessage || '准备中...'}</p>
              </div>
            </div>
          </div>
        )}

        {previewState === 'result' && result && (
          <div className="w-full">
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
                  <p className="text-xl font-bold text-slate-800">{result.summary?.created_count ?? '-'}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">生成文件</p>
                </div>
                <div className="rounded-lg bg-emerald-50 p-3 text-center border border-emerald-200">
                  <p className="text-xl font-bold text-emerald-700">{Math.round((result.summary?.quality?.page_count_match_rate || 0) * 100)}%</p>
                  <p className="text-[10px] text-emerald-600 mt-0.5">页数匹配率</p>
                </div>
                <div className="rounded-lg bg-blue-50 p-3 text-center border border-blue-200">
                  <p className="text-xl font-bold text-blue-700">{Math.round((result.summary?.validation?.pass_rate || 0) * 100)}%</p>
                  <p className="text-[10px] text-blue-600 mt-0.5">验证通过率</p>
                </div>
              </div>
              <div className="flex gap-2 justify-center">
                <button onClick={onOpenReport} className="h-7 px-3.5 text-[11px] font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors cursor-pointer">查看报告</button>
                <button onClick={onOpenOutput} className="h-7 px-3.5 text-[11px] font-medium text-slate-600 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors cursor-pointer">打开输出</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
