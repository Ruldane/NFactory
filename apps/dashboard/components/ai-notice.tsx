import type { ReactNode } from "react";

// AI Act, article 50: say plainly that AI agents do the work and that what they
// deliver is AI-generated (ADR-0014). A glyph plus text, never color alone.
export function AiNotice({ children }: { children: ReactNode }) {
  return (
    <p
      role="note"
      className="border-l-4 border-butter bg-butter/25 px-4 py-3 text-sm text-navy"
    >
      <span aria-hidden="true" className="mr-2 font-mono">
        IA
      </span>
      {children}
    </p>
  );
}
