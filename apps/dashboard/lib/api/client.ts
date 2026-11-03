// Browser-side API client. Requests go to /api/v1 on the dashboard origin; Next rewrites
// proxy them to the FastAPI service (see next.config.ts), so no CORS in normal use.

import type { ApiErrorBody } from "@/lib/api/types";

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const UNREACHABLE = "L'API NFactory ne répond pas. Vérifiez que les services sont démarrés.";

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "network_error", UNREACHABLE);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as ApiErrorBody | null)?.error;
    throw new ApiError(response.status, error?.code ?? "http_error", error?.message ?? UNREACHABLE);
  }
  return body as T;
}

export function apiGet<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const query = params
    ? `?${new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))}`
    : "";
  return request<T>(`${path}${query}`, { headers: { Accept: "application/json" } });
}

export function apiPost<T>(
  path: string,
  body?: unknown,
  headers: Record<string, string> = {},
): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json", ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE", headers: { Accept: "application/json" } });
}

// Multipart upload: the browser sets the Content-Type boundary itself.
export function apiUpload<T>(path: string, form: FormData): Promise<T> {
  return request<T>(path, { method: "POST", headers: { Accept: "application/json" }, body: form });
}
