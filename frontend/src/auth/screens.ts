import type { View } from "../components/SiteHeader";

// The screens each logged-in role may open, its home screen first (AC 2). Staff get no attendee
// screens, so the attendee routes are never called with a staff token (PR #62 review).
// Registrations is US28's (SCRUM-96), for the organiser and coordinator. Equipment is US26's (SCRUM-110): the coordinator
// requests it, and it's Tech support's only screen.
// Events is US12's (SCRUM-15): the coordinator opens, edits and reads the history of their events in planning onwards.
const SCREENS: Record<string, View[]> = {
  organiser: ["event-requests", "registrations", "venues"],
  coordinator: ["event-requests", "events", "registrations", "venues", "equipment"],
  coordinator_lead: ["event-requests", "venues"],
  venue_staff: ["venues"],
  tech_support: ["equipment"],
  attendee: ["discovery", "my-events"],
};

/** A role's screens, or undefined for a role this frontend doesn't know yet (e.g. one US16b adds). */
export function screensFor(role: string): View[] | undefined {
  return Object.hasOwn(SCREENS, role) ? SCREENS[role] : undefined;
}
