"use client";

// Data hooks for the local coding tools (codex, claude, gh) reached through the bridge.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPost } from "@/lib/api/client";
import type { LocalRuntimesView } from "@/lib/api/types";

export const localRuntimeKeys = { list: ["local-runtimes"] as const };

export function useLocalRuntimes() {
  return useQuery({
    queryKey: localRuntimeKeys.list,
    queryFn: () => apiGet<LocalRuntimesView>("/local-runtimes"),
  });
}

export function usePairBridge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => apiPost<LocalRuntimesView>("/local-runtimes/pairing", { code }),
    onSuccess: (view) => client.setQueryData(localRuntimeKeys.list, view),
  });
}

export function useUnpairBridge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiDelete("/local-runtimes/pairing"),
    onSuccess: () => client.invalidateQueries({ queryKey: localRuntimeKeys.list }),
  });
}
