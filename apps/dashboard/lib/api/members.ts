"use client";

// A member's rights (ADR-0015): the member list and erasure. The export of one's own data
// is a plain download link (MY_DATA_URL), so the browser saves the JSON file itself.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { API_BASE, apiDelete, apiGet } from "@/lib/api/client";
import type { Erasure, Items, Member } from "@/lib/api/types";

export const MY_DATA_URL = `${API_BASE}/me/export`;

const membersKey = ["members"] as const;

export function useMembers(enabled: boolean) {
  return useQuery({
    queryKey: membersKey,
    enabled,
    queryFn: () => apiGet<Items<Member>>("/members"),
  });
}

export function useEraseMember() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => apiDelete<Erasure>(`/members/${userId}`),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: membersKey });
      void client.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}
