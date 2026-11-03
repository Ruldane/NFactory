"use client";

// Reusable factory recipes (spec F38): save a delivered run, replay it as a new run.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPost } from "@/lib/api/client";
import type { Items, RunDetail, SavedRecipe } from "@/lib/api/types";

const recipeKeys = { all: ["saved-recipes"] as const };

export function useSavedRecipes() {
  return useQuery({
    queryKey: recipeKeys.all,
    queryFn: () => apiGet<Items<SavedRecipe>>("/saved-recipes"),
  });
}

export interface SaveInput {
  runId: string;
  name: string;
}

export function useSaveRecipe() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, name }: SaveInput) =>
      apiPost<SavedRecipe>("/saved-recipes", { run_id: runId, name }),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: recipeKeys.all }),
  });
}

export interface ReplayInput {
  recipeId: string;
  // One key per click: a double click or a retry never launches two runs.
  idempotencyKey: string;
}

export function useReplayRecipe() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ recipeId, idempotencyKey }: ReplayInput) =>
      apiPost<RunDetail>(
        `/saved-recipes/${recipeId}/launch`,
        {},
        { "Idempotency-Key": idempotencyKey },
      ),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: recipeKeys.all }),
  });
}

export function useDeleteRecipe() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (recipeId: string) =>
      apiDelete<null>(`/saved-recipes/${recipeId}`),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: recipeKeys.all }),
  });
}
