import { AuthError } from "@supabase/supabase-js";
import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { accountErrorMessage, loginErrorMessage } from "./messages";

// What the login page and the account check say when something goes wrong (SCRUM-105, PR #62 review).
describe("loginErrorMessage", () => {
  it("TC-US16A-34: wrong details get the one AC 3 message", () => {
    expect(loginErrorMessage(new AuthError("Invalid login credentials", 400, "invalid_credentials"))).toBe(
      "Email or password is incorrect",
    );
  });

  it("says when the email isn't confirmed yet", () => {
    expect(loginErrorMessage(new AuthError("Email not confirmed", 400, "email_not_confirmed"))).toBe(
      "Confirm your email first: open the link we sent you, then log in.",
    );
  });

  it("says when there have been too many attempts", () => {
    expect(loginErrorMessage(new AuthError("Too many requests", 429, "over_request_rate_limit"))).toBe(
      "Too many attempts. Wait a minute, then try again.",
    );
  });

  it("says when the login service can't be reached", () => {
    expect(loginErrorMessage(new AuthError("Failed to fetch", 0))).toBe("Can't reach the login service. Try again.");
  });

  it("has a fallback for anything else", () => {
    expect(loginErrorMessage(new AuthError("Server error", 500, "unexpected_failure"))).toBe(
      "Couldn't log in. Try again.",
    );
  });
});

describe("accountErrorMessage", () => {
  it("says when the account has no profile yet", () => {
    expect(accountErrorMessage(new ApiError(403, "PROFILE_REQUIRED"))).toBe("Your account doesn't have a profile yet.");
  });

  it("says when the account is deactivated", () => {
    expect(accountErrorMessage(new ApiError(403, "FORBIDDEN"))).toBe(
      "This account is deactivated. Ask an administrator to reactivate it.",
    );
  });

  it("says when login is down on the server", () => {
    expect(accountErrorMessage(new ApiError(503, "AUTH_UNAVAILABLE"))).toBe(
      "Login is unavailable right now. Try again shortly.",
    );
    expect(accountErrorMessage(new ApiError(500, "AUTH_NOT_CONFIGURED"))).toBe(
      "Login is unavailable right now. Try again shortly.",
    );
  });

  it("asks to check the backend only when it can't be reached", () => {
    expect(accountErrorMessage(new TypeError("Failed to fetch"))).toBe(
      "Couldn't load your account. Check the backend is running, then refresh.",
    );
  });
});
