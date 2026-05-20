import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";

interface Props {
  label?: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  placeholder?: string;
  shortcuts?: number[];
  disabled?: boolean;
  className?: string;
}

export default function NumberCombo({
  label,
  value,
  onChange,
  min = 1,
  max,
  placeholder,
  shortcuts = [5, 10, 30, 50, 100],
  disabled = false,
  className = "",
}: Props) {
  const [open, setOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const updatePosition = useCallback(() => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const menuHeight = shortcuts.length * 28 + 8;
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const dropUp = spaceBelow < menuHeight && spaceAbove >= menuHeight;
    setMenuStyle({
      position: "fixed",
      left: rect.left,
      minWidth: rect.width,
      ...(dropUp ? { bottom: window.innerHeight - rect.top + 4 } : { top: rect.bottom + 4 }),
    });
  }, [shortcuts.length]);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    const onScroll = () => updatePosition();
    const onClick = (e: MouseEvent) => {
      if (ref.current?.contains(e.target as Node) || menuRef.current?.contains(e.target as Node))
        return;
      setOpen(false);
    };
    window.addEventListener("scroll", onScroll, true);
    document.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, updatePosition]);

  const toggleOpen = useCallback(() => {
    if (disabled) return;
    setOpen((prev) => !prev);
  }, [disabled]);

  return (
    <div className={`${label ? "space-y-1.5" : ""} ${className}`}>
      {label && <label className="text-xs font-medium text-slate-500">{label}</label>}
      <div ref={ref}>
        <div className="relative">
          <input
            type="number"
            min={min}
            max={max}
            value={value}
            onChange={(e) => {
              const v = parseInt(e.target.value);
              onChange(isNaN(v) ? min : Math.max(min, max ? Math.min(v, max) : v));
            }}
            disabled={disabled}
            placeholder={placeholder}
            className="[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none w-full h-8 rounded-md border border-slate-200 bg-slate-50 pl-3 pr-7 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-500/20 focus:border-slate-400 transition-all disabled:opacity-50"
          />
          {shortcuts.length > 0 && (
            <button
              type="button"
              onClick={toggleOpen}
              disabled={disabled}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center justify-center text-slate-400 hover:text-slate-600 cursor-pointer disabled:opacity-40"
            >
              <svg
                className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>
          )}
        </div>
      </div>
      {open &&
        createPortal(
          <div
            ref={menuRef}
            style={menuStyle}
            className="z-50 bg-white border border-slate-200 rounded-md shadow-lg py-1"
          >
            {shortcuts.map((s) => (
              <button
                key={s}
                onClick={() => {
                  onChange(s);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-1.5 text-xs cursor-pointer transition-colors ${
                  value === s
                    ? "text-blue-600 bg-blue-50 font-medium"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {s}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </div>
  );
}
