interface Props {
  running: boolean;
  cancelling?: boolean;
  taskPaused?: boolean;
  runDisabled?: boolean;
  runDisabledHint?: string;
  onRun: () => void;
  onCancel: () => void;
  runLabel: string;
  resumeLabel?: string;
  runIcon?: React.ReactNode;
  accent?: string;
}

const RUN_COLORS: Record<string, string> = {
  blue: "bg-blue-600 hover:bg-blue-700",
  amber: "bg-amber-600 hover:bg-amber-700",
  emerald: "bg-emerald-600 hover:bg-emerald-700",
  slate: "bg-slate-700 hover:bg-slate-800",
};

const DefaultRunIcon = (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
    />
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
);

const CancelIcon = (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <rect x="6" y="6" width="12" height="12" rx="2" strokeWidth={2} />
  </svg>
);

export default function ActionFooter({
  running,
  cancelling = false,
  taskPaused = false,
  runDisabled = false,
  runDisabledHint,
  onRun,
  onCancel,
  runLabel,
  resumeLabel = "继续任务",
  runIcon,
  accent = "blue",
}: Props) {
  const disabledClass = "bg-slate-300 cursor-not-allowed hover:bg-slate-300";
  if (running) {
    return (
      <button
        onClick={onCancel}
        disabled={cancelling}
        className={`shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white active:scale-[0.98] transition-all shadow-sm cursor-pointer flex items-center justify-center gap-2 ${cancelling ? "bg-slate-400 cursor-not-allowed" : "bg-red-500 hover:bg-red-600"}`}
      >
        {CancelIcon}
        {cancelling ? "正在取消..." : "取消任务"}
      </button>
    );
  }

  if (taskPaused) {
    return (
      <button
        onClick={onRun}
        disabled={runDisabled}
        title={runDisabled ? runDisabledHint : undefined}
        className={`shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white ${runDisabled ? disabledClass : RUN_COLORS[accent] || RUN_COLORS.blue} active:scale-[0.98] transition-all shadow-sm cursor-pointer flex items-center justify-center gap-2`}
      >
        {runIcon || DefaultRunIcon}
        {resumeLabel}
      </button>
    );
  }

  return (
    <button
      onClick={onRun}
      disabled={runDisabled}
      title={runDisabled ? runDisabledHint : undefined}
      className={`shrink-0 w-full h-11 rounded-lg text-sm font-semibold text-white ${runDisabled ? disabledClass : RUN_COLORS[accent] || RUN_COLORS.blue} active:scale-[0.98] transition-all shadow-sm cursor-pointer flex items-center justify-center gap-2`}
    >
      {runIcon || DefaultRunIcon}
      {runLabel}
    </button>
  );
}
