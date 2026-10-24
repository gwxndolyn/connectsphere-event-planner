import { AuthError, type User } from "@supabase/supabase-js";
import { describe, expect, it } from "vitest";
import { SIGN_UP_ROLES, profileFromMetadata, signUpOutcome, validateSignUp, type SignUpFields } from "./signUp";

// The sign-up page's rules (SCRUM-106, US16a AC 6 and 7), without Supabase or the API.
const VALID: SignUpFields = { full_name: "Pat Person", email: "pat@example.com", password: "secret-123", role: "attendee" };

function user(identities: unknown[]): User {
  return { id: "u1", email: "pat@example.com", identities } as unknown as User;
}

describe("SIGN_UP_ROLES", () => {
  it("TC-US16A-42: offers only Organiser and Attendee", () => {
    expect(SIGN_UP_ROLES.map((role) => role.label)).toEqual(["Organiser", "Attendee"]);
    expect(SIGN_UP_ROLES.map((role) => role.value)).toEqual(["organiser", "attendee"]);
  });
});

describe("validateSignUp", () => {
  it("accepts a complete form", () => {
    expect(validateSignUp(VALID)).toEqual({});
  });

  it("TC-US16A-44: names every missing field", () => {
    expect(validateSignUp({ full_name: " ", email: "", password: "", role: "" })).toEqual({
      full_name: "Enter your name.",
      email: "Enter your email.",
      password: "Enter a password.",
      role: "Choose Organiser or Attendee.",
    });
  });

  it("TC-US16A-44: refuses a password under 6 characters", () => {
    expect(validateSignUp({ ...VALID, password: "12345" })).toEqual({ password: "Use at least 6 characters." });
    expect(validateSignUp({ ...VALID, password: "123456" })).toEqual({});
  });
});

describe("signUpOutcome", () => {
  it("TC-US16A-50: a new account waits for the confirmation email, with nobody logged in", () => {
    expect(signUpOutcome({ data: { user: user([{ id: "i1" }]), session: null }, error: null })).toEqual({ kind: "check_email" });
  });

  it("TC-US16A-43: an email that already has an account is refused", () => {
    // With "Confirm email" on, Supabase answers an existing email with a user that has no identities.
    expect(signUpOutcome({ data: { user: user([]), session: null }, error: null })).toEqual({ kind: "already_registered" });
    const exists = new AuthError("User already registered", 422, "user_already_exists");
    expect(signUpOutcome({ data: { user: null, session: null }, error: exists })).toEqual({ kind: "already_registered" });
  });

  it("says when there have been too many attempts, or the service can't be reached", () => {
    const limited = new AuthError("Too many requests", 429, "over_email_send_rate_limit");
    expect(signUpOutcome({ data: { user: null, session: null }, error: limited })).toEqual({
      kind: "error",
      message: "Too many attempts. Wait a minute, then try again.",
    });
    expect(signUpOutcome({ data: { user: null, session: null }, error: new AuthError("Failed to fetch", 0) })).toEqual({
      kind: "error",
      message: "Can't reach the sign-up service. Try again.",
    });
  });
});

describe("profileFromMetadata", () => {
  it("TC-US16A-40, 41: reads the name and role saved at sign-up", () => {
    expect(profileFromMetadata({ full_name: "Pat Person", role: "organiser", email_verified: true })).toEqual({
      full_name: "Pat Person",
      role: "organiser",
    });
  });

  it("TC-US16A-42: never turns metadata into a staff role", () => {
    expect(profileFromMetadata({ full_name: "Pat Person", role: "coordinator" })).toBeNull();
    expect(profileFromMetadata({ role: "attendee" })).toBeNull();
    expect(profileFromMetadata(undefined)).toBeNull();
  });
});
