/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEV_USER_ID?: string;
  readonly VITE_DEV_COORDINATOR_ID?: string;
  readonly VITE_DEV_LEAD_ID?: string;
  readonly VITE_DEV_VENUE_STAFF_ID?: string;
  readonly VITE_DEV_TECH_SUPPORT_ID?: string;
  readonly VITE_DEV_SAFETY_OFFICER_ID?: string;
  readonly VITE_DEV_ATTENDEE_ID?: string;
  readonly VITE_DEV_AUTH?: string;
  readonly VITE_SUPABASE_URL?: string;
  readonly VITE_SUPABASE_PUBLISHABLE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
