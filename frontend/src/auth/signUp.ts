import type { AuthError, Session, User } from "@supabase/supabase-js";
import { ApiError, apiClient } from "../api/client";

// Sign-up (SCRUM-106, US16a AC 6 and 7): only Organisers and Attendees sign themselves up; staff
// accounts are seeded. Supabase's "Confirm email" is on, so sign-up ends with a confirmation email and
// the profile is created at the first login, from the name and role saved on the Supabase account.

export type SignUpRole = "organiser" | "attendee";

export const SIGN_UP_ROLES: { value: SignUpRole; label: string }[] = [
  { value: "organiser", label: "Organiser" },
  { value: "attendee", label: "Attendee" },
];

// Supabase's default minimum password length (Authentication → Providers → Email).
const MIN_PASSWORD_LENGTH = 6;

export interface SignUpFields {
  full_name: string;
  email: string;
  password: string;
  role: SignUpRole | "";
}

/** Field errors to show before anything is sent (TC-US16A-44); empty when the form is complete. */
export function validateSignUp(fields: SignUpFields): Partial<Record<keyof SignUpFields, string>> {
  const errors: Partial<Record<keyof SignUpFields, string>> = {};
  if (!fields.full_name.trim()) errors.full_name = "Enter your name.";
  if (!fields.email.trim()) errors.email = "Enter your email.";
  if (!fields.password) errors.password = "Enter a password.";
  else if (fields.password.length < MIN_PASSWORD_LENGTH) errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  if (!fields.role) errors.role = "Choose Organiser or Attendee.";
  return errors;
}

export type SignUpOutcome = { kind: "check_email" } | { kind: "already_registered" } | { kind: "error"; message: string };

/** What a `supabase.auth.signUp` answer means for the page. */
export function signUpOutcome(result: {
  data: { user: User | null; session: Session | null };
  error: AuthError | null;
}): SignUpOutcome {
  const { data, error } = result;
  if (error) {
    if (error.code === "user_already_exists" || error.code === "email_exists") return { kind: "already_registered" };
    if (error.status === 429) return { kind: "error", message: "Too many attempts. Wait a minute, then try again." };
    if (!error.status) return { kind: "error", message: "Can't reach the sign-up service. Try again." };
    return { kind: "error", message: "Couldn't sign up. Try again." };
  }
  // With "Confirm email" on, Supabase doesn't say an email is taken (so it can't be probed); it returns
  // a user with no identities instead (TC-US16A-43).
  if (data.user && data.user.identities?.length === 0) return { kind: "already_registered" };
  return { kind: "check_email" };
}

/** The name and role saved at sign-up, or null if they're missing or the role isn't one a person may
 * choose (TC-US16A-42: metadata can never make anyone staff). */
export function profileFromMetadata(
  metadata: Record<string, unknown> | undefined,
): { full_name: string; role: SignUpRole } | null {
  const fullName = typeof metadata?.full_name === "string" ? metadata.full_name.trim() : "";
  const role = metadata?.role;
  if (!fullName || (role !== "organiser" && role !== "attendee")) return null;
  return { full_name: fullName, role };
}

export interface Profile {
  id: string;
  email: string;
  full_name: string | null;
  // Every role the user holds, in the role type's order (US16b, SCRUM-121); sign-up makes one.
  roles: string[];
}

/** First login after confirming (TC-US16A-40, 41): create the profile from what sign-up saved. */
export async function completeProfile(metadata: Record<string, unknown> | undefined): Promise<Profile> {
  const profile = profileFromMetadata(metadata);
  if (!profile) throw new ApiError(403, "PROFILE_REQUIRED");
  try {
    return await apiClient.post<Profile>("/api/v1/auth/profile", profile);
  } catch (error) {
    // 409 also comes back when this account's own profile already exists: the confirmation link's
    // tab, a retry or StrictMode's double effect created it first. Read it back; if there's still no
    // profile, the email belongs to someone else and the 409 stands (PR #75 review).
    if (!(error instanceof ApiError && error.code === "EMAIL_ALREADY_REGISTERED")) throw error;
    try {
      return await apiClient.get<Profile>("/api/v1/me");
    } catch {
      throw error;
    }
  }
}
