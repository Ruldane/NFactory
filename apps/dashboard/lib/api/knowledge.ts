"use client";

// Data hooks for the knowledge base: documents, upload, search, embedding engine.

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPut, apiUpload } from "@/lib/api/client";
import type {
  EmbeddingChoice,
  KnowledgeDocument,
  KnowledgeDocumentDetail,
  KnowledgeSearch,
  KnowledgeSettings,
  UploadResult,
} from "@/lib/api/types";

// While vectors are being computed, the list and the progress refresh on their own.
const INDEXING_REFRESH_MS = 3000;

export const knowledgeKeys = {
  all: ["knowledge"] as const,
  documents: (projectId: string | null) => ["knowledge", "documents", { projectId }] as const,
  document: (id: string) => ["knowledge", "document", id] as const,
  search: (q: string, projectId: string | null) => ["knowledge", "search", { q, projectId }] as const,
  settings: ["knowledge", "settings"] as const,
};

export function useDocuments(projectId: string | null) {
  return useQuery({
    queryKey: knowledgeKeys.documents(projectId),
    queryFn: async () =>
      (
        await apiGet<{ items: KnowledgeDocument[] }>(
          "/knowledge/documents",
          projectId ? { project_id: projectId } : undefined,
        )
      ).items,
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.embedded < d.chunks) ? INDEXING_REFRESH_MS : false,
  });
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: knowledgeKeys.document(id),
    queryFn: () => apiGet<KnowledgeDocumentDetail>(`/knowledge/documents/${id}`),
  });
}

export function useUploadDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ file, projectId }: { file: File; projectId: string | null }) => {
      const form = new FormData();
      form.append("file", file);
      if (projectId) form.append("project_id", projectId);
      return apiUpload<UploadResult>("/knowledge/documents", form);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: knowledgeKeys.all }),
  });
}

export function useDeleteDocument() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiDelete<null>(`/knowledge/documents/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: knowledgeKeys.all }),
  });
}

export function useKnowledgeSearch(q: string, projectId: string | null) {
  return useQuery({
    queryKey: knowledgeKeys.search(q, projectId),
    queryFn: () =>
      apiGet<KnowledgeSearch>("/knowledge/search", projectId ? { q, project_id: projectId } : { q }),
    enabled: q.trim().length > 0,
    placeholderData: keepPreviousData,
  });
}

export function useKnowledgeSettings() {
  return useQuery({
    queryKey: knowledgeKeys.settings,
    queryFn: () => apiGet<KnowledgeSettings>("/knowledge/settings"),
    refetchInterval: (query) => {
      const index = query.state.data?.index;
      return index && index.embedded < index.total && !query.state.data?.index_error
        ? INDEXING_REFRESH_MS
        : false;
    },
  });
}

export function useSaveEmbedding() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (embedding: EmbeddingChoice) =>
      apiPut<KnowledgeSettings>("/knowledge/settings", { embedding }),
    onSuccess: () => client.invalidateQueries({ queryKey: knowledgeKeys.all }),
  });
}
