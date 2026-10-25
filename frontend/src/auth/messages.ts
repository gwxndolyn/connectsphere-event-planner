import type { AuthError } from "@supabase/supabase-js";
import { ApiError } from "../api/client";

// AC 3: one message for a wrong password and for an unknown email, so it never hints which.
const WRONG_DETAILS = "Email or password is incorrect";

/** What the login page says when Supabase refuses a login. */
export function loginErrorMessage(error: AuthError): string {
  if (error.code === "invalid_credentials") return WRONG_DETAILS;
  if (error.code === "email_not_confirmed") return "Confirm your email first: open the link we sent you, then log in.";
  if (error.status === 429) return "Too many attempts. Wait a minute, then try again.";
  if (!error.status) return "Can't reach the login service. Try again.";
  return "Couldn't log in. Try again.";
}

/** What App says when GET /api/v1/me fails after a login. */
export function accountErrorMessage(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.code === "PROFILE_REQUIRED") return "Your account doesn't have a profile yet.";
    if (reason.code === "FORBIDDEN") return "This account is deactivated. Ask an administrator to reactivate it.";
    // SCRUM-106: sign-up's email already belongs to a profile, e.g. a seeded staff account (TC-US16A-43).
    if (reason.code === "EMAIL_ALREADY_REGISTERED") return "This email already belongs to an account. Log in with that account instead.";
    return "Login is unavailable right now. Try again shortly.";
  }
  return "Couldn't load your account. Check the backend is running, then refresh.";
}
