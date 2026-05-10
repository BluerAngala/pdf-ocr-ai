import type { LogEntry } from '../types'
import { LOG_LEVEL_COLORS } from '../constants'

interface Props {
  logs: LogEntry[]
  expanded: boolean
  onToggle: () => void
  onCopy: () => void
  logsEndRef: React.RefObject<HTMLDivElement | null>
}

export default function LogsPanel({ logs, expanded, onToggle, onCopy, logsEndRef }: Props) {
  return (
    <div className="h-full bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col overflow-hidden">
      <div className="shrink-0 flex items-center justify-between gap-2 px-4 py-2.5 border-b border-slate-100">
        <button onClick={onToggle} className="flex items-center gap-2 hover:bg-slate-50 transition-colors cursor-pointer rounded px-2 -ml-2 py-1">
          <svg className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
          <span className="text-xs font-medium text-slate-500">运行日志</span>
        </button>
        <button onClick={onCopy} className="inline-flex items-center justify-center rounded-md text-[10px] font-medium h-5 px-1.5 border border-slate-200 bg-white text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-all cursor-pointer">
          <svg className="w-3 h-3 mr-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2" />
          </svg>
          复制
        </button>
      </div>
      {expanded && (
        <div className="flex-1 overflow-y-auto px-4 py-2 font-mono text-[11px] leading-relaxed space-y-0.5">
          {logs.map(log => (
            <div key={log.id} className="log-item flex items-start gap-1.5">
              <span className="text-slate-300 font-mono">{log.time}</span>
              <span className={LOG_LEVEL_COLORS[log.level] || 'text-slate-500'}>[{log.level.toUpperCase()}]</span>
              <span className="text-slate-600">{log.message}</span>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      )}
    </div>
  )
}
