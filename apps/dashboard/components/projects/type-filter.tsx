import { cn } from "cn";

import { PROJECT_TYPE_LABELS, PROJECT_TYPES } from "@/components/projects/project-types";
import type { ProjectType } from "@/lib/api/types";

interface TypeFilterProps {
  value: ProjectType | null;
  onChange: (value: ProjectType | null) => void;
}

const OPTIONS: { value: ProjectType | null; label: string }[] = [
  { value: null, label: "Tous" },
  ...PROJECT_TYPES.map((t) => ({ value: t, label: PROJECT_TYPE_LABELS[t] })),
];

export function TypeFilter({ value, onChange }: TypeFilterProps) {
  return (
    <div role="radiogroup" aria-label="Filtrer par type" className="flex flex-wrap gap-2">
      {OPTIONS.map((option) => {
        const checked = option.value === value;
        return (
          <button
            key={option.label}
            type="button"
            role="radio"
            aria-checked={checked}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-sm border px-3 py-1 font-mono text-[11px] uppercase tracking-wider transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-coral-deep",
              checked
                ? "border-eggplant bg-eggplant text-cream"
                : "border-navy/20 text-navy/75 hover:border-navy/50",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
