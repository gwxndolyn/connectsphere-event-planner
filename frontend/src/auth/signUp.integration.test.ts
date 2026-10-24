import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { callsTo, startMockBackend } from "../test/server";
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
});
