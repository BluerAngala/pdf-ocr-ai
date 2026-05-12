import { useEffect, useState } from "react";
import changelogData from "../changelog.json";

interface ChangeItem {
  type: "feature" | "improvement" | "fix";
  description: string;
}

interface Release {
  version: string;
  date: string;
  changes: ChangeItem[];
}

const TYPE_CONFIG: Record<string, { label: string; color: string; bgColor: string }> = {
  feature: { label: "新功能", color: "text-emerald-700", bgColor: "bg-emerald-50" },
  improvement: { label: "优化", color: "text-blue-700", bgColor: "bg-blue-50" },
  fix: { label: "修复", color: "text-amber-700", bgColor: "bg-amber-50" },
};

interface Props {
  onClose: () => void;
}

export default function ChangelogModal({ onClose }: Props) {
  const [releases] = useState<Release[]>(changelogData.releases as Release[]);
  const [currentVersion] = useState<string>(changelogData.version);

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
        className="modal-content rounded-lg border bg-white shadow-2xl w-[480px] max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 shrink-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-800">更新日志</h3>
            <span className="text-xs text-slate-400">v{currentVersion}</span>
          </div>
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

        <div className="flex-1 overflow-y-auto py-4">
          {releases.map((release, idx) => (
            <div
              key={release.version}
              className={idx > 0 ? "mt-4 pt-4 border-t border-slate-100" : ""}
            >
              <div className="px-5 mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-800">v{release.version}</span>
                  <span className="text-xs text-slate-400">{release.date}</span>
                  {idx === 0 && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-medium">
                      最新
                    </span>
                  )}
                </div>
              </div>
              <div className="px-5 space-y-2">
                {release.changes.map((change, changeIdx) => {
                  const config = TYPE_CONFIG[change.type] || TYPE_CONFIG.improvement;
                  return (
                    <div key={changeIdx} className="flex items-start gap-2.5">
                      <span
                        className={`shrink-0 text-xs px-1.5 py-0.5 rounded ${config.bgColor} ${config.color} font-medium mt-0.5`}
                      >
                        {config.label}
                      </span>
                      <span className="text-sm text-slate-600 leading-relaxed">
                        {change.description}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="px-5 py-3 bg-slate-50 border-t border-slate-100 shrink-0 flex justify-end">
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
