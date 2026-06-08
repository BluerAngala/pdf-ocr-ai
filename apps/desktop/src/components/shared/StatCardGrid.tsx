interface StatItem {
  label: string;
  value: string | number;
  color: "emerald" | "amber" | "red" | "blue" | "slate" | "orange";
}

const CARD_COLORS: Record<string, string> = {
  emerald: "bg-emerald-50 text-emerald-700",
  amber: "bg-amber-50 text-amber-700",
  red: "bg-red-50 text-red-700",
  blue: "bg-blue-50 text-blue-700",
  slate: "bg-slate-50 text-slate-700",
  orange: "bg-orange-50 text-orange-700",
};

interface Props {
  items: StatItem[];
  columns?: number;
}

export default function StatCardGrid({ items, columns }: Props) {
  // 自动响应式：优先用 CSS grid auto-fill，columns 仅作为最小宽度提示
  const minMaxMap: Record<number, string> = {
    2: "minmax(100px, 1fr)",
    3: "minmax(100px, 1fr)",
    4: "minmax(100px, 1fr)",
    5: "minmax(90px, 1fr)",
    6: "minmax(80px, 1fr)",
  };
  const minMax = minMaxMap[columns || 5] || minMaxMap[5];

  return (
    <div
      className="grid gap-2"
      style={{ gridTemplateColumns: `repeat(auto-fill, ${minMax})` }}
    >
      {items.map((item) => (
        <div
          key={item.label}
          className={`rounded-lg px-2.5 py-1.5 text-center ${CARD_COLORS[item.color] || CARD_COLORS.slate}`}
        >
          <div className="text-lg font-bold leading-tight">{item.value}</div>
          <div className="text-[10px] opacity-70">{item.label}</div>
        </div>
      ))}
    </div>
  );
}
