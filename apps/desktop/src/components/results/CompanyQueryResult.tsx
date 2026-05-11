import type { ProcessingResult, CompanyQueryItem } from "../../types";

const STATUS_STYLES: Record<string, { badge: string; dot: string }> = {
  success: { badge: "text-emerald-700 bg-emerald-50 border-emerald-200", dot: "bg-emerald-500" },
  failed: { badge: "text-red-700 bg-red-50 border-red-200", dot: "bg-red-500" },
};

function CompanyRow({ item, index }: { item: CompanyQueryItem; index: number }) {
  const style = STATUS_STYLES[item.status] || STATUS_STYLES.failed;

  return (
    <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50/50 transition-colors">
      <td className="px-3 py-2 text-xs text-slate-400 text-center">{index + 1}</td>
      <td className="px-3 py-2 text-xs text-slate-700 max-w-[180px] truncate" title={item.original_name}>
        {item.original_name}
      </td>
      <td className="px-3 py-2 text-xs text-slate-700 max-w-[200px] truncate" title={item.current_name}>
        {item.current_name || "-"}
      </td>
      <td className="px-3 py-2 text-xs text-slate-700 truncate">{item.legal_person || "-"}</td>
      <td className="px-3 py-2 text-xs text-slate-700 truncate">{item.location || "-"}</td>
      <td className="px-3 py-2 text-xs text-slate-500 font-mono truncate">{item.credit_code || "-"}</td>
      <td className="px-3 py-2 text-center">
        <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded border ${style.badge}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          {item.status === "success" ? "成功" : "失败"}
        </span>
      </td>
    </tr>
  );
}

export default function CompanyQueryResult({ result }: { result: ProcessingResult }) {
  const stats = result.company_stats;
  const companies = result.companies || [];

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="grid grid-cols-4 gap-2">
        <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
          <p className="text-lg font-bold text-slate-800">{stats?.total ?? companies.length}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">企业总数</p>
        </div>
        <div className="rounded-lg bg-emerald-50 p-3 text-center border border-emerald-200">
          <p className="text-lg font-bold text-emerald-700">{stats?.success_count ?? "-"}</p>
          <p className="text-[10px] text-emerald-600 mt-0.5">✓ 查询成功</p>
        </div>
        <div className="rounded-lg bg-red-50 p-3 text-center border border-red-200">
          <p className="text-lg font-bold text-red-700">{stats?.fail_count ?? "-"}</p>
          <p className="text-[10px] text-red-600 mt-0.5">✗ 查询失败</p>
        </div>
        <div className="rounded-lg bg-blue-50 p-3 text-center border border-blue-200">
          <p className="text-lg font-bold text-blue-700">
            {stats && stats.total > 0 ? Math.round((stats.success_count / stats.total) * 100) : 0}%
          </p>
          <p className="text-[10px] text-blue-600 mt-0.5">成功率</p>
        </div>
      </div>

      {companies.length > 0 && (
        <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-slate-200">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-slate-50 z-10">
              <tr className="border-b border-slate-200">
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider text-center w-10">#</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">被执行人</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">现用名（含曾用名）</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">法代</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">所在地</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">信用代码</th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider text-center w-16">状态</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((item, i) => (<CompanyRow key={i} item={item} index={i} />))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
