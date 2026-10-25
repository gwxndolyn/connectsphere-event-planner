// US16b AC 2 (SCRUM-121): a user holding several roles works in one at a time. The choice is only the
// frontend's (D46): the API allows whatever any held role allows, so this decides what's shown, not
// what's permitted. Kept per user on this browser, so a refresh stays put and the next person to log in
// here starts on their own first role.
const ROLE_KEY = "connectsphere.role";

const LABELS: Record<string, string> = {
  organiser: "Organiser",
  coordinator: "Coordinator",
  coordinator_lead: "Coordinator Lead",
  venue_staff: "Venue staff",
  tech_support: "Tech support",
  safety_officer: "Safety officer",
  attendee: "Attendee",
};

/** How the screens name a role; an unknown one is shown as sent. */
export function roleLabel(role: string): string {
  return LABELS[role] ?? role;
}

/** The role this user chose last time, if they still hold it; otherwise their first held role, which is
 * the first in the role type's order as GET /api/v1/me lists them (TC-US16B-18, 20). Undefined only
 * when `roles` is empty. */
export function startingRole(userId: string, roles: string[]): string | undefined {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(ROLE_KEY) ?? "null");
    if (stored && typeof stored === "object" && "userId" in stored && "role" in stored) {
      const { userId: storedUser, role } = stored as { userId: unknown; role: unknown };
      if (storedUser === userId && typeof role === "string" && roles.includes(role)) return role;
    }
  } catch {
    // Unreadable or unavailable storage: start on the first role.
  }
  return roles[0];
}

export function rememberRole(userId: string, role: string) {
  try {
    localStorage.setItem(ROLE_KEY, JSON.stringify({ userId, role }));
  } catch {
    // Storage can be unavailable (private windows); the role then resets on refresh.
  }
}
