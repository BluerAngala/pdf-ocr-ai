import PathSelector from "../shared/PathSelector";
import ActionFooter from "../shared/ActionFooter";

interface Props {
  sampleRoot: string;
  excelFile: string;
  running: boolean;
  cancelling?: boolean;
  taskPaused?: boolean;
  onSampleRootChange: (v: string) => void;
  onExcelFileChange: (v: string) => void;
  onPreset: () => void;
  outputDir: string;
  onSelectFolder: () => void;
  onSelectExcel: () => void;
  onSelectOutputDir: () => void;
  onOutputDirChange: (v: string) => void;
  onRun: () => void;
  onCancel: () => void;
}

export default function NonLitigationConfig({
  sampleRoot,
  excelFile,
  running,
  cancelling = false,
  taskPaused = false,
  onSampleRootChange,
  onExcelFileChange,
  outputDir,
  onPreset,
  onSelectFolder,
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
              className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 px-2 py-1 rounded transition-colors cursor-pointer"
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
              label="🗂️ 样本材料文件夹"
              value={sampleRoot}
              onChange={onSampleRootChange}
              onSelect={onSelectFolder}
              placeholder="选择文件夹..."
              accent="blue"
            />
            <PathSelector
              label="📋 台账 Excel 文件"
              value={excelFile}
              onChange={onExcelFileChange}
              onSelect={onSelectExcel}
              placeholder="选择文件..."
              accent="blue"
            />
            <PathSelector
              label="📂 输出目录（可选）"
              value={outputDir}
              onChange={onOutputDirChange}
              onSelect={onSelectOutputDir}
              placeholder="默认按时间自动创建..."
              accent="blue"
            />
          </div>
        </div>
      </div>
      <ActionFooter
        running={running}
        cancelling={cancelling}
        taskPaused={taskPaused}
        onRun={onRun}
        onCancel={onCancel}
        runLabel="开始处理"
        resumeLabel="继续处理"
        accent="blue"
      />
    </div>
  );
}
