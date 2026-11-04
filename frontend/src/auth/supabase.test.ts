import { afterEach, describe, expect, it, vi } from "vitest";

// SCRUM-145: frontend/.env.example leaves both Supabase values blank. The module must then load without
// creating a client (createClient throws on an empty URL), so the login page can say login isn't set up.
afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("supabase client", () => {
  it("is null, and loading it doesn't throw, when the Supabase values are blank", async () => {
    vi.stubEnv("VITE_SUPABASE_URL", "");
    vi.stubEnv("VITE_SUPABASE_PUBLISHABLE_KEY", "");
    vi.resetModules();

    const loaded = import("./supabase");
    await expect(loaded).resolves.toBeDefined();
    const { supabase, accessToken } = await loaded;

    expect(supabase).toBeNull();
    await expect(accessToken()).resolves.toBeNull();
  });
});
