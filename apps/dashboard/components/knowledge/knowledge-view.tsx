"use client";

import { DocumentList } from "@/components/knowledge/document-list";
import { EnginePanel } from "@/components/knowledge/engine-panel";
import { SearchPanel } from "@/components/knowledge/search-panel";
import { UploadForm } from "@/components/knowledge/upload-form";

// The "Base de connaissances" page: search first, then the documents, then the engine.
export function KnowledgeView() {
  return (
    <div className="space-y-12">
      <SearchPanel />
      <section aria-labelledby="documents-title" className="space-y-5">
        <div>
          <h2 id="documents-title" className="font-display text-2xl text-navy">
            Documents
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-navy/70">
            Markdown, texte, code, PDF ou Word, 10 Mo au maximum. Un document rattaché à un projet
            n&apos;est lu que par les runs de ce projet ; sans projet, il sert à tout l&apos;espace.
          </p>
        </div>
        <UploadForm />
        <DocumentList />
      </section>
      <EnginePanel />
    </div>
  );
}
