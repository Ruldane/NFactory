"use client";

// Data hooks for the "Moteurs IA" page: connections, tests, model catalog, routing.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api/client";
import type {
  CatalogModel,
  Pricing,
  ProviderConfigInput,
  ProviderView,
  RoutingConfig,
  RoutingView,
  ValidationResult,
} from "@/lib/api/types";

export const providerKeys = {
  list: ["providers"] as const,
  models: (kind: string) => ["providers", kind, "models"] as const,
  routing: ["routing"] as const,
};

export function useProviders() {
  return useQuery({
    queryKey: providerKeys.list,
    queryFn: async () => (await apiGet<{ providers: ProviderView[] }>("/providers")).providers,
  });
}

export function useConfigureProvider(kind: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: ProviderConfigInput) =>
      apiPut<ProviderView>(`/providers/${kind}/configuration`, input),
    onSuccess: () => client.invalidateQueries({ queryKey: providerKeys.list }),
  });
}

export function useRemoveProvider(kind: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiDelete<ProviderView>(`/providers/${kind}/configuration`),
    onSuccess: () => client.invalidateQueries({ queryKey: providerKeys.list }),
  });
}

export function useValidateProvider(kind: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<ValidationResult>(`/providers/${kind}/validate`),
    onSettled: () => {
      client.invalidateQueries({ queryKey: providerKeys.list });
      client.invalidateQueries({ queryKey: providerKeys.models(kind) });
    },
  });
}

export function useCatalog(kind: string, enabled = true) {
  return useQuery({
    queryKey: providerKeys.models(kind),
    queryFn: async () =>
      (await apiGet<{ models: CatalogModel[] }>(`/providers/${kind}/models`)).models,
    enabled,
  });
}

const modelPath = (kind: string, modelId: string) =>
  `/providers/${kind}/models/${modelId.split("/").map(encodeURIComponent).join("/")}`;

export function useSaveModel(kind: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ modelId, pricing }: { modelId: string; pricing: Pricing | null }) =>
      apiPut<CatalogModel>(modelPath(kind, modelId), { pricing }),
    onSuccess: () => client.invalidateQueries({ queryKey: providerKeys.models(kind) }),
  });
}

export function useDeleteModel(kind: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (modelId: string) => apiDelete<{ removed: string }>(modelPath(kind, modelId)),
    onSuccess: () => client.invalidateQueries({ queryKey: providerKeys.models(kind) }),
  });
}

export function useRouting() {
  return useQuery({
    queryKey: providerKeys.routing,
    queryFn: () => apiGet<RoutingView>("/routing"),
  });
}

export function useSaveRouting() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (routing: RoutingConfig) => apiPut<RoutingView>("/routing", routing),
    onSuccess: (view) => client.setQueryData(providerKeys.routing, view),
  });
}
