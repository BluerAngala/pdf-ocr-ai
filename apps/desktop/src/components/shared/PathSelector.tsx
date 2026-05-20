interface Props {
  label: string;
  value: string;
  onChange: (v: string) => void;
  onSelect: () => void;
  placeholder?: string;
  accent?: string;
  compact?: boolean;
}

const ACCENT_MAP: Record<string, { ring: string; border: string; hover: string; text: string }> = {
  blue: {
    ring: "focus:ring-blue-500/20 focus:border-blue-400",
    border: "hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700",
    hover: "hover:bg-blue-50",
    text: "",
  },
  amber: {
    ring: "focus:ring-amber-500/20 focus:border-amber-400",
    border: "hover:bg-amber-50 hover:border-amber-200 hover:text-amber-700",
    hover: "hover:bg-amber-50",
    text: "",
  },
  emerald: {
    ring: "focus:ring-emerald-500/20 focus:border-emerald-400",
    border: "hover:bg-emerald-50 hover:border-emerald-200 hover:text-emerald-700",
    hover: "hover:bg-emerald-50",
    text: "",
  },
  slate: {
    ring: "focus:ring-slate-500/20 focus:border-slate-400",
    border: "hover:bg-slate-100 hover:border-slate-300 hover:text-slate-700",
    hover: "hover:bg-slate-100",
    text: "",
  },
};

export default function PathSelector({
  label,
  value,
  onChange,
  onSelect,
  placeholder = "选择路径...",
  accent = "blue",
  compact = false,
}: Props) {
  const style = ACCENT_MAP[accent] || ACCENT_MAP.blue;

  if (compact) {
    return (
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-slate-500">{label}</label>
        <div className="flex gap-2">
          <input
            type="text"
            readOnly
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className={`flex-1 h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 ${style.ring} transition-all`}
          />
          <button
            onClick={onSelect}
            className={`h-8 w-8 flex items-center justify-center rounded-md text-slate-600 bg-slate-50 border border-slate-200 ${style.border} transition-all cursor-pointer`}
            title="选择"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              />
            </svg>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-slate-500">{label}</label>
      <input
        type="text"
        readOnly
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full h-8 rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 ${style.ring} transition-all`}
      />
      <button
        onClick={onSelect}
        className={`w-full h-8 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-slate-600 bg-slate-50 border border-slate-200 ${style.border} transition-all cursor-pointer`}
      >
        📁 选择
      </button>
    </div>
  );
}
