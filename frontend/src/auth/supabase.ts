import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Supabase Auth (US16a, §9). The publishable key is safe in the browser; the secret key never is.
const url = import.meta.env.VITE_SUPABASE_URL;
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

// Null when frontend/.env lacks the two values: the login page then says login isn't set up.
export const supabase: SupabaseClient | null = url && publishableKey ? createClient(url, publishableKey) : null;

// VITE_DEV_AUTH=true keeps the pre-login behaviour for local dev and the existing E2E tests: no login
// required, the "Acting as" switch and the X-User-Id / X-Attendee-Id stubs (TC-US16A-38).
export const DEV_AUTH = import.meta.env.VITE_DEV_AUTH === "true";

/** The current access token, read on every request so refreshed tokens are picked up (§9). */
export async function accessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
