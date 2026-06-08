import type { ProcessingResult, CompanyQueryItem } from "../../types";

const STATUS_STYLES: Record<string, { badge: string; dot: string; label: string }> = {
  success: {
    badge: "text-emerald-700 bg-emerald-50 border-emerald-200",
    dot: "bg-emerald-500",
    label: "成功",
  },
  warning: {
    badge: "text-amber-700 bg-amber-50 border-amber-200",
    dot: "bg-amber-500",
    label: "警告",
  },
  failed: { badge: "text-red-700 bg-red-50 border-red-200", dot: "bg-red-500", label: "失败" },
};

function CompanyRow({ item, index }: { item: CompanyQueryItem; index: number }) {
  const style = STATUS_STYLES[item.status] || STATUS_STYLES.failed;

  return (
    <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50/50 transition-colors">
      <td className="px-3 py-2 text-xs text-slate-400 text-center">{index + 1}</td>
      <td className="px-3 py-2 text-xs text-slate-700 truncate" title={item.original_name}>
        {item.original_name}
      </td>
      <td className="px-3 py-2 text-xs text-slate-700 truncate" title={item.current_name}>
        {item.current_name || "-"}
      </td>
      <td className="px-3 py-2 text-xs text-slate-700 truncate">{item.legal_person || "-"}</td>
      <td className="px-3 py-2 text-xs text-slate-700 truncate">{item.location || "-"}</td>
      <td className="px-3 py-2 text-xs text-slate-500 font-mono truncate">
        {item.credit_code || "-"}
      </td>
      <td className="px-3 py-2 text-center">
        <span
          className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded border ${style.badge}`}
          title={item.error || ""}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          {style.label}
        </span>
      </td>
      <td className="px-3 py-2 text-xs text-slate-500 truncate" title={item.error || ""}>
        {item.error || "-"}
      </td>
    </tr>
  );
}

export default function CompanyQueryResult({ result }: { result: ProcessingResult }) {
  const stats = result.company_stats;
  const companies = result.companies || [];

  // 判断是否全部失败（成功率0%且失败数>0）
  const allFailed =
    stats && stats.total > 0 && stats.success_count === 0 && stats.fail_count === stats.total;
  // 检查是否包含余额不足错误
  const hasBalanceError = allFailed && companies.some((c) => c.error?.includes("余额不足"));
  const rechargeUrl = companies.find((c) => c.recharge_url)?.recharge_url;

  return (
    <div className="flex flex-col gap-4 h-full">
      <div
        className="grid gap-2"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(90px, 1fr))" }}
      >
        <div className="rounded-lg bg-slate-50 p-3 text-center border border-slate-100">
          <p className="text-lg font-bold text-slate-800">{stats?.total ?? companies.length}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">企业总数</p>
        </div>
        <div className="rounded-lg bg-emerald-50 p-3 text-center border border-emerald-200">
          <p className="text-lg font-bold text-emerald-700">{stats?.success_count ?? 0}</p>
          <p className="text-[10px] text-emerald-600 mt-0.5">✓ 查询成功</p>
        </div>
        <div className="rounded-lg bg-amber-50 p-3 text-center border border-amber-200">
          <p className="text-lg font-bold text-amber-700">{stats?.warning_count ?? 0}</p>
          <p className="text-[10px] text-amber-600 mt-0.5">⚠ 警告</p>
        </div>
        <div className="rounded-lg bg-red-50 p-3 text-center border border-red-200">
          <p className="text-lg font-bold text-red-700">{stats?.fail_count ?? 0}</p>
          <p className="text-[10px] text-red-600 mt-0.5">✗ 查询失败</p>
        </div>
        <div className="rounded-lg bg-blue-50 p-3 text-center border border-blue-200">
          <p className="text-lg font-bold text-blue-700">
            {stats && stats.total > 0 ? Math.round((stats.success_count / stats.total) * 100) : 0}%
          </p>
          <p className="text-[10px] text-blue-600 mt-0.5">成功率</p>
        </div>
      </div>

      {hasBalanceError && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 flex items-start gap-3">
          <svg
            className="w-5 h-5 text-red-500 shrink-0 mt-0.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-red-700">查询失败：API 余额不足</p>
            <p className="text-xs text-red-600 mt-1">
              所有企业查询均因 API 余额不足而失败。
              {rechargeUrl ? (
                <>
                  请
                  <a
                    href={rechargeUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mx-1 text-red-700 font-medium underline hover:text-red-800"
                    onClick={(e) => {
                      e.preventDefault();
                      window.open(rechargeUrl, "_blank");
                    }}
                  >
                    点击充值
                  </a>
                  后重试。
                </>
              ) : (
                "请充值后重试。"
              )}
            </p>
          </div>
        </div>
      )}

      {allFailed && !hasBalanceError && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 flex items-start gap-3">
          <svg
            className="w-5 h-5 text-red-500 shrink-0 mt-0.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-red-700">查询全部失败</p>
            <p className="text-xs text-red-600 mt-1">
              所有企业查询均失败，请检查网络连接或 API 配置后重试。
            </p>
          </div>
        </div>
      )}

      {companies.length > 0 && (
        <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-slate-200">
          <table className="w-full text-left min-w-[700px]">
            <thead className="sticky top-0 bg-slate-50 z-10">
              <tr className="border-b border-slate-200">
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider text-center whitespace-nowrap">
                  #
                </th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                  被执行人
                </th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                  现用名
                </th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                  法代
                </th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                  所在地
                </th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                  信用代码
                </th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider text-center whitespace-nowrap">
                  状态
                </th>
                <th className="px-3 py-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap">
                  错误信息
                </th>
              </tr>
            </thead>
            <tbody>
              {companies.map((item, i) => (
                <CompanyRow key={i} item={item} index={i} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
