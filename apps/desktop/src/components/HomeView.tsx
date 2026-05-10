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
};

interface Props {
  onNavigate: (module: ModuleType) => void;
}

export default function HomeView({ onNavigate }: Props) {
  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 flex flex-col items-center justify-center px-8 gap-8">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold text-[#0F172A] tracking-tight">公积金 OCR 工具</h1>
          <p className="text-sm text-slate-500">选择功能模块开始处理非诉与强制执行材料</p>
        </div>

        <div className="grid grid-cols-3 gap-6 w-full max-w-3xl">
          {MODULES.map((m) => (
            <button
              key={m.key}
              onClick={() => onNavigate(m.key)}
              className={`group relative bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-lg ${m.hoverBorder} hover:-translate-y-0.5 transition-all duration-200 p-6 text-left cursor-pointer`}
            >
              <div
                className={`w-10 h-10 ${m.iconBg} rounded-lg flex items-center justify-center mb-4 transition-colors`}
              >
                <svg
                  className={`w-5 h-5 ${ICON_COLORS[m.color]}`}
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
              <h3 className="text-base font-semibold text-[#0F172A] mb-1.5">{m.title}</h3>
              <p className="text-xs text-slate-500 leading-relaxed whitespace-pre-line">{m.desc}</p>
              <div
                className={`mt-3 flex items-center gap-1 text-xs font-medium ${m.arrowColor} opacity-0 group-hover:opacity-100 transition-opacity`}
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
