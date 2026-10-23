import { useEffect, useState } from "react";
import { ApiError, apiClient } from "../../api/client";
import { statusLabel } from "./clarificationSections";
import type {
  CoordinatorOptionsResponse,
  EventRequest,
  QueuePerson,
  UnassignedRequest,
  UnassignedRequestsResponse,
} from "./types";
import "./eventRequests.css";
import "./assignments.css";

type Screen = "queue" | "assign" | "done";

// SCRUM-13 AC 4 and 7: the backend says why a pick was refused.
const REFUSALS: Record<string, string> = {
  self_assignment: "You can't assign a request to yourself. The Lead isn't a coordinator.",
  not_a_coordinator: "That person doesn't have the Event Coordinator role.",
  inactive: "That coordinator is inactive.",
  unknown_user: "That person no longer exists. Reload and pick again.",
};

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "The request could not be completed. Check the backend connection and try again.";
  if (error.code === "UNAUTHENTICATED") return "Set VITE_DEV_LEAD_ID to the seeded Coordinator Lead ID, then restart the frontend.";
  if (error.code === "FORBIDDEN") return "Only the Event Coordinator Lead can assign. Switch \"Acting as\" to Coordinator Lead.";
  if (error.code === "NOT_FOUND") return "This request is no longer available.";
  if (error.code === "ASSIGNMENT_NOT_ALLOWED") return "This request is no longer waiting for a coordinator. It has been assigned or moved on.";
  if (error.code === "INVALID_COORDINATOR") {
    const reason = error.body.reason;
    return (typeof reason === "string" && REFUSALS[reason]) || "That coordinator can't be assigned.";
  }
  return `The backend rejected the request (${error.status}).`;
}

function dates(request: EventRequest): string {
  return request.preferred_dates?.length ? request.preferred_dates.join(", ") : "Dates not set";
}

/** The Event Coordinator Lead's unassigned queue and the assign step (SCRUM-13, US10a). */
export function AssignmentQueuePage() {
  const [requests, setRequests] = useState<UnassignedRequest[]>([]);
  const [screen, setScreen] = useState<Screen>("queue");
  const [active, setActive] = useState<UnassignedRequest | null>(null);
  const [coordinators, setCoordinators] = useState<QueuePerson[]>([]);
  const [picked, setPicked] = useState("");
  const [assignedTo, setAssignedTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let current = true;
    apiClient
      .get<UnassignedRequestsResponse>("/api/v1/event-requests/unassigned")
      .then((response) => {
        if (current) setRequests(response.event_requests);
      })
      .catch((reason: unknown) => {
        if (current) setError(errorMessage(reason));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, []);

  async function startAssigning(request: UnassignedRequest) {
    setError(null);
    try {
      const response = await apiClient.get<CoordinatorOptionsResponse>("/api/v1/coordinators");
      setCoordinators(response.coordinators);
      setActive(request);
      setPicked("");
      setScreen("assign");
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function confirmAssignment() {
    if (!active || !picked) return;
    setSaving(true);
    setError(null);
    try {
      const result = await apiClient.post<EventRequest>(`/api/v1/event-requests/${active.id}/assignment`, {
        coordinator_id: picked,
      });
      // AC 5: the request leaves the queue once it's assigned.
      setRequests((current) => current.filter((request) => request.id !== active.id));
      setAssignedTo(result.coordinator?.name ?? null);
      setScreen("done");
    } catch (reason) {
      setError(errorMessage(reason));
      // The queue is stale if someone else assigned it first.
      if (reason instanceof ApiError && reason.code === "ASSIGNMENT_NOT_ALLOWED") {
        setRequests((current) => current.filter((request) => request.id !== active.id));
      }
    } finally {
      setSaving(false);
    }
  }

  function backToQueue() {
    setScreen("queue");
    setActive(null);
    setAssignedTo(null);
    setError(null);
  }

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <p className="request-page__eyebrow">EVENT MANAGEMENT / ASSIGNMENT</p>
          <h1>{screen === "queue" ? "Unassigned requests" : screen === "assign" ? "Assign a coordinator" : "Assignment complete"}</h1>
        </div>
        {screen === "assign" && (
          <button className="request-button request-button--quiet" type="button" onClick={backToQueue}>
            Back to queue
          </button>
        )}
      </div>

      {error && <div className="request-alert" role="alert">{error}</div>}

      {screen === "queue" && (
        <section aria-label="Unassigned requests" className="request-list">
          {loading ? (
            <p className="request-empty" role="status">Loading requests…</p>
          ) : requests.length === 0 ? (
            <div className="request-empty">
              <p>No requests are waiting for a coordinator.</p>
            </div>
          ) : (
            requests.map((request) => (
              <div className="assign-row" key={request.id}>
                <span className="assign-row__main">
                  <strong>{request.name || "Untitled event request"}</strong>
                  <span>Organiser: {request.organiser?.name ?? "Unknown"}</span>
                  <span>Preferred dates: {dates(request)}</span>
                  <span>Expected attendance: {request.expected_attendees ?? "Not set"}</span>
                </span>
                <span className={`request-status request-status--${request.status}`}>{statusLabel(request.status)}</span>
                <button
                  className="request-button request-button--primary"
                  type="button"
                  aria-label={`Assign ${request.name || "request"}`}
                  onClick={() => void startAssigning(request)}
                >
                  Assign
                </button>
              </div>
            ))
          )}
        </section>
      )}

      {screen === "assign" && active && (
        <section className="request-form" aria-label="Assign a coordinator">
          <div className="clarify-summary">
            <strong>{active.name || "Untitled event request"}</strong>
            {active.request_reference && <code>{active.request_reference}</code>}
            <span className={`request-status request-status--${active.status}`}>{statusLabel(active.status)}</span>
          </div>

          {coordinators.length === 0 ? (
            <p className="request-notice">There are no active coordinators to assign.</p>
          ) : (
            <fieldset className="assign-picker">
              <legend>Event Coordinator</legend>
              {coordinators.map((person) => (
                <label className="assign-picker__option" key={person.id}>
                  <input
                    type="radio"
                    name="coordinator"
                    value={person.id}
                    checked={picked === person.id}
                    onChange={() => {
                      setPicked(person.id);
                      setError(null);
                    }}
                  />
                  {person.name} <span>({person.email})</span>
                </label>
              ))}
            </fieldset>
          )}

          <div className="request-form__actions">
            <button className="request-button request-button--quiet" type="button" onClick={backToQueue}>
              Cancel
            </button>
            <button
              className="request-button request-button--primary"
              type="button"
              disabled={!picked || saving}
              onClick={() => void confirmAssignment()}
            >
              {saving ? "Assigning…" : "Confirm assignment"}
            </button>
          </div>
        </section>
      )}

      {screen === "done" && active && (
        <section className="request-confirmation" aria-labelledby="assigned-title">
          <span className="request-confirmation__mark" aria-hidden="true">✓</span>
          <h2 id="assigned-title">Coordinator assigned</h2>
          <p>
            {active.name || "The request"} is assigned to <strong>{assignedTo}</strong> and is now under review.
          </p>
          <button className="request-button request-button--primary" type="button" onClick={backToQueue}>
            Back to queue
          </button>
        </section>
      )}
    </main>
  );
}
