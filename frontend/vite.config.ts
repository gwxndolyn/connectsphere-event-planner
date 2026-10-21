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
      VITE_API_BASE_URL: 'http://api.test',
      VITE_DEV_USER_ID: 'organiser-id',
      VITE_DEV_COORDINATOR_ID: 'coordinator-id',
      VITE_DEV_ATTENDEE_ID: 'attendee-id',
    },
    restoreMocks: true,
    unstubGlobals: true,
  },
})
