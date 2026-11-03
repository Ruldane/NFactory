import type { Metadata } from "next";
import { Suspense } from "react";

import { RunView } from "@/components/run/run-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Run · NFactory" };

// The run id is runtime data under Cache Components: read it inside Suspense so the
// page shell stays static.
export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<Skeleton className="h-96 bg-navy/8" aria-label="Chargement du run" />}>
      {params.then(({ id }) => (
        <RunView runId={id} />
      ))}
    </Suspense>
  );
}
