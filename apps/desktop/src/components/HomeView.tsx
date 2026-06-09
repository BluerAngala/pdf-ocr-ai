import { useState, useLayoutEffect } from "react";
import type { ModuleType } from "../types";

const MODULES: {
  key: ModuleType;
  title: string;
  desc: string;
  color: string;
  iconBg: string;
  hoverBorder: string;
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
  onCheckUpdate?: () => void;
}

export default function HomeView({ onNavigate, onOpenChangelog, onCheckUpdate }: Props) {
  const [windowSize, setWindowSize] = useState({ width: 900, height: 600 });

  // useLayoutEffect 保证首屏 DPR/size 正确测量，避免初始布局抖动
  useLayoutEffect(() => {
    const updateSize = () => {
      setWindowSize({
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };

    updateSize();
    window.addEventListener("resize", updateSize);
    // DPR 变化时（用户拖窗口到不同 DPI 屏）WebView 不会自动 resize，需监听 matchMedia
    const mql = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
    mql.addEventListener("change", updateSize);
    return () => {
      window.removeEventListener("resize", updateSize);
      mql.removeEventListener("change", updateSize);
    };
  }, []);

  // 双重判断：高度 < 650 或 宽度 < 720 时切换紧凑模式
  const isCompact = windowSize.height < 650 || windowSize.width < 720;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* 标题栏 */}
      <div className="shrink-0 px-4 pt-4 pb-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A]">公积金 OCR 工具</h1>
            <p className="text-sm text-slate-500 mt-1">PDF 智能识别与案件处理平台</p>
          </div>
          <div className="flex items-center gap-2">
            {onCheckUpdate && (
              <button
                onClick={onCheckUpdate}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-md shadow-sm transition-all cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
                <span>检查更新</span>
              </button>
            )}
            <button
              onClick={onOpenChangelog}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-md shadow-sm transition-all cursor-pointer"
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
        </div>
      </div>

      {/* 卡片网格 - 自适应窗口宽度，最大 580px */}
      <div className="flex-1 min-h-0 px-4 pb-4 flex items-center justify-center overflow-auto">
        <div
          className="grid grid-cols-2 gap-4 sm:gap-5 w-full"
          style={{
            maxWidth: "min(580px, calc(100vw - 32px))",
          }}
        >
          {MODULES.map((m) => (
            <button
              key={m.key}
              onClick={() => onNavigate(m.key)}
              className={`group relative flex flex-col items-center justify-center bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md ${m.hoverBorder} hover:-translate-y-0.5 transition-all duration-200 cursor-pointer min-h-[160px] ${
                isCompact ? "p-4" : "p-5"
              }`}
            >
              <div
                className={`${isCompact ? "w-10 h-10" : "w-12 h-12"} ${m.iconBg} rounded-lg flex items-center justify-center mb-2 transition-colors shrink-0`}
              >
                <svg
                  className={`${isCompact ? "w-5 h-5" : "w-6 h-6"} ${ICON_COLORS[m.color]}`}
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

              <h3
                className={`${isCompact ? "text-sm" : "text-base"} font-semibold text-[#0F172A] mb-0.5`}
              >
                {m.title}
              </h3>

              <p
                className={`${isCompact ? "text-[11px]" : "text-xs"} text-slate-500 leading-relaxed whitespace-pre-line text-center`}
              >
                {m.desc}
              </p>

              <div
                className={`absolute bottom-2 right-2 flex items-center gap-0.5 text-xs font-medium ${m.arrowColor} opacity-0 group-hover:opacity-100 transition-opacity`}
              >
                <span>进入</span>
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
