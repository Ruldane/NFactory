import { cn } from "cn";

import { TONE_CLASSES } from "@/components/runs/tone";
import { describeProviderStatus } from "@/lib/provider-status";

export function ProviderStatusBadge({ status }: { status: string }) {
  const { label, tone, glyph } = describeProviderStatus(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wider",
        TONE_CLASSES[tone],
      )}
    >
      <span aria-hidden>{glyph}</span>
      {label}
    </span>
  );
}
