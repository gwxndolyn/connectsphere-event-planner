const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly fields: string[] = [],
  ) {
    super(code);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (import.meta.env.VITE_DEV_USER_ID && !headers.has("X-User-Id")) {
    headers.set("X-User-Id", import.meta.env.VITE_DEV_USER_ID);
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const errorBody = payload && typeof payload === "object" ? payload : {};
    const body = errorBody as { code?: unknown; fields?: unknown };
    throw new ApiError(
      response.status,
      typeof body.code === "string" ? body.code : "HTTP_ERROR",
      Array.isArray(body.fields) ? body.fields.filter((field): field is string => typeof field === "string") : [],
    );
  }

  const contentType = response.headers.get("content-type") || "";
  return (contentType.includes("application/json") ? response.json() : response.text()) as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
};
