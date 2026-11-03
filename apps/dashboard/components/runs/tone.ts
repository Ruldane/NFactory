import type { Tone } from "@/lib/run-state";

// Tone -> Tailwind classes, built on the palette tokens in globals.css.
// Text colors were picked for WCAG AA contrast on the cream background.
export const TONE_CLASSES: Record<Tone, string> = {
  success: "bg-forest/12 text-forest border-forest/30",
  danger: "bg-coral-deep/10 text-coral-deep border-coral-deep/35",
  attention: "bg-butter/45 text-eggplant border-butter",
  active: "bg-coral/15 text-coral-deep border-coral/40",
  neutral: "bg-navy/6 text-navy/75 border-navy/15",
};
