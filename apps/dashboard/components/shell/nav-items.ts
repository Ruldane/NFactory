// Navigation from spec §9.2. Screens not built yet are listed with the phase that
// delivers them instead of linking to placeholder pages.

export interface NavItem {
  href: string;
  label: string;
  phase: number;
  ready: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Vue d'ensemble", phase: 0, ready: true },
  { href: "/projects", label: "Projets", phase: 0, ready: true },
  { href: "/new", label: "Nouveau projet", phase: 1, ready: true },
  { href: "/live", label: "Usine en direct", phase: 1, ready: true },
  { href: "/providers", label: "Moteurs IA", phase: 2, ready: true },
  { href: "/knowledge", label: "Base de connaissances", phase: 3, ready: true },
  { href: "/evaluations", label: "Évaluations", phase: 5, ready: false },
  { href: "/audit", label: "Audit & sécurité", phase: 5, ready: false },
  { href: "/settings", label: "Réglages", phase: 1, ready: true },
];

// A section stays highlighted on its sub-pages (a run, a cited document).
export function isActive(href: string, pathname: string | null): boolean {
  if (!pathname) return false;
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
