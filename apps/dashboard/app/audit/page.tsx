import type { Metadata } from "next";

import { ApprovalCenter } from "@/components/audit/approval-center";

export const metadata: Metadata = { title: "Approbations & audit · NFactory" };

export default function AuditPage() {
  return (
    <div className="space-y-10">
      <header className="nf-rise">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-coral-deep">
          Centre d&apos;approbation
        </p>
        <h1 className="mt-2 font-display text-5xl text-navy">
          Ce qui attend votre accord
        </h1>
        <p className="mt-3 max-w-2xl text-navy/70">
          Les décisions humaines en attente, puis la trace de chaque action
          sensible : qui, quoi, quand et avec quelle décision.
        </p>
      </header>
      <div className="nf-rise [animation-delay:80ms]">
        <ApprovalCenter />
      </div>
    </div>
  );
}
