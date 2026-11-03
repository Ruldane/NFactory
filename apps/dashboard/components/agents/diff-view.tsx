// A unified diff, line by line. The +/- prefix stays visible: color only underlines it.
// Ligatures are off: a reviewer must read `->` and `==` as typed, not as arrows.

import { cn } from "cn";

function lineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff --git")) {
    return "text-navy/55";
  }
  if (line.startsWith("@@")) return "text-eggplant/80";
  if (line.startsWith("+")) return "bg-forest/10 text-forest";
  if (line.startsWith("-")) return "bg-coral-deep/8 text-coral-deep";
  return "text-navy/80";
}

export function DiffView({ diff, truncated }: { diff: string; truncated: boolean }) {
  const lines = diff.replace(/\n$/, "").split("\n");
  return (
    <div className="space-y-2">
      <pre
        aria-label="Diff"
        className="max-h-[32rem] overflow-auto border border-navy/15 bg-cream/70 py-2 font-mono text-[12.5px] leading-relaxed [font-variant-ligatures:none]"
      >
        {lines.map((line, index) => (
          <div key={index} className={cn("px-4 whitespace-pre", lineClass(line))}>
            {line || " "}
          </div>
        ))}
      </pre>
      {truncated ? <p className="text-sm text-navy/60">Diff tronqué : il est trop long pour être affiché en entier.</p> : null}
    </div>
  );
}
