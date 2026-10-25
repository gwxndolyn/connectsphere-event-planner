import { useEffect, useState } from "react";
import { ApiError, apiClient } from "../../api/client";
import { statusLabel } from "./clarificationSections";
import type {
  AssignedRequest,
  AssignedRequestsResponse,
  AssignmentHistoryResponse,
  AssignmentRecord,
  CoordinatorOption,
  CoordinatorOptionsResponse,
  EventRequest,
  UnassignedRequest,
  UnassignedRequestsResponse,
} from "./types";
import { LeadRequestDetail } from "./LeadRequestDetail";
import "./eventRequests.css";
import "./assignments.css";

type Screen = "queue" | "assign" | "done" | "history" | "detail";
type Tab = "unassigned" | "assigned";

// SCRUM-86 AC 3: the statuses an assigned, still-active event can be in.
const ACTIVE_STATUSES = ["under_review", "awaiting_clarification", "approved", "planning", "confirmed"];

// SCRUM-13 AC 4 and 7: the backend says why a pick was refused.
const REFUSALS: Record<string, string> = {
  self_assignment: "You can't assign a request to yourself. The Lead isn't a coordinator.",
  not_a_coordinator: "That person doesn't have the Event Coordinator role.",
  inactive: "That coordinator is inactive.",
  same_coordinator: "This event already belongs to that coordinator. Pick a different one.",
  unknown_user: "That person no longer exists. Reload and pick again.",
};

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "The request could not be completed. Check the backend connection and try again.";
  if (error.code === "UNAUTHENTICATED") return "Set VITE_DEV_LEAD_ID to the seeded Coordinator Lead ID, then restart the frontend.";
  if (error.code === "FORBIDDEN") return "Only the Event Coordinator Lead can assign. Switch \"Acting as\" to Coordinator Lead.";
  if (error.code === "NOT_FOUND") return "This request is no longer available.";
  if (error.code === "ASSIGNMENT_NOT_ALLOWED") return "This request is no longer waiting for a coordinator. It has been assigned or moved on.";
  if (error.code === "REASSIGNMENT_NOT_ALLOWED") return "This event can no longer be reassigned. It has no coordinator or has been rejected, cancelled or completed.";
  if (error.code === "MISSING_REQUIRED_FIELD") return "Give a reason for the reassignment.";
  if (error.code === "INVALID_STATUS_FILTER") return "That status can't be filtered here. Pick an active status.";
  if (error.code === "INVALID_COORDINATOR") {
    const reason = error.body.reason;
    return (typeof reason === "string" && REFUSALS[reason]) || "That coordinator can't be assigned.";
  }
  return `The backend rejected the request (${error.status}).`;
}

// SCRUM-67 AC 1, 2: how many events the coordinator is currently planning; 0 when none.
function workloadLabel(count: number): string {
  return `${count} ${count === 1 ? "event" : "events"} planning`;
}

// SCRUM-69 AC 3: when it happened, in Singapore time like the rest of the app (D9).
function when(iso: string): string {
  return new Date(iso).toLocaleString("en-SG", {
    timeZone: "Asia/Singapore",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function dates(request: EventRequest): string {
  return request.preferred_dates?.length ? request.preferred_dates.join(", ") : "Dates not set";
}

/** The Event Coordinator Lead's unassigned queue and the assign step (SCRUM-13, US10a). */
export function AssignmentQueuePage() {
  const [requests, setRequests] = useState<UnassignedRequest[]>([]);
  const [screen, setScreen] = useState<Screen>("queue");
  const [active, setActive] = useState<UnassignedRequest | null>(null);
  const [coordinators, setCoordinators] = useState<CoordinatorOption[]>([]);
  const [picked, setPicked] = useState("");
  const [assignedTo, setAssignedTo] = useState<string | null>(null);
  // SCRUM-83: the assign screen doubles as the reassign screen, which also asks for a reason.
  const [reassigning, setReassigning] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // SCRUM-86: the Assigned tab, its filters, and the coordinators it can be filtered by.
  const [tab, setTab] = useState<Tab>("unassigned");
  const [assigned, setAssigned] = useState<AssignedRequest[]>([]);
  const [assignedLoaded, setAssignedLoaded] = useState(false);
  const [filterCoordinator, setFilterCoordinator] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [assignedVersion, setAssignedVersion] = useState(0);
  const [filterOptions, setFilterOptions] = useState<{ id: string; name: string }[]>([]);
  // SCRUM-69: the history of the request being viewed.
  const [history, setHistory] = useState<AssignmentRecord[]>([]);

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

  useEffect(() => {
    let current = true;
    const params = new URLSearchParams();
    if (filterCoordinator) params.set("coordinator_id", filterCoordinator);
    if (filterStatus) params.set("status", filterStatus);
    const query = params.size ? `?${params.toString()}` : "";
    apiClient
      .get<AssignedRequestsResponse>(`/api/v1/event-requests/assigned${query}`)
      .then((response) => {
        if (!current) return;
        setAssigned(response.event_requests);
        // The coordinator filter lists everyone the Lead has assigned to, so it must not shrink
        // to the coordinator just chosen.
        if (!query) {
          const seen = new Map<string, string>();
          response.event_requests.forEach((row) => row.coordinator && seen.set(row.coordinator.id, row.coordinator.name));
          setFilterOptions([...seen].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name)));
        }
        setAssignedLoaded(true);
      })
      .catch((reason: unknown) => {
        if (current) setError(errorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, [filterCoordinator, filterStatus, assignedVersion]);

  function viewDetail(request: EventRequest) {
    setError(null);
    setActive(request as UnassignedRequest);
    setScreen("detail");
  }

  async function openHistory(request: EventRequest) {
    setError(null);
    try {
      const response = await apiClient.get<AssignmentHistoryResponse>(
        `/api/v1/event-requests/${request.id}/assignment-history`,
      );
      setHistory(response.assignments);
      setActive(request as UnassignedRequest);
      setScreen("history");
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function startAssigning(request: UnassignedRequest, reassign = false) {
    setError(null);
    try {
      const response = await apiClient.get<CoordinatorOptionsResponse>("/api/v1/coordinators");
      // AC 2, 5: only a different coordinator can be picked, so the current one isn't offered.
      setCoordinators(response.coordinators.filter((person) => !reassign || person.id !== request.coordinator?.id));
      setActive(request);
      setPicked("");
      setReason("");
      setReassigning(reassign);
      setScreen("assign");
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function confirmAssignment() {
    if (!active || !picked) return;
    if (reassigning && !reason.trim()) {
      setError("Give a reason for the reassignment.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = reassigning
        ? await apiClient.post<EventRequest>(`/api/v1/event-requests/${active.id}/reassignment`, {
            coordinator_id: picked,
            reason: reason.trim(),
          })
        : await apiClient.post<EventRequest>(`/api/v1/event-requests/${active.id}/assignment`, {
            coordinator_id: picked,
          });
      // AC 5: the request leaves the queue once it's assigned.
      setRequests((current) => current.filter((request) => request.id !== active.id));
      setAssignedTo(result.coordinator?.name ?? null);
      // The Assigned tab now includes this request; reload it (and the filter options) from scratch.
      setFilterCoordinator("");
      setFilterStatus("");
      setAssignedLoaded(false);
      setAssignedVersion((version) => version + 1);
      setActive({ ...active, coordinator: result.coordinator });
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
    setReassigning(false);
    setError(null);
  }

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <p className="request-page__eyebrow">EVENT MANAGEMENT / ASSIGNMENT</p>
          <h1>
            {screen === "queue"
              ? "Unassigned requests"
              : screen === "assign"
                ? reassigning
                  ? "Reassign an event"
                  : "Assign a coordinator"
                : screen === "history"
                  ? "Assignment history"
                  : screen === "detail"
                    ? "Request details"
                    : reassigning
                      ? "Reassignment complete"
                      : "Assignment complete"}
          </h1>
        </div>
        {(screen === "assign" || screen === "history" || screen === "detail") && (
          <button className="request-button request-button--quiet" type="button" onClick={backToQueue}>
            Back to queue
          </button>
        )}
      </div>

      {error && <div className="request-alert" role="alert">{error}</div>}

      {screen === "queue" && (
        <div className="assign-tabs" role="tablist" aria-label="Lead views">
          {(["unassigned", "assigned"] as Tab[]).map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              id={`tab-${id}`}
              aria-selected={tab === id}
              aria-controls={`panel-${id}`}
              className={`assign-tabs__tab${tab === id ? " assign-tabs__tab--active" : ""}`}
              onClick={() => setTab(id)}
            >
              {id === "unassigned" ? "Unassigned" : "Assigned"}
            </button>
          ))}
        </div>
      )}

      {screen === "queue" && tab === "unassigned" && (
        <section id="panel-unassigned" role="tabpanel" aria-labelledby="tab-unassigned" aria-label="Unassigned requests" className="request-list">
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
                <span className="assign-row__actions">
                  <button
                    className="request-button request-button--quiet"
                    type="button"
                    aria-label={`View ${request.name || "request"}`}
                    onClick={() => viewDetail(request)}
                  >
                    View
                  </button>
                  <button
                    className="request-button request-button--primary"
                    type="button"
                    aria-label={`Assign ${request.name || "request"}`}
                    onClick={() => void startAssigning(request)}
                  >
                    Assign
                  </button>
                </span>
              </div>
            ))
          )}
        </section>
      )}

      {screen === "queue" && tab === "assigned" && (
        <section id="panel-assigned" role="tabpanel" aria-labelledby="tab-assigned" aria-label="Assigned requests" className="request-list">
          <div className="assign-filters">
            <label className="request-field">
              Coordinator
              <select value={filterCoordinator} onChange={(event) => setFilterCoordinator(event.target.value)}>
                <option value="">All coordinators</option>
                {filterOptions.map((option) => (
                  <option key={option.id} value={option.id}>{option.name}</option>
                ))}
              </select>
            </label>
            <label className="request-field">
              Status
              <select value={filterStatus} onChange={(event) => setFilterStatus(event.target.value)}>
                <option value="">All statuses</option>
                {ACTIVE_STATUSES.map((status) => (
                  <option key={status} value={status}>{statusLabel(status)}</option>
                ))}
              </select>
            </label>
          </div>
          {!assignedLoaded ? (
            <p className="request-empty" role="status">Loading events…</p>
          ) : assigned.length === 0 ? (
            <div className="request-empty">
              <p>{filterCoordinator || filterStatus ? "No assigned events match these filters." : "You haven't assigned any active events yet."}</p>
            </div>
          ) : (
            assigned.map((request) => (
              <div className="assign-row" key={request.id}>
                <span className="assign-row__main">
                  <strong>{request.name || "Untitled event request"}</strong>
                  <span>Coordinator: {request.coordinator?.name}</span>
                  <span>Event date: {request.event_date ?? "Not set"}</span>
                </span>
                <span className={`request-status request-status--${request.status}`}>{statusLabel(request.status)}</span>
                <span className="assign-row__actions">
                  <button
                    className="request-button request-button--quiet"
                    type="button"
                    aria-label={`View ${request.name || "request"}`}
                    onClick={() => viewDetail(request)}
                  >
                    View
                  </button>
                  <button
                    className="request-button request-button--quiet"
                    type="button"
                    aria-label={`Assignment history for ${request.name || "request"}`}
                    onClick={() => void openHistory(request)}
                  >
                    History
                  </button>
                </span>
              </div>
            ))
          )}
        </section>
      )}

      {screen === "detail" && active && (
        <LeadRequestDetail
          request={active}
          onAssign={() => void startAssigning(active)}
          onReassign={() => void startAssigning(active, true)}
          onHistory={() => void openHistory(active)}
        />
      )}

      {screen === "history" && active && (
        <section aria-label="Assignment history" className="request-list">
          <div className="clarify-summary">
            <strong>{active.name || "Untitled event request"}</strong>
            {active.request_reference && <code>{active.request_reference}</code>}
          </div>
          {history.length === 0 ? (
            <p className="request-empty">No assignments have been recorded for this event.</p>
          ) : (
            <ol className="assign-history">
              {history.map((entry) => (
                <li className="assign-history__entry" key={entry.id}>
                  <strong>{entry.kind === "reassignment" ? "Reassignment" : "Assignment"}</strong>
                  <span>
                    {entry.assigned_by.name} assigned <strong>{entry.coordinator.name}</strong>
                    {entry.reason && <em className="assign-history__reason">Reason: {entry.reason}</em>}
                  </span>
                  <time dateTime={entry.created_at}>{when(entry.created_at)}</time>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}

      {screen === "assign" && active && (
        <section className="request-form" aria-label={reassigning ? "Reassign an event" : "Assign a coordinator"}>
          <div className="clarify-summary">
            <strong>{active.name || "Untitled event request"}</strong>
            {active.request_reference && <code>{active.request_reference}</code>}
            <span className={`request-status request-status--${active.status}`}>{statusLabel(active.status)}</span>
          </div>
          {reassigning && active.coordinator && (
            <p className="request-notice">
              Currently with <strong>{active.coordinator.name}</strong>. They will lose access, and everything linked to
              the event moves to the coordinator you pick.
            </p>
          )}

          {coordinators.length === 0 ? (
            <p className="request-notice">There are no other active coordinators to assign.</p>
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
                  <span className="assign-picker__workload">{workloadLabel(person.planning_count)}</span>
                </label>
              ))}
            </fieldset>
          )}

          {reassigning && (
            <label className="assign-reason">
              Reason for reassigning
              <textarea
                value={reason}
                maxLength={1000}
                rows={3}
                onChange={(event) => {
                  setReason(event.target.value);
                  setError(null);
                }}
              />
            </label>
          )}

          <div className="request-form__actions">
            <button className="request-button request-button--quiet" type="button" onClick={backToQueue}>
              Cancel
            </button>
            <button
              className="request-button request-button--primary"
              type="button"
              disabled={!picked || (reassigning && !reason.trim()) || saving}
              onClick={() => void confirmAssignment()}
            >
              {saving ? (reassigning ? "Reassigning…" : "Assigning…") : reassigning ? "Confirm reassignment" : "Confirm assignment"}
            </button>
          </div>
        </section>
      )}

      {screen === "done" && active && (
        <section className="request-confirmation" aria-labelledby="assigned-title">
          <span className="request-confirmation__mark" aria-hidden="true">✓</span>
          <h2 id="assigned-title">{reassigning ? "Event reassigned" : "Coordinator assigned"}</h2>
          <p>
            {active.name || "The request"} is {reassigning ? "now with" : "assigned to"} <strong>{assignedTo}</strong>
            {reassigning ? ". Everyone involved has been told." : " and is now under review."}
          </p>
          <div className="request-form__actions">
            <button className="request-button request-button--quiet" type="button" onClick={() => void openHistory(active)}>
              View assignment history
            </button>
            <button className="request-button request-button--primary" type="button" onClick={backToQueue}>
              Back to queue
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
