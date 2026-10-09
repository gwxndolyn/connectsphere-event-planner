import type { ClarificationSection, EventRequest } from "./types";

type DisplayedField = [keyof EventRequest, string];

// Same order as the backend's CLARIFICATION_SECTIONS (D13); each groups the US1 fields it covers.
export const SECTIONS: { key: ClarificationSection; label: string; fields: DisplayedField[] }[] = [
  {
    key: "details",
    label: "Event details",
    fields: [
      ["name", "Event name"],
      ["event_category", "Event category"],
      ["purpose", "Purpose / description"],
    ],
  },
  {
    key: "schedule",
    label: "Schedule",
    fields: [
      ["preferred_dates", "Preferred dates"],
      ["preferred_start_time", "Start time"],
      ["preferred_end_time", "End time"],
    ],
  },
  { key: "attendance", label: "Attendance", fields: [["expected_attendees", "Expected attendees"]] },
  { key: "layout", label: "Room layout", fields: [["room_layout_preference", "Room layout preference"]] },
  { key: "accessibility", label: "Accessibility", fields: [["accessibility_needs", "Accessibility needs"]] },
  { key: "equipment", label: "Equipment", fields: [["equipment_needs", "Equipment needs"]] },
  { key: "registration", label: "Registration", fields: [["registration_required", "Attendee registration"]] },
];

export function sectionLabel(key: string): string {
  return SECTIONS.find((section) => section.key === key)?.label ?? key;
}

export function displayValue(value: EventRequest[keyof EventRequest]): string {
  if (value === null || value === "" || (Array.isArray(value) && value.length === 0)) return "Not provided";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "Required" : "Not required";
  // The API sends times as HH:MM:SS; the form takes HH:MM, so show them the same way.
  if (typeof value === "string" && /^\d{2}:\d{2}:\d{2}$/.test(value)) return value.slice(0, 5);
  return String(value);
}

export function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}
