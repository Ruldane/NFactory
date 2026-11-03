import { cn } from "cn";

import type { ProjectType, Recipe } from "@/lib/api/types";

interface RecipePickerProps {
  recipes: Recipe[];
  value: ProjectType | null;
  onChange: (type: ProjectType) => void;
}

// One card per catalog entry. Types not built yet stay visible but disabled, with the
// phase that delivers them (honest status, spec §20).
export function RecipePicker({ recipes, value, onChange }: RecipePickerProps) {
  const ordered = [...recipes].sort(
    (a, b) => Number(b.available) - Number(a.available) || a.phase - b.phase,
  );
  return (
    <fieldset>
      <legend className="font-mono text-[11px] uppercase tracking-[0.2em] text-navy/60">
        Type de livrable
      </legend>
      <div className="mt-3 grid gap-px overflow-hidden border border-navy/10 bg-navy/10 sm:grid-cols-2 lg:grid-cols-3">
        {ordered.map((recipe) => {
          const checked = recipe.project_type === value;
          return (
            <label
              key={recipe.kind}
              className={cn(
                "relative flex flex-col gap-2 bg-cream p-4 transition-colors",
                recipe.available ? "cursor-pointer hover:bg-butter/25" : "cursor-not-allowed",
                checked && "bg-butter/40 shadow-[inset_4px_0_0_var(--color-coral-deep)]",
                "has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-coral-deep",
              )}
            >
              <input
                type="radio"
                name="project-type"
                value={recipe.project_type}
                checked={checked}
                disabled={!recipe.available}
                onChange={() => onChange(recipe.project_type)}
                className="sr-only"
              />
              <span className="flex items-center justify-between gap-2">
                <span
                  className={cn(
                    "font-display text-lg leading-tight",
                    recipe.available ? "text-navy" : "text-navy/45",
                  )}
                >
                  {recipe.label}
                </span>
                {checked ? (
                  <span aria-hidden className="font-mono text-sm text-coral-deep">
                    ●
                  </span>
                ) : null}
              </span>
              <span className={cn("text-sm", recipe.available ? "text-navy/70" : "text-navy/40")}>
                {recipe.description}
              </span>
              <span className="mt-auto flex flex-wrap items-center gap-1.5 pt-1 font-mono text-[10px] uppercase tracking-wider">
                <span className="rounded-sm border border-navy/20 px-1.5 py-0.5 text-navy/70">
                  {recipe.deliverable === "code" ? "Code" : "Non-code"}
                </span>
                {recipe.outputs.map((output) => (
                  <span key={output} className="text-navy/50">
                    {output}
                  </span>
                ))}
                {recipe.available ? null : (
                  <span className="ml-auto rounded-sm bg-navy/8 px-1.5 py-0.5 text-navy/60">
                    Phase {recipe.phase}
                  </span>
                )}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
