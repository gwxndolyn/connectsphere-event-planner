const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Development identity stub (D12): no login until Supabase Auth, so the app acts as one of the
// seeded users and sends their id as X-User-Id. The header's "Acting as" switch picks which.
export type DevRole = "organiser" | "coordinator";

export const DEV_USER_IDS: Record<DevRole, string | undefined> = {
  organiser: import.meta.env.VITE_DEV_USER_ID,
  coordinator: import.meta.env.VITE_DEV_COORDINATOR_ID,
};

const DEV_ROLE_KEY = "connectsphere.devRole";

function readStoredRole(): DevRole {
  try {
    return localStorage.getItem(DEV_ROLE_KEY) === "coordinator" ? "coordinator" : "organiser";
  } catch {
    return "organiser";
  }
}

let devRole: DevRole = readStoredRole();

export function getDevRole(): DevRole {
  return devRole;
}

export function setDevRole(role: DevRole) {
  devRole = role;
  try {
    localStorage.setItem(DEV_ROLE_KEY, role);
  } catch {
    // Storage can be unavailable (private windows); the choice then lasts until reload.
  }
}

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
  const devUserId = DEV_USER_IDS[devRole];
  if (devUserId && !headers.has("X-User-Id")) {
    headers.set("X-User-Id", devUserId);
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
