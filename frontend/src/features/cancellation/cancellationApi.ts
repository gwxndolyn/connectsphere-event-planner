import { ApiError, apiClient } from "../../api/client";
import type { Cancellation } from "./types";

// US9 (SCRUM-12): asking is the organiser's, deciding and cancelling the assigned coordinator's (X-User-Id or a token).
export const cancellationApi = {
  async list(eventId: string): Promise<Cancellation[]> {
    const body = await apiClient.get<{ cancellations: Cancellation[] }>(`/api/v1/event-requests/${eventId}/cancellations`);
    return body.cancellations;
  },

  request: (eventId: string, reason: string) =>
    apiClient.post<Cancellation>(`/api/v1/event-requests/${eventId}/cancellation-requests`, { reason }),

  cancel: (eventId: string, reason: string) =>
    apiClient.post<Cancellation>(`/api/v1/event-requests/${eventId}/cancel`, { reason }),

  approve: (cancellationId: string) => apiClient.post<Cancellation>(`/api/v1/event-cancellations/${cancellationId}/approve`, {}),

  reject: (cancellationId: string, reason: string) =>
    apiClient.post<Cancellation>(`/api/v1/event-cancellations/${cancellationId}/reject`, { reason }),
};

// AC 1: from approval until the start. Before approval a request is rejected (US17), not cancelled.
export const CANCELLABLE = ["approved", "planning", "confirmed", "preparation"];
// Where the panel shows: once cancelling is possible, and afterwards for the record (AC 8).
export const CANCELLATION_VISIBLE = [...CANCELLABLE, "cancelled", "completed"];
export const REASON_MAX_LENGTH = 1000;

const FALLBACK = "The request could not be completed. Check the backend connection and try again.";

export function cancellationErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK;
  switch (error.code) {
    case "MISSING_REQUIRED_FIELD":
    case "INVALID_CANCELLATION":
      return "Give a reason, of at most 1,000 characters.";
    case "CANCELLATION_NOT_ALLOWED":
      return "This event can't be cancelled in its current status.";
    case "EVENT_STARTED":
      return "This event has already started, so it can't be cancelled.";
    case "CANCELLATION_PENDING":
      return "A cancellation request is already waiting for a decision.";
    case "CANCELLATION_NOT_PENDING":
      return "This cancellation request has already been decided.";
    case "SELF_DECISION_NOT_ALLOWED":
      return "You can't decide a cancellation request you made.";
    case "NOT_FOUND":
      return "This event isn't yours, or it no longer exists.";
    case "UNAUTHENTICATED":
      return "Your session has ended. Log in again and try again.";
    case "FORBIDDEN":
      return "Your role can't do this. Switch to the event's organiser or coordinator.";
    default:
      return FALLBACK;
  }
}

const STATUS: Record<Cancellation["status"], string> = {
  pending: "Waiting for decision",
  approved: "Cancelled",
  rejected: "Rejected",
};

export function cancellationStatusLabel(status: Cancellation["status"]): string {
  return STATUS[status];
}
