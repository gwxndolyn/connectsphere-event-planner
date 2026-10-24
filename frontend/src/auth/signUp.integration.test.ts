import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { callsTo, server, startMockBackend } from "../test/server";
import { completeProfile } from "./signUp";

// SCRUM-106: the first login after confirming the email creates the profile from what sign-up saved.
startMockBackend();

describe("completeProfile", () => {
  it("TC-US16A-40, 41: posts the saved name and role, and returns the new profile", async () => {
    const profile = await completeProfile({ full_name: "Pat Person", role: "organiser", email_verified: true });

    expect(profile).toEqual({ id: "new-user-id", email: "pat@example.com", full_name: "Pat Person", role: "organiser" });
    expect(callsTo("POST", "/api/v1/auth/profile").map((call) => call.body)).toEqual([
      { full_name: "Pat Person", role: "organiser" },
    ]);
  });

  it("sends nothing when sign-up saved no usable name and role", async () => {
    await expect(completeProfile({ role: "coordinator" })).rejects.toBeInstanceOf(ApiError);
    expect(callsTo("POST", "/api/v1/auth/profile")).toEqual([]);
  });

  // PR #75 review: the confirmation link opens a second tab, and both tabs (or a retry, or StrictMode's
  // double effect) try to create the same profile. The loser gets 409 and must read the profile back.
  const API = "http://api.test";
  const PROFILE = { id: "new-user-id", email: "pat@example.com", full_name: "Pat Person", role: "organiser" };

  function profileAlreadyExists() {
    server.use(
      http.post(`${API}/api/v1/auth/profile`, () =>
        HttpResponse.json({ code: "EMAIL_ALREADY_REGISTERED" }, { status: 409 }),
      ),
    );
  }

  it("TC-US16A-40, 41: when another tab created the profile first, reads it back and carries on", async () => {
    profileAlreadyExists();
    server.use(http.get(`${API}/api/v1/me`, () => HttpResponse.json(PROFILE)));

    await expect(completeProfile({ full_name: "Pat Person", role: "organiser" })).resolves.toEqual(PROFILE);
  });

  it("TC-US16A-43: when the email belongs to someone else's profile, keeps the 409", async () => {
    profileAlreadyExists();
    server.use(
      http.get(`${API}/api/v1/me`, () => HttpResponse.json({ code: "PROFILE_REQUIRED" }, { status: 403 })),
    );

    const refused = completeProfile({ full_name: "Pat Person", role: "organiser" });

    await expect(refused).rejects.toMatchObject({ status: 409, code: "EMAIL_ALREADY_REGISTERED" });
  });
});
