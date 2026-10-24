import type { EventRequest, UnassignedRequest } from "./types";
import { statusLabel } from "./clarificationSections";
import "./eventRequests.css";
import "./assignments.css";

interface Props {
  request: EventRequest | UnassignedRequest;
  onAssign: () => void;
  onHistory: () => void;
}

function value(text: string | number | null | undefined): string {
  return text === null || text === undefined || text === "" ? "Not set" : String(text);
}

/** SCRUM-86 AC 4: the Lead's read-only view of a listed event. The only actions are starting an
 * assignment (an unassigned request) and reading its history; approving, rejecting and confirming
 * belong to other roles. Reassigning arrives with US10e (SCRUM-83). */
export function LeadRequestDetail({ request, onAssign, onHistory }: Props) {
  const organiser = "organiser" in request ? request.organiser : null;
  const rows: [string, string][] = [
    ["Reference", value(request.request_reference)],
    ["Organiser", value(organiser?.name)],
    ["Coordinator", request.coordinator?.name ?? "Unassigned"],
    ["Category", value(request.event_category)],
    ["Purpose", value(request.purpose)],
    ["Preferred dates", request.preferred_dates?.length ? request.preferred_dates.join(", ") : "Not set"],
    ["Preferred time", request.preferred_start_time ? `${request.preferred_start_time.slice(0, 5)} to ${request.preferred_end_time?.slice(0, 5) ?? "?"}` : "Not set"],
    ["Expected attendance", value(request.expected_attendees)],
    ["Room layout", value(request.room_layout_preference)],
    ["Accessibility needs", value(request.accessibility_needs)],
    ["Equipment needs", value(request.equipment_needs)],
  ];
  return (
    <section className="request-form" aria-label="Request details">
      <div className="clarify-summary">
        <strong>{request.name || "Untitled event request"}</strong>
        <span className={`request-status request-status--${request.status}`}>{statusLabel(request.status)}</span>
      </div>
      <dl className="assign-detail">
        {rows.map(([label, text]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>
      <div className="request-form__actions">
        {request.coordinator ? (
          <button className="request-button request-button--quiet" type="button" onClick={onHistory}>
            Assignment history
          </button>
        ) : (
          <button className="request-button request-button--primary" type="button" onClick={onAssign}>
            Assign a coordinator
          </button>
        )}
      </div>
    </section>
  );
}
