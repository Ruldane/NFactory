"use client";

// The caller's rights, the approval center and the audit log (task 5.4).

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiGet, apiPost } from "@/lib/api/client";
import type {
  ApprovalItem,
  AuditPage,
  Items,
  Me,
  Permission,
} from "@/lib/api/types";

const PENDING_REFRESH_MS = 15_000;

export const accessKeys = {
  me: ["me"] as const,
  approvals: ["approvals", "pending"] as const,
  audit: ["audit"] as const,
};

export function useMe() {
  return useQuery({
    queryKey: accessKeys.me,
    queryFn: () => apiGet<Me>("/me"),
  });
}

// The default workspace is the first one listed; local mode has exactly one.
export function can(me: Me | undefined, permission: Permission): boolean {
  return me?.workspaces[0]?.permissions.includes(permission) ?? false;
}

export function usePendingApprovals() {
  return useQuery({
    queryKey: accessKeys.approvals,
    queryFn: () =>
      apiGet<Items<ApprovalItem>>("/approvals", { status: "pending" }),
    refetchInterval: PENDING_REFRESH_MS,
  });
}

export function useAuditLog(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: accessKeys.audit,
    enabled,
    initialPageParam: null as number | null,
    queryFn: ({ pageParam }) =>
      apiGet<AuditPage>(
        "/audit",
        pageParam === null ? { limit: 50 } : { limit: 50, before: pageParam },
      ),
    getNextPageParam: (page) => page.next_before,
  });
}

export interface Decision {
  item: ApprovalItem;
  approve: boolean;
}

// Retry the same engine or stop the run; choosing a replacement engine happens on the run.
export function useDecide() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ item, approve }: Decision) =>
      apiPost<unknown>(
        `/runs/${item.run_id}/approvals/${item.id}/${approve ? "approve" : "reject"}`,
        approve ? {} : undefined,
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: accessKeys.approvals });
      void client.invalidateQueries({ queryKey: accessKeys.audit });
    },
  });
}
