"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api/client";
import type {
  Artifact,
  DashboardSummary,
  FileContent,
  FileList,
  Items,
  OverviewFilters,
  Page,
  Preview,
  Project,
  ProjectType,
  Recipe,
  RunDetail,
  RunLimits,
  WorkspaceSettings,
} from "@/lib/api/types";
import { isTerminalRunState } from "@/lib/run-state";

const OVERVIEW_REFRESH_MS = 15_000;
// Safety net only: live runs are refreshed by their SSE stream (lib/api/use-run-events.ts).
const ACTIVE_RUN_REFRESH_MS = 10_000;

export const runKeys = {
  all: (id: string) => ["runs", id] as const,
  detail: (id: string) => ["runs", id, "detail"] as const,
  files: (id: string) => ["runs", id, "files"] as const,
  file: (id: string, path: string) => ["runs", id, "files", path] as const,
  artifacts: (id: string) => ["runs", id, "artifacts"] as const,
  preview: (id: string) => ["runs", id, "preview"] as const,
};

export function useDashboardSummary(
  filters: OverviewFilters = { days: null, project_type: null },
) {
  const params: Record<string, string | number> = {};
  if (filters.days !== null) params.days = filters.days;
  if (filters.project_type !== null) params.project_type = filters.project_type;
  return useQuery({
    queryKey: ["dashboard", "summary", filters],
    queryFn: () =>
      apiGet<DashboardSummary>(
        "/dashboard/summary",
        Object.keys(params).length ? params : undefined,
      ),
    refetchInterval: OVERVIEW_REFRESH_MS,
  });
}

export function useProjects(type: ProjectType | null) {
  return useQuery({
    queryKey: ["projects", { type }],
    queryFn: () =>
      apiGet<Page<Project>>(
        "/projects",
        type ? { type, limit: 100 } : { limit: 100 },
      ),
  });
}

export function useRecipes() {
  return useQuery({
    queryKey: ["recipes"],
    queryFn: () => apiGet<Items<Recipe>>("/recipes"),
    staleTime: Infinity,
  });
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: runKeys.detail(runId),
    queryFn: () => apiGet<RunDetail>(`/runs/${runId}`),
    refetchInterval: (query) =>
      query.state.data && !isTerminalRunState(query.state.data.state)
        ? ACTIVE_RUN_REFRESH_MS
        : false,
  });
}

export function useRunFiles(runId: string) {
  return useQuery({
    queryKey: runKeys.files(runId),
    queryFn: () => apiGet<FileList>(`/runs/${runId}/files`),
  });
}

export function useFileContent(runId: string, path: string | null) {
  return useQuery({
    queryKey: runKeys.file(runId, path ?? ""),
    queryFn: () =>
      apiGet<FileContent>(`/runs/${runId}/files/content`, { path: path ?? "" }),
    enabled: path !== null,
  });
}

export function useRunArtifacts(runId: string) {
  return useQuery({
    queryKey: runKeys.artifacts(runId),
    queryFn: () => apiGet<Items<Artifact>>(`/runs/${runId}/artifacts`),
  });
}

export function usePreview(runId: string) {
  return useQuery({
    queryKey: runKeys.preview(runId),
    queryFn: () => apiGet<Preview>(`/runs/${runId}/preview`),
  });
}

export function useStartPreview(runId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<Preview>(`/runs/${runId}/preview`),
    onSuccess: (preview) =>
      client.setQueryData(runKeys.preview(runId), preview),
  });
}

export function useStopPreview(runId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiDelete<null>(`/runs/${runId}/preview`),
    onSuccess: () =>
      client.setQueryData<Preview>(runKeys.preview(runId), {
        running: false,
        url: null,
        expires_in_s: null,
      }),
  });
}

export function useCancelRun(runId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<RunDetail>(`/runs/${runId}/cancel`),
    onSuccess: (run) => client.setQueryData(runKeys.detail(runId), run),
  });
}

export interface ApprovalInput {
  approvalId: string;
  // null: retry the engine that failed. Otherwise switch the failed engine to this one.
  replacement: { provider: string; model: string } | null;
}

export function useApproveRun(runId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ approvalId, replacement }: ApprovalInput) =>
      apiPost<RunDetail>(
        `/runs/${runId}/approvals/${approvalId}/approve`,
        replacement ?? {},
      ),
    onSuccess: (run) => client.setQueryData(runKeys.detail(runId), run),
  });
}

export function useRejectRun(runId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (approvalId: string) =>
      apiPost<RunDetail>(`/runs/${runId}/approvals/${approvalId}/reject`),
    onSuccess: (run) => client.setQueryData(runKeys.detail(runId), run),
  });
}

export interface LaunchInput {
  title: string;
  type: ProjectType;
  request: string;
  // One key per submission: a double click or a retry never launches two runs.
  idempotencyKey: string;
}

export interface ChangeInput {
  request: string;
  idempotencyKey: string;
}

// A change request on a delivered run: a child run of the same project (scenario E).
export function useRequestChange(run: RunDetail) {
  return useMutation({
    mutationFn: ({ request, idempotencyKey }: ChangeInput) =>
      apiPost<RunDetail>(
        `/projects/${run.project.id}/runs`,
        { request, parent_run_id: run.id },
        { "Idempotency-Key": idempotencyKey },
      ),
  });
}

export function useLaunchProject() {
  return useMutation({
    mutationFn: async ({
      title,
      type,
      request,
      idempotencyKey,
    }: LaunchInput) => {
      const project = await apiPost<Project>("/projects", {
        title,
        type,
        description: request,
      });
      return apiPost<RunDetail>(
        `/projects/${project.id}/runs`,
        { request },
        { "Idempotency-Key": idempotencyKey },
      );
    },
  });
}

const settingsKey = ["settings"] as const;

export function useWorkspaceSettings() {
  return useQuery({
    queryKey: settingsKey,
    queryFn: () => apiGet<WorkspaceSettings>("/settings"),
  });
}

export function useSaveRunLimits() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (limits: RunLimits) =>
      apiPut<WorkspaceSettings>("/settings/run-limits", limits),
    onSuccess: (settings) => client.setQueryData(settingsKey, settings),
  });
}
