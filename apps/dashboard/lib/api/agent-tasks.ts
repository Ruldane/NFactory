"use client";

// Data hooks for coding-agent tasks on the user's machine through the bridge, and their
// sandbox checks and their GitHub publication (tasks 4.3, 4.4, 4.6).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/lib/api/client";
import type { AgentCheck, AgentRuntime, AgentTask, LocalRepo, Publication } from "@/lib/api/types";
import { isCheckActive, isTaskActive } from "@/lib/agent-task-status";

export const agentTaskKeys = {
  repos: ["local-runtimes", "repos"] as const,
  task: (id: string) => ["local-runtimes", "tasks", id] as const,
  check: (id: string) => ["local-runtimes", "checks", id] as const,
};

export interface StartAgentTask {
  runtime: AgentRuntime;
  repoId: string;
  task: string;
}

export function useLocalRepos() {
  return useQuery({
    queryKey: agentTaskKeys.repos,
    queryFn: () => apiGet<{ repos: LocalRepo[] }>("/local-runtimes/repos"),
  });
}

export function useAgentTask(id: string | null, pollMs: number) {
  return useQuery({
    queryKey: agentTaskKeys.task(id ?? ""),
    queryFn: () => apiGet<AgentTask>(`/local-runtimes/tasks/${id}`),
    enabled: id !== null,
    // Follow a running task; stop once it has ended.
    refetchInterval: (query) => (query.state.data && !isTaskActive(query.state.data.status) ? false : pollMs),
  });
}

export function useStartAgentTask() {
  const client = useQueryClient();
  return useMutation({
    // `consent: true` is sent only from the explicit checkbox of the form.
    mutationFn: ({ runtime, repoId, task }: StartAgentTask) =>
      apiPost<AgentTask>("/local-runtimes/tasks", {
        runtime,
        repo_id: repoId,
        task,
        consent: true,
      }),
    onSuccess: (task) => client.setQueryData(agentTaskKeys.task(task.id), task),
  });
}

export function useAgentTaskAction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "cancel" | "discard" | "collect" }) =>
      apiPost<AgentTask>(`/local-runtimes/tasks/${id}/${action}`),
    onSuccess: (task) => client.setQueryData(agentTaskKeys.task(task.id), task),
  });
}

export function useStartCheck() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => apiPost<AgentCheck>(`/local-runtimes/tasks/${taskId}/checks`),
    onSuccess: (check) => client.setQueryData(agentTaskKeys.check(check.id), check),
  });
}

export function useAgentCheck(id: string | null, pollMs: number) {
  return useQuery({
    queryKey: agentTaskKeys.check(id ?? ""),
    queryFn: () => apiGet<AgentCheck>(`/local-runtimes/checks/${id}`),
    enabled: id !== null,
    refetchInterval: (query) => (query.state.data && !isCheckActive(query.state.data.status) ? false : pollMs),
  });
}

function usePublicationUpdate() {
  const client = useQueryClient();
  return (taskId: string, publication: Publication) =>
    client.setQueryData<AgentTask>(agentTaskKeys.task(taskId), (task) => (task ? { ...task, publication } : task));
}

export function usePublishTask() {
  const update = usePublicationUpdate();
  return useMutation({
    // `approve: true` is sent only from the publication checkbox, never with the launch.
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      apiPost<Publication>(`/local-runtimes/tasks/${id}/publish`, { approve: true, title }),
    onSuccess: (publication, { id }) => update(id, publication),
  });
}

export function useVerifyPublication() {
  const update = usePublicationUpdate();
  return useMutation({
    mutationFn: (id: string) => apiGet<Publication>(`/local-runtimes/tasks/${id}/publication`),
    onSuccess: (publication, id) => update(id, publication),
  });
}
