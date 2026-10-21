import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// client.ts reads the stored "Acting as" role when it loads, so each test imports a fresh copy.
async function loadClient() {
  vi.resetModules();
  return import("./client");
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let fetchMock: ReturnType<typeof vi.fn>;

function sentHeaders(call = 0): Headers {
  return fetchMock.mock.calls[call][1].headers as Headers;
}

beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.resetModules();
});

describe("apiClient identity headers", () => {
  it("sends the organiser's X-User-Id by default", async () => {
    const { apiClient } = await loadClient();
    await apiClient.get("/api/v1/me/event-requests");

    expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/me/event-requests", expect.anything());
    expect(sentHeaders().get("X-User-Id")).toBe("organiser-id");
    expect(sentHeaders().get("X-Attendee-Id")).toBeNull();
  });

  it("sends the coordinator's X-User-Id after switching Acting as", async () => {
    const { apiClient, setDevRole } = await loadClient();
    setDevRole("coordinator");
    await apiClient.get("/api/v1/event-requests");

    expect(sentHeaders().get("X-User-Id")).toBe("coordinator-id");
  });

  it("sends only X-Attendee-Id for the attendee routes", async () => {
    const { apiClient } = await loadClient();
    await apiClient.get("/api/v1/me/registrations", "attendee");

    expect(sentHeaders().get("X-Attendee-Id")).toBe("attendee-id");
    expect(sentHeaders().get("X-User-Id")).toBeNull();
  });

  it("sends no identity header for routes that take none (D7)", async () => {
    const { apiClient } = await loadClient();
    await apiClient.post("/api/v1/events/e1/waitlist", { email: "a@smu.edu.sg" }, "none");

    expect(sentHeaders().get("X-Attendee-Id")).toBeNull();
    expect(sentHeaders().get("X-User-Id")).toBeNull();
  });

  it("sends JSON bodies with the method and Content-Type", async () => {
    const { apiClient } = await loadClient();
    await apiClient.patch("/api/v1/event-requests/r1", { name: "Workshop" });

    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ name: "Workshop" }));
    expect(sentHeaders().get("Content-Type")).toBe("application/json");
  });
});

describe("Acting as role", () => {
  it("defaults to organiser", async () => {
    const { getDevRole } = await loadClient();
    expect(getDevRole()).toBe("organiser");
  });

  it("is kept in localStorage across reloads", async () => {
    const first = await loadClient();
    first.setDevRole("coordinator");
    expect(localStorage.getItem("connectsphere.devRole")).toBe("coordinator");

    const reloaded = await loadClient();
    expect(reloaded.getDevRole()).toBe("coordinator");
  });

  it("falls back to organiser for an unknown stored value", async () => {
    localStorage.setItem("connectsphere.devRole", "admin");
    const { getDevRole } = await loadClient();
    expect(getDevRole()).toBe("organiser");
  });
});

describe("responses", () => {
  it("parses JSON bodies", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ events: [] }));
    const { apiClient } = await loadClient();
    await expect(apiClient.get("/api/v1/events/available", "attendee")).resolves.toEqual({ events: [] });
  });

  it("returns text for non-JSON bodies, like the health check", async () => {
    fetchMock.mockResolvedValue(new Response("event service is up", { headers: { "Content-Type": "text/plain" } }));
    const { apiClient } = await loadClient();
    await expect(apiClient.get("/api/events/health")).resolves.toBe("event service is up");
  });

  it("throws ApiError with the code, fields and whole body of a 4xx", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ code: "MISSING_REQUIRED_FIELD", fields: ["dietary", 7], extra: true }, 422),
    );
    const { apiClient, ApiError } = await loadClient();

    const error = await apiClient.post("/api/v1/events/e1/registrations", {}, "attendee").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      code: "MISSING_REQUIRED_FIELD",
      fields: ["dietary"],
      body: { code: "MISSING_REQUIRED_FIELD", extra: true },
    });
  });

  it("uses HTTP_ERROR when the error body has no code or isn't JSON", async () => {
    fetchMock.mockResolvedValue(new Response("Internal Server Error", { status: 500 }));
    const { apiClient } = await loadClient();

    await expect(apiClient.get("/api/v1/me/event-requests")).rejects.toMatchObject({
      status: 500,
      code: "HTTP_ERROR",
      fields: [],
    });
  });
});
