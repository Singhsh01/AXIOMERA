"use client";
import useSWR, { SWRConfiguration } from "swr";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    credentials: "include",
    ...init,
    headers: init?.body instanceof FormData ? init?.headers : { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (res.status === 401 && typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
    location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export const post = <T = any>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body ?? {}) });
export const patch = <T = any>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const put = <T = any>(path: string, body: unknown) => api<T>(path, { method: "PUT", body: JSON.stringify(body) });

export function useApi<T = any>(path: string | null, opts: SWRConfiguration & { live?: number } = {}) {
  const { live, ...rest } = opts;
  return useSWR<T>(path, (p: string) => api<T>(p), { refreshInterval: live, revalidateOnFocus: true, ...rest });
}
