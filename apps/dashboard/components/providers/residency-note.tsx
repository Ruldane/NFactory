// Where an engine processes the data it receives (ADR-0016): a glyph and a French label,
// the provider's own page as source, and any condition the user must meet.

import type { Residency, Zone } from "@/lib/api/types";

export const ZONES: Record<Zone, { glyph: string; label: string }> = {
  local: { glyph: "⌂", label: "Local" },
  eu: { glyph: "●", label: "UE" },
  outside_eu: { glyph: "▲", label: "Hors UE" },
  unknown: { glyph: "?", label: "Pays non documenté" },
};

export function residencyText({ zone, country }: { zone: Zone; country: string }): string {
  const { glyph, label } = ZONES[zone];
  return zone === "unknown" ? `${glyph} ${label}` : `${glyph} ${label} · ${country}`;
}

export function regionOption(region: { label: string; zone: Zone; country: string }): string {
  const zone = ZONES[region.zone].label;
  return region.label.includes(region.country)
    ? `${region.label} · ${zone}`
    : `${region.label} · ${region.country}, ${zone}`;
}

export function ResidencyNote({ residency }: { residency: Residency }) {
  return (
    <div className="space-y-1 text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-navy/60">
          Traitement des données
        </span>
        <span className="text-navy">{residencyText(residency)}</span>
        {residency.source ? (
          <a
            href={residency.source}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-navy/60 underline-offset-2 hover:underline"
          >
            Source
          </a>
        ) : null}
      </p>
      {residency.note ? <p className="text-xs text-navy/70">{residency.note}</p> : null}
    </div>
  );
}
