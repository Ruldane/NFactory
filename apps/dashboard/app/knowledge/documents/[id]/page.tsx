import type { Metadata } from "next";
import { Suspense } from "react";

import { DocumentViewer } from "@/components/knowledge/document-viewer";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Document · NFactory" };

// The document id and the cited lines are runtime data under Cache Components: read
// them inside Suspense so the page shell stays static.
export default function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<Skeleton className="h-96 bg-navy/8" aria-label="Chargement du document" />}>
      {params.then(({ id }) => (
        <DocumentViewer documentId={id} />
      ))}
    </Suspense>
  );
}
