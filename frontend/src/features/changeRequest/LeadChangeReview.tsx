import { useEffect, useState } from "react";
import { RequestToDecide } from "./ChangeRequestReview";
import { changeReviewApi, decisionErrorMessage, statusWord } from "./changeRequestApi";
import type { ChangeRequestReview } from "./types";
import "./changeRequests.css";

interface LeadChangeReviewProps {
  requestId: string;
  // After a decision, so the Lead's list reloads.
  onDecided: () => void;
}

/**
 * US29b (SCRUM-144, D102): the Lead decides a coordinator's own US12 edit. Built from the change request alone
 * (GET /change-requests/{id}, acting_as=coordinator_lead): the edit's event is Planning or Confirmed, which only its
 * assigned coordinator may read (request_service._can_read). The same table and Approve / Reject as the coordinator's
 * panel; once decided, the request closes and only the outcome stays.
 */
export function LeadChangeReview({ requestId, onDecided }: LeadChangeReviewProps) {
  const [request, setRequest] = useState<ChangeRequestReview | null>(null);
  const [loads, setLoads] = useState(0);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    changeReviewApi
      .one(requestId, "coordinator_lead")
      .then((found) => {
        if (current) setRequest(found);
      })
      .catch((reason: unknown) => {
        if (current) setError(decisionErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, [requestId, loads]);

  return (
    <section className="change-decide" aria-label="Change requests for this event">
      <h2>Change request</h2>
      {request && (
        <p>
          <strong>{request.event_name ?? "Untitled event"}</strong> · {statusWord(request.event_status)}
        </p>
      )}
      {outcome && <p className="request-notice" role="status">{outcome}</p>}
      {error && <div className="request-alert" role="alert">{error}</div>}
      {request === null && !error ? (
        <p className="request-empty">Loading the change request…</p>
      ) : (
        request?.status === "pending_approval" &&
        !outcome && (
          <RequestToDecide
            request={request}
            eventStatus={request.event_status}
            onDecided={(message) => {
              setError(null);
              setOutcome(message);
              onDecided();
            }}
            onRefused={(message) => {
              setError(message);
              setLoads((count) => count + 1);
            }}
          />
        )
      )}
    </section>
  );
}
