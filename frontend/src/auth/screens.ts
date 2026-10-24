import type { View } from "../components/SiteHeader";

// The screens each logged-in role may open, its home screen first (AC 2). Staff get no attendee
// screens, so the attendee routes are never called with a staff token (PR #62 review).
// `operations_manager` stands in for Venue staff (D19).
const SCREENS: Record<string, View[]> = {
  organiser: ["event-requests", "venues"],
  coordinator: ["event-requests", "venues"],
  coordinator_lead: ["event-requests", "venues"],
  operations_manager: ["venues"],
  attendee: ["discovery", "my-events"],
};

/** A role's screens, or undefined for a role this frontend doesn't know yet (e.g. one US16b adds). */
export function screensFor(role: string): View[] | undefined {
  return Object.hasOwn(SCREENS, role) ? SCREENS[role] : undefined;
}
