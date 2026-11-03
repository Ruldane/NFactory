// French display formatters. `null` means "not measurable yet" and is shown as such,
// never as a misleading zero.

const DASH = "—";

const percent = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 0 });
const usd = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "USD" });
const dateTime = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" });

export function formatPercent(ratio: number | null): string {
  return ratio === null ? DASH : percent.format(ratio);
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return DASH;
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h} h ${String(m).padStart(2, "0")} min`;
  if (m > 0) return `${m} min ${s} s`;
  return `${s} s`;
}

export function formatCost(usdAmount: number | null): string {
  return usdAmount === null ? "Non mesuré" : usd.format(usdAmount);
}

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

const STEP_NAMES: Record<string, string> = {
  requirements: "Besoins",
  plan: "Plan",
  architect: "Architecture",
  build: "Construction",
  checks: "Vérifications",
  tests: "Tests",
  review: "Revue",
  docs: "Documentation",
  package: "Livraison",
};

export function formatStepName(name: string): string {
  return STEP_NAMES[name] ?? name;
}

const oneDecimal = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${oneDecimal.format(bytes / 1024)} Ko`;
  return `${oneDecimal.format(bytes / (1024 * 1024))} Mo`;
}

const latency = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

// A model call's latency, in seconds with one decimal.
export function formatLatency(seconds: number | null): string {
  if (seconds === null) return "Non mesuré";
  return seconds > 0 && seconds < 0.05 ? "< 0,1 s" : `${latency.format(seconds)} s`;
}

// Token counts of a group of calls; null when no call reported them.
export function formatTokens(input: number | null, output: number | null): string {
  if (input === null && output === null) return "Non mesuré";
  return `${input ?? "—"} / ${output ?? "—"}`;
}

// A delay that may not be recorded at all.
export function formatWait(seconds: number | null): string {
  return seconds === null ? "Non mesuré" : formatDuration(seconds);
}

// The cost of a group of calls; "partiel" when some calls had no known price.
export function formatCallCost(usdAmount: number | null, complete: boolean): string {
  if (usdAmount === null) return "Non mesuré";
  return complete ? usd.format(usdAmount) : `${usd.format(usdAmount)} (partiel)`;
}
