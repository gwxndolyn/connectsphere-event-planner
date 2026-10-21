// D18's fixed tag lists, mirrored from backend/app/venue/models.py (DECISION-PENDING there).
// Change both together, or the form offers a tag the API rejects.
export const FACILITIES = [
  "projector",
  "screen",
  "sound_system",
  "microphone",
  "stage",
  "wifi",
  "whiteboard",
  "video_conferencing",
  "power_outlets",
] as const;

export const ACCESSIBILITY_FEATURES = [
  "wheelchair",
  "lift",
  "accessible_toilet",
  "hearing_loop",
  "step_free_entrance",
] as const;

export const ROOM_LAYOUTS = ["theatre", "classroom", "banquet", "boardroom", "u_shape", "cabaret", "standing"] as const;

const LABEL_OVERRIDES: Record<string, string> = {
  wifi: "Wi-Fi",
  u_shape: "U-shape",
  step_free_entrance: "Step-free entrance",
};

export function tagLabel(tag: string): string {
  if (LABEL_OVERRIDES[tag]) return LABEL_OVERRIDES[tag];
  const words = tag.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
