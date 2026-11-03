"use client";

import { cn } from "cn";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { isActive, NAV_ITEMS } from "@/components/shell/nav-items";

export function Sidebar() {
  return (
    <aside className="flex w-full flex-col bg-eggplant text-cream md:sticky md:top-0 md:h-dvh md:w-64 md:shrink-0">
      <div className="flex items-baseline gap-2 px-6 pt-7 pb-8">
        <span className="font-display text-3xl font-semibold tracking-tight">
          N<span className="text-coral">F</span>actory
        </span>
      </div>

      {/* usePathname is runtime data on dynamic routes: highlight once it is known. */}
      <Suspense fallback={<NavList pathname={null} />}>
        <CurrentNavList />
      </Suspense>

      <p className="px-6 py-6 font-mono text-[10px] uppercase leading-relaxed tracking-wider text-cream/45">
        Mode local · aucune donnée envoyée à un fournisseur externe
      </p>
    </aside>
  );
}

function CurrentNavList() {
  return <NavList pathname={usePathname()} />;
}

function NavList({ pathname }: { pathname: string | null }) {
  return (
  <nav aria-label="Navigation principale" className="flex-1 px-3">
    <ul className="space-y-0.5">
      {NAV_ITEMS.map((item) => {
        const active = item.ready && isActive(item.href, pathname);
        return (
          <li key={item.href}>
            {item.ready ? (
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center justify-between rounded-sm px-3 py-2 text-sm transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-butter",
                  active ? "bg-cream/10 text-cream" : "text-cream/75 hover:bg-cream/5 hover:text-cream",
                )}
              >
                {item.label}
                {active ? <span aria-hidden className="size-1.5 rounded-full bg-coral" /> : null}
              </Link>
            ) : (
              <span
                aria-disabled="true"
                className="flex items-center justify-between px-3 py-2 text-sm text-cream/40"
              >
                {item.label}
                <span className="font-mono text-[10px] uppercase tracking-wider">
                  Phase {item.phase}
                </span>
              </span>
            )}
          </li>
        );
      })}
    </ul>
  </nav>
  );
}
