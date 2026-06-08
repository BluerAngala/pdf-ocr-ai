import type { ModuleType } from "../types";

const MODULES: {
  key: ModuleType;
  title: string;
  desc: string;
  color: string;
  iconBg: string;
  hoverBorder: string;
  hoverIconBg: string;
  arrowColor: string;
  iconPath: string;
}[] = [
  {
    key: "non-litigation",
    title: "非诉审查",
    desc: "PDF 自动识别、切分与重命名\n支持 OCR 缓存与 Mock 模式",
    color: "blue",
    iconBg: "bg-blue-50 group-hover:bg-blue-100",
    hoverBorder: "hover:border-blue-200",
    hoverIconBg: "group-hover:bg-blue-100",
    arrowColor: "text-blue-600",
    iconPath:
      "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  },
  {
    key: "enforcement",
    title: "强制执行",
    desc: "裁定书信息提取\nExcel 台账自动更新",
    color: "amber",
    iconBg: "bg-amber-50 group-hover:bg-amber-100",
    hoverBorder: "hover:border-amber-200",
    hoverIconBg: "group-hover:bg-amber-100",
    arrowColor: "text-amber-600",
    iconPath:
      "M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3",
  },
  {
    key: "company-query",
    title: "企业信息查询",
    desc: "企业工商信息、司法信息\n批量查询与结果导出",
    color: "emerald",
    iconBg: "bg-emerald-50 group-hover:bg-emerald-100",
    hoverBorder: "hover:border-emerald-200",
    hoverIconBg: "group-hover:bg-emerald-100",
    arrowColor: "text-emerald-600",
    iconPath:
      "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
  },
  {
    key: "print",
    title: "自动打印",
    desc: "企业信息、裁定、责令\n批量自动打印输出",
    color: "slate",
    iconBg: "bg-slate-50 group-hover:bg-slate-100",
    hoverBorder: "hover:border-slate-300",
    hoverIconBg: "group-hover:bg-slate-100",
    arrowColor: "text-slate-500",
    iconPath:
      "M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z",
  },
];

const ICON_COLORS: Record<string, string> = {
  blue: "text-blue-600",
  amber: "text-amber-600",
  slate: "text-slate-600",
  emerald: "text-emerald-600",
};

interface Props {
  onNavigate: (module: ModuleType) => void;
  onOpenChangelog: () => void;
}

export default function HomeView({ onNavigate, onOpenChangelog }: Props) {
  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="absolute top-4 right-4 z-10">
        <button
          onClick={onOpenChangelog}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-500 hover:text-slate-700 bg-white/80 hover:bg-white border border-slate-200 rounded-md shadow-sm transition-all cursor-pointer"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
            />
          </svg>
          <span>更新日志</span>
        </button>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center px-4 sm:px-8 gap-6 sm:gap-8 min-h-0">
        <div className="text-center space-y-2 sm:space-y-3">
          <h1 className="text-2xl sm:text-4xl font-bold text-[#0F172A] tracking-tight">公积金 OCR 工具</h1>
          <p className="text-sm sm:text-lg text-slate-500">选择功能模块开始处理</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 w-full max-w-2xl">
          {MODULES.map((m) => (
            <button
              key={m.key}
              onClick={() => onNavigate(m.key)}
              className={`group relative bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-lg ${m.hoverBorder} hover:-translate-y-0.5 transition-all duration-200 p-5 sm:p-8 text-center cursor-pointer`}
            >
              <div
                className={`w-10 h-10 sm:w-12 sm:h-12 ${m.iconBg} rounded-lg flex items-center justify-center mb-3 sm:mb-4 mx-auto transition-colors`}
              >
                <svg
                  className={`w-5 h-5 sm:w-6 sm:h-6 ${ICON_COLORS[m.color]}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d={m.iconPath}
                  />
                </svg>
              </div>
              <h3 className="text-base sm:text-lg font-semibold text-[#0F172A] mb-1 sm:mb-1.5">{m.title}</h3>
              <p className="text-xs sm:text-sm text-slate-500 leading-relaxed whitespace-pre-line">{m.desc}</p>
              <div
                className={`absolute bottom-2 right-2 sm:bottom-3 sm:right-3 flex items-center gap-1 text-xs sm:text-sm font-medium ${m.arrowColor} opacity-0 group-hover:opacity-100 transition-opacity`}
              >
                <span>进入模块</span>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
