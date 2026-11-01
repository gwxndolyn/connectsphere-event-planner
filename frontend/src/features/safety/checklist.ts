// US30a AC 2: the checklist items' labels, for showing a stored review (the API sends them with a
// review to be filled in, but a stored review only has the keys).
export const CHECKLIST_LABELS: Record<string, string> = {
  attendance_capacity: "Expected attendance against venue capacity",
  layout: "Room layout",
  emergency_access: "Emergency access",
  accessibility: "Accessibility",
  equipment_placement: "Equipment placement",
  crowd_movement: "Expected crowd movement",
  venue_restrictions: "Known venue restrictions",
};

export function checklistLabel(key: string): string {
  return CHECKLIST_LABELS[key] ?? key;
}
