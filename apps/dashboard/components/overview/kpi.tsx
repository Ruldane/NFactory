import { cn } from "cn";
import { useId } from "react";

interface KpiProps {
  label: string;
  value: string;
  hint?: string;
  highlight?: boolean;
}

// Fixed rows (label / value / hint) keep every value on the same baseline across the row.
export function Kpi({ label, value, hint, highlight = false }: KpiProps) {
  const labelId = useId();
  return (
    <div
      role="group"
      aria-labelledby={labelId}
      className={cn(
        "grid grid-rows-[2.25rem_auto_1.25rem] gap-y-3 border-t-2 px-1 pt-3",
        highlight ? "border-coral-deep" : "border-navy/80",
      )}
    >
      <span
        id={labelId}
        className="font-mono text-[11px] uppercase leading-snug tracking-[0.14em] text-navy/70"
      >
        {label}
      </span>
      <span className="whitespace-nowrap font-display text-[2rem] leading-none text-navy tabular-nums">
        {value}
      </span>
      <span className="truncate text-xs text-navy/60">{hint}</span>
    </div>
  );
}
