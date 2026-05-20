import PathSelector from "../shared/PathSelector";
import ActionFooter from "../shared/ActionFooter";
import NumberCombo from "../shared/NumberCombo";

interface Props {
  excelFile: string;
  running: boolean;
  rangeStart: number;
  rangeEnd: number;
  cacheTtlDays: number;
  onLoadCache: () => void;
  onClearCache: () => void;
  onExcelFileChange: (v: string) => void;
  onRangeStartChange: (v: number) => void;
  onRangeEndChange: (v: number) => void;
  onCacheTtlDaysChange: (v: number) => void;
  outputDir: string;
  onPreset: () => void;
  onSelectExcel: () => void;
  onSelectOutputDir: () => void;
  onOutputDirChange: (v: string) => void;
  onRun: () => void;
  onCancel: () => void;
}

const CACHE_TTL_OPTIONS = [
  { value: 0, label: "不缓存" },
  { value: 3, label: "3 天" },
  { value: 7, label: "7 天" },
  { value: 30, label: "30 天" },
  { value: 90, label: "3 个月" },
  { value: 180, label: "6 个月" },
];

export default function CompanyQueryConfig({
  excelFile,
  running,
  rangeStart,
  rangeEnd,
  cacheTtlDays,
  onLoadCache,
  onClearCache,
  onExcelFileChange,
  onRangeStartChange,
  onRangeEndChange,
  onCacheTtlDaysChange,
  outputDir,
  onPreset,
  onSelectExcel,
  onSelectOutputDir,
  onOutputDirChange,
  onRun,
  onCancel,
}: Props) {
  return (
    <div className="h-full flex flex-col gap-4 overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              ⚙️ 配置
            </h3>
            <button
              onClick={onPreset}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 px-2 py-1 rounded transition-colors cursor-pointer"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
              测试示例
            </button>
          </div>
          <div className="p-4 space-y-3.5">
            <PathSelector
              label="📊 企业信息数据 Excel"
              value={excelFile}
              onChange={onExcelFileChange}
              onSelect={onSelectExcel}
              placeholder="选择包含被执行人列表的 Excel..."
              accent="emerald"
            />
            <PathSelector
              label="📂 输出目录（可选）"
              value={outputDir}
              onChange={onOutputDirChange}
              onSelect={onSelectOutputDir}
              placeholder="默认按时间自动创建..."
              accent="emerald"
            />

            <NumberCombo
              label="📋 查询范围（从第几行）"
              value={rangeStart}
              onChange={onRangeStartChange}
              min={1}
              shortcuts={[1, 2, 5]}
            />
            <NumberCombo
              label="到第几行"
              value={rangeEnd}
              onChange={onRangeEndChange}
              min={1}
              shortcuts={[5, 10, 30, 50, 100, 200]}
              placeholder="99999=全部"
            />
            <p className="text-[10px] text-slate-400">99999 视为查询全部，支持断点续查</p>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">💾 缓存有效期</label>
              <select
                value={cacheTtlDays}
                onChange={(e) => onCacheTtlDaysChange(parseInt(e.target.value))}
                disabled={running}
                className="w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {CACHE_TTL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <p className="text-[10px] text-slate-400">
                {cacheTtlDays === 0
                  ? "每次重新查询，不使用缓存"
                  : `缓存 ${CACHE_TTL_OPTIONS.find((o) => o.value === cacheTtlDays)?.label} 内有效`}
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={onLoadCache}
                disabled={!excelFile || running}
                className="flex-1 h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 hover:bg-amber-100 hover:border-amber-300 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"
                  />
                </svg>
                查看缓存
              </button>
              <button
                onClick={onClearCache}
                disabled={!excelFile || running}
                className="flex-1 h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-red-700 bg-red-50 border border-red-200 hover:bg-red-100 hover:border-red-300 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
                清除缓存
              </button>
            </div>

            <p className="text-[10px] text-slate-400 leading-relaxed">
              Excel
              需包含"被执行人"列，系统将逐个查询企业工商信息。已查询过的条目会自动跳过（缓存）。
            </p>
          </div>
        </div>
      </div>

      <ActionFooter
        running={running}
        onRun={onRun}
        onCancel={onCancel}
        runLabel="开始查询"
        runIcon={
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        }
        accent="emerald"
      />
    </div>
  );
}
