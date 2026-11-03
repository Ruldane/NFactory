import type { RunDetail } from "@/lib/api/types";

interface ExplanationData {
  summary: string;
  generated: string[];
  verify: string[];
  limits: string[];
}

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

// The documenter's output is agent-generated JSON: read it defensively.
function explanationOf(run: RunDetail): ExplanationData | null {
  const raw = run.steps.find((step) => step.name === "docs")?.output?.explanation;
  if (!raw || typeof raw !== "object") return null;
  const data = raw as Record<string, unknown>;
  if (typeof data.summary !== "string") return null;
  return {
    summary: data.summary,
    generated: strings(data.generated),
    verify: strings(data.verify),
    limits: strings(data.limits),
  };
}

function Section({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  const id = `explanation-${title.replace(/\W+/g, "-")}`;
  return (
    <section className="space-y-2">
      <h3 id={id} className="font-display text-xl text-eggplant">
        {title}
      </h3>
      {items.length > 0 ? (
        <ul aria-labelledby={id} className="list-disc space-y-1 pl-5">
          {items.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-navy/60">{empty}</p>
      )}
    </section>
  );
}

// Explain mode (spec §1.1): what was generated, what to check, what the limits are.
// Rendered from the documentation step's structured output; the same text is shipped
// in the ZIP as EXPLICATION.md.
export function Explanation({ run }: { run: RunDetail }) {
  const explanation = explanationOf(run);
  if (!explanation) {
    return (
      <p className="border border-dashed border-navy/25 px-6 py-8 text-center text-sm text-navy/70">
        L&apos;explication est rédigée à l&apos;étape Documentation.
      </p>
    );
  }
  return (
    <article className="max-w-3xl space-y-6 border-l-4 border-butter bg-butter/15 px-6 py-5 text-[15px] leading-relaxed text-navy">
      <p className="text-lg">{explanation.summary}</p>
      <Section title="Ce qui a été produit" items={explanation.generated} empty="Rien de listé." />
      <Section
        title="À vérifier avant utilisation"
        items={explanation.verify}
        empty="Rien de listé."
      />
      <Section title="Limites connues" items={explanation.limits} empty="Aucune limite signalée." />
    </article>
  );
}
