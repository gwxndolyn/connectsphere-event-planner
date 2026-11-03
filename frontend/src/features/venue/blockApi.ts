import { ApiError, apiClient } from "../../api/client";
import { formatInstantDateTime } from "../registration/datetime";
import { singaporeInstant } from "./bookingApi";
import type { VenueBlock, VenueBlockReason, VenueBlockWrite } from "./bookingTypes";

// US23a (SCRUM-90): Venue staff mark a venue unavailable for a period.
export const blockApi = {
  // US23b (SCRUM-91) AC 5 (D117): Venue staff end a period early, so the venue may be free again.
  endEarly: (venueId: string, blockId: string) =>
    apiClient.post<VenueBlock>(`/api/v1/venues/${venueId}/blocks/${blockId}/end`, {}),
  markUnavailable: (venueId: string, body: VenueBlockWrite) =>
    apiClient.post<VenueBlock>(`/api/v1/venues/${venueId}/blocks`, body),
};

const REASON_LABELS: Record<VenueBlockReason, string> = {
  maintenance: "Maintenance",
  equipment_failure: "Equipment failure",
  renovation: "Renovation",
  safety: "Safety",
  other: "Other",
};

/** AC 1's reasons, in the order the form lists them. */
export const BLOCK_REASONS = Object.keys(REASON_LABELS) as VenueBlockReason[];

export function blockReasonLabel(reason: string): string {
  return REASON_LABELS[reason as VenueBlockReason] ?? reason;
}

/** "8 Oct 2026, 10:00 am to 9 Oct 2026, 6:00 pm (Maintenance)". */
export function formatBlockPeriod(block: { starts_at: string; ends_at: string; reason: string }): string {
  return `${formatInstantDateTime(block.starts_at)} to ${formatInstantDateTime(block.ends_at)} (${blockReasonLabel(block.reason)})`;
}

export interface BlockFormValues {
  venueId: string;
  startDate: string;
  startTime: string;
  endDate: string;
  endTime: string;
  reason: string;
  note: string;
}

/** The body, in Singapore time (D9). Blank fields are left out, so MISSING_REQUIRED_FIELD names each one. */
export function toBlockBody(form: BlockFormValues): VenueBlockWrite {
  const body: VenueBlockWrite = {};
  const startsAt = singaporeInstant(form.startDate, form.startTime);
  const endsAt = singaporeInstant(form.endDate, form.endTime);
  if (startsAt) body.starts_at = startsAt;
  if (endsAt) body.ends_at = endsAt;
  if (form.reason) body.reason = form.reason;
  if (form.note.trim()) body.note = form.note.trim();
  return body;
}

/** AC 2, before sending: the API says the same, but the form can say it at once. */
export function endBeforeStart(form: BlockFormValues): boolean {
  const startsAt = singaporeInstant(form.startDate, form.startTime);
  const endsAt = singaporeInstant(form.endDate, form.endTime);
  return Boolean(startsAt && endsAt && Date.parse(endsAt) <= Date.parse(startsAt));
}

const FALLBACK_MESSAGE = "The period could not be saved. Check the backend connection and try again.";

export function blockErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  switch (error.code) {
    case "MISSING_REQUIRED_FIELD":
      return "Complete the fields marked below.";
    case "INVALID_BLOCK":
      return "Review the fields marked below and try again.";
    case "NOT_FOUND":
      return "That venue no longer exists. Choose another.";
    case "FORBIDDEN":
      return "Only Venue staff can mark a venue unavailable.";
    // US23b (SCRUM-91): ending a period that's already over.
    case "BLOCK_ENDED":
      return "This period has already ended. Reload the calendar to see it as it is now.";
    default:
      return FALLBACK_MESSAGE;
  }
}

/** The API's errors by its field names (starts_at, ends_at, reason, note). */
export function blockFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  if (error.code === "MISSING_REQUIRED_FIELD") return Object.fromEntries(error.fields.map((field) => [field, "Required."]));
  if (error.code !== "INVALID_BLOCK") return {};
  const errors = error.body.errors;
  if (!errors || typeof errors !== "object") return {};
  return Object.fromEntries(Object.entries(errors).filter((entry): entry is [string, string] => typeof entry[1] === "string"));
}
