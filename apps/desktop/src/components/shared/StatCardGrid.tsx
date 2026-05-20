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

export default function StatCardGrid({ items, columns = 5 }: Props) {
  const gridCols: Record<number, string> = {
    2: "grid-cols-2",
    3: "grid-cols-3",
    4: "grid-cols-4",
    5: "grid-cols-5",
    6: "grid-cols-6",
  };

  return (
    <div className={`grid ${gridCols[columns] || gridCols[5]} gap-2`}>
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
