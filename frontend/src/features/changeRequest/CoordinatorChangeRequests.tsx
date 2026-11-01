import { useEffect, useState } from "react";
import { formatInstantDateTime } from "../registration/datetime";
import { changeReviewApi, decisionErrorMessage } from "./changeRequestApi";
import type { ChangeRequestReview } from "./types";
import "./changeRequests.css";

interface CoordinatorChangeRequestsProps {
  // Opens the event's review screen at its change requests.
  onReview: (eventId: string, requestId: string) => void;
  // SCRUM-144: the Lead's list, "Coordinator edits to approve", of coordinators' own US12 edits only (D102).
  heading?: string;
  source?: ChangeRequestReview["source"];
  // Changed after a decision elsewhere, so the list reloads.
  reloadKey?: number;
}

/**
 * US29b AC 1 (SCRUM-143): above the coordinator's review queue, every pending change request on the events assigned
 * to them, oldest first. Nothing shows while none waits. Deviation 69: placed here, the coordinator's Event requests
 * screen, because every status a request can be decided in opens from it.
 */
export function CoordinatorChangeRequests({
  onReview,
  heading = "Change requests to review",
  source,
  reloadKey = 0,
}: CoordinatorChangeRequestsProps) {
  const [requests, setRequests] = useState<ChangeRequestReview[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    changeReviewApi
      .pending()
      .then((found) => {
        // The API lists only what this user decides; a user holding both roles still sees one role's list.
        if (current) setRequests(source ? found.filter((request) => request.source === source) : found);
      })
      .catch((reason: unknown) => {
        if (current) setError(decisionErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, [source, reloadKey]);

  if (error) return <div className="request-alert" role="alert">{error}</div>;
  if (!requests || requests.length === 0) return null;
  return (
    <section className="change-queue" aria-labelledby="change-queue-title">
      <h2 id="change-queue-title">{heading} ({requests.length})</h2>
      <ul className="change-queue__list">
        {requests.map((request) => (
          <li className="change-queue__row" key={request.id} aria-label={`${request.event_name ?? "Untitled event"} change request`}>
            <span className="change-queue__main">
              <strong>{request.event_name ?? "Untitled event"}</strong>
              <span>
                {request.requested_by.name} · Requested {formatInstantDateTime(request.created_at)}
              </span>
            </span>
            {request.significant && <span className="change-badge change-badge--significant">Significant</span>}
            <button className="request-button request-button--quiet" type="button" onClick={() => onReview(request.event_id, request.id)}>
              Review
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
