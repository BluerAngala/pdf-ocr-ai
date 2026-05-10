import type { SystemStatus, DependenciesCheck } from "../types";

interface Props {
  statusInfo: { status: SystemStatus | null; deps: DependenciesCheck | null };
  onClick: () => void;
}

export default function StatusBar({ statusInfo, onClick }: Props) {
  const { status } = statusInfo;

  return (
    <footer
      onClick={onClick}
      className="h-7 bg-[#0F172A] text-slate-400 flex items-center justify-between px-5 shrink-0 cursor-pointer"
    >
      <span className="text-[11px] text-slate-500">
        软件版本号：v{status?.app_version || "1.0.0"}，{status?.developer || "陈恒律师"}
        基于开源项目开发，向开源精神致敬！
      </span>
      <span className="text-[10px] text-slate-600">点击查看详情</span>
    </footer>
  );
}
