/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // Fixed values, so tests never depend on a developer's frontend/.env.
    env: {
      // Dev mode (SCRUM-105, #62): App skips the login page and apiClient sends the X-User-Id /
      // X-Attendee-Id stubs only when this is "true". Does nothing before #62 merges.
      VITE_DEV_AUTH: 'true',
      VITE_API_BASE_URL: 'http://api.test',
      VITE_DEV_USER_ID: 'organiser-id',
      VITE_DEV_COORDINATOR_ID: 'coordinator-id',
      VITE_DEV_ATTENDEE_ID: 'attendee-id',
      VITE_DEV_VENUE_STAFF_ID: 'venue-staff-id',
    },
    // Integration flows type through whole forms; CI runners are slower than a laptop.
    testTimeout: 15000,
    restoreMocks: true,
    unstubGlobals: true,
  },
})
