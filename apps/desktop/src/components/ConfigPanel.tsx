interface Props {
  sampleRoot: string
  excelFile: string
  mockMode: boolean
  forceOcr: boolean
  onSampleRootChange: (v: string) => void
  onExcelFileChange: (v: string) => void
  onMockModeChange: (v: boolean) => void
  onForceOcrChange: (v: boolean) => void
  onSelectFolder: () => void
  onSelectExcel: () => void
}

export default function ConfigPanel({
  sampleRoot, excelFile, mockMode, forceOcr,
  onSampleRootChange, onExcelFileChange, onMockModeChange, onForceOcrChange,
  onSelectFolder, onSelectExcel,
}: Props) {
  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto">
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
        <div className="px-4 py-3 border-b border-slate-100">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">📂 快速选择</h3>
        </div>
        <div className="p-4 flex flex-col gap-1.5">
          <button onClick={onSelectFolder} className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-all cursor-pointer">
            📁 选择样本文件夹
          </button>
          <button onClick={onSelectExcel} className="w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-all cursor-pointer">
            📊 选择 Excel 文件
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
        <div className="px-4 py-3 border-b border-slate-100">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">⚙️ 配置</h3>
        </div>
        <div className="p-4 space-y-3.5">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-500">🗂️ 样本材料文件夹</label>
            <input
              type="text"
              readOnly
              value={sampleRoot}
              onChange={e => onSampleRootChange(e.target.value)}
              placeholder="选择文件夹..."
              className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-500">📋 台账 Excel 文件</label>
            <input
              type="text"
              readOnly
              value={excelFile}
              onChange={e => onExcelFileChange(e.target.value)}
              placeholder="选择文件..."
              className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all"
            />
          </div>
          <div className="flex items-center gap-4 pt-1">
            <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-500 hover:text-slate-700 transition-colors">
              <input
                type="checkbox"
                checked={mockMode}
                onChange={e => onMockModeChange(e.target.checked)}
                className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/30 w-3.5 h-3.5"
              />
              🎭 Mock 模式
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-500 hover:text-slate-700 transition-colors">
              <input
                type="checkbox"
                checked={forceOcr}
                onChange={e => onForceOcrChange(e.target.checked)}
                className="rounded border-slate-300 text-blue-600 focus:ring-blue-500/30 w-3.5 h-3.5"
              />
              🔄 强制 OCR
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}
