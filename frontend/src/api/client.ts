import { DEV_AUTH, accessToken } from "../auth/supabase";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Development identity stub (D12), used only in dev mode (VITE_DEV_AUTH=true) without a login: the app
// acts as one of the seeded users and sends their id as X-User-Id. The header's "Acting as" switch picks which.
// Venue staff is operations_manager in the backend until US16b (D19). Tech support (SCRUM-110) is the
// real tech_support role (deviation 34).
export type DevRole = "organiser" | "coordinator" | "coordinator_lead" | "venue_staff" | "tech_support";

export const DEV_USER_IDS: Record<DevRole, string | undefined> = {
  organiser: import.meta.env.VITE_DEV_USER_ID,
  coordinator: import.meta.env.VITE_DEV_COORDINATOR_ID,
  coordinator_lead: import.meta.env.VITE_DEV_LEAD_ID,
  venue_staff: import.meta.env.VITE_DEV_VENUE_STAFF_ID,
  tech_support: import.meta.env.VITE_DEV_TECH_SUPPORT_ID,
};

// The Sprint 1 attendee routes (events board, register, withdraw, My Events) identify the caller
// by X-Attendee-Id instead (§3). One seeded attendee for now; Supabase Auth replaces both stubs.
export const DEV_ATTENDEE_ID: string | undefined = import.meta.env.VITE_DEV_ATTENDEE_ID;

// "none": no identity header, for routes that take none (joining a waitlist by email, D7).
export type Identity = "user" | "attendee" | "none";

interface RequestOptions extends RequestInit {
  identity?: Identity;
}

const DEV_ROLE_KEY = "connectsphere.devRole";

function readStoredRole(): DevRole {
  try {
    const stored = localStorage.getItem(DEV_ROLE_KEY);
    return stored === "coordinator" || stored === "coordinator_lead" || stored === "venue_staff" || stored === "tech_support"
      ? stored
      : "organiser";
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
    // The whole error payload, for codes that carry more than `fields` (e.g. EVENT_FULL's
    // waitlist_available).
    readonly body: Record<string, unknown> = {},
  ) {
    super(code);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, { identity = "user", ...options }: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  // Logged in: the Supabase token identifies the caller, never the dev stubs (TC-US16A-39).
  const token = identity === "none" ? null : await accessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else if (!DEV_AUTH) {
    // Not logged in and no dev stubs: send no identity.
  } else if (identity === "attendee") {
    if (DEV_ATTENDEE_ID && !headers.has("X-Attendee-Id")) headers.set("X-Attendee-Id", DEV_ATTENDEE_ID);
  } else if (identity === "user") {
    const devUserId = DEV_USER_IDS[devRole];
    if (devUserId && !headers.has("X-User-Id")) {
      headers.set("X-User-Id", devUserId);
    }
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
      errorBody as Record<string, unknown>,
    );
  }

  const contentType = response.headers.get("content-type") || "";
  return (contentType.includes("application/json") ? response.json() : response.text()) as Promise<T>;
}

export const apiClient = {
  get: <T>(path: string, identity?: Identity) => request<T>(path, { identity }),
  post: <T>(path: string, body: unknown, identity?: Identity) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body), identity }),
  patch: <T>(path: string, body: unknown, identity?: Identity) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body), identity }),
  // A 204 has no body, so this resolves to "".
  delete: <T = string>(path: string, identity?: Identity) => request<T>(path, { method: "DELETE", identity }),
};
