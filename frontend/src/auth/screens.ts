import type { View } from "../components/SiteHeader";

// The screens each logged-in role may open, its home screen first (AC 2). Staff get no attendee
// screens, so the attendee routes are never called with a staff token (PR #62 review).
// Registrations is US28's (SCRUM-96), for the organiser and coordinator. Equipment is US26's (SCRUM-110): the coordinator
// requests it, and it's Tech support's only screen.
// Events is US12's (SCRUM-15): the coordinator opens, edits and reads the history of their events in planning onwards.
// Notifications (US31, SCRUM-107) is every role's last screen: everyone reads their own.
const SCREENS: Record<string, View[]> = {
  organiser: ["event-requests", "registrations", "venues", "notifications"],
  coordinator: ["event-requests", "events", "registrations", "venues", "equipment", "notifications"],
  coordinator_lead: ["event-requests", "venues", "notifications"],
  venue_staff: ["venues", "notifications"],
  tech_support: ["equipment", "notifications"],
  // US30a (SCRUM-99): the Safety Officer's queue and checklist are their home screen.
  safety_officer: ["safety-reviews", "notifications"],
  attendee: ["discovery", "my-events", "notifications"],
};

/** A role's screens, or undefined for a role this frontend doesn't know yet (e.g. one US16b adds). */
export function screensFor(role: string): View[] | undefined {
  return Object.hasOwn(SCREENS, role) ? SCREENS[role] : undefined;
}
