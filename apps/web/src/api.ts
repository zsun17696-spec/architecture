export type Client = "admin" | "flutter" | "tauri" | "electron";

export function readClient(): Client {
  const raw = new URLSearchParams(location.search).get("client") || "admin";
  if (raw === "flutter" || raw === "tauri" || raw === "electron" || raw === "admin") return raw;
  return "admin";
}

function role(): string {
  return readClient() === "admin" ? "admin" : "user";
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Role", role());
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => req<{ ok: boolean; chunks: number }>("/health"),
  projects: () => req<Record<string, unknown>[]>("/v1/projects"),
  documents: () => req<Record<string, unknown>[]>("/v1/documents"),
  patchDocument: (id: string, body: object) =>
    req<Record<string, unknown>>(`/v1/documents/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  chunks: (q = "") => req<Record<string, unknown>[]>(`/v1/chunks${q}`),
  patchMandatory: (id: number, body: object) =>
    req<Record<string, unknown>>(`/v1/chunks/${id}/mandatory`, { method: "PATCH", body: JSON.stringify(body) }),
  reviews: () => req<Record<string, unknown>[]>("/v1/reviews"),
  traces: () => req<Record<string, unknown>[]>("/v1/traces"),
  trace: (id: string) => req<Record<string, unknown>>(`/v1/traces/${id}`),
  evalLatest: () => req<Record<string, unknown>>("/v1/eval/latest"),
  ask: (body: object) => req<Record<string, unknown>>("/v1/ask", { method: "POST", body: JSON.stringify(body) }),
  chunk: (id: number) => req<Record<string, unknown>>(`/v1/chunks/${id}`),
};

export function pageSrc(docId: string, page: number): string {
  const n = String(page).padStart(3, "0");
  return `/media/pages/${encodeURIComponent(docId)}/p${n}.jpg`;
}

export function ensureClientParam(client: Client): void {
  const url = new URL(location.href);
  if (url.searchParams.get("client") !== client) {
    url.searchParams.set("client", client);
    history.replaceState(null, "", url.toString());
  }
}
