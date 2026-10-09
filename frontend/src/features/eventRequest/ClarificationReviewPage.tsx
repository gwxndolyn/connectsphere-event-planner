import { useEffect, useState, type FormEvent } from "react";
import { ApiError, apiClient } from "../../api/client";
import { SECTIONS, displayValue, sectionLabel, statusLabel } from "./clarificationSections";
import type {
  ClarificationSection,
  ClarificationSent,
  EventRequest,
  EventRequestsResponse,
} from "./types";
import "./eventRequests.css";
import "./clarifications.css";

type Screen = "queue" | "review" | "sent";
// SCRUM-11 AC 2: the backend refuses other statuses with CLARIFICATION_NOT_ALLOWED.
const CLARIFIABLE_STATUSES = new Set(["submitted", "under_review"]);

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "The request could not be completed. Check the backend connection and try again.";
  if (error.code === "UNAUTHENTICATED") return "Set VITE_DEV_COORDINATOR_ID to the seeded coordinator ID, then restart the frontend.";
  if (error.code === "FORBIDDEN") return "Only coordinators can review requests. Switch \"Acting as\" to Coordinator.";
  if (error.code === "NOT_FOUND") return "This request is no longer available for review.";
  if (error.code === "MISSING_REQUIRED_FIELD") return "Choose at least one section and write a comment for the organiser.";
  if (error.code === "INVALID_CLARIFICATION") return "One of the chosen sections isn't recognised. Reload and try again.";
  if (error.code === "CLARIFICATION_NOT_ALLOWED") return "This request can't take a clarification request in its current status.";
  return `The backend rejected the request (${error.status}).`;
}

export function ClarificationReviewPage() {
  const [requests, setRequests] = useState<EventRequest[]>([]);
  const [screen, setScreen] = useState<Screen>("queue");
  const [activeRequest, setActiveRequest] = useState<EventRequest | null>(null);
  const [selected, setSelected] = useState<ClarificationSection[]>([]);
  const [comment, setComment] = useState("");
  const [invalidFields, setInvalidFields] = useState<string[]>([]);
  const [sent, setSent] = useState<ClarificationSent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let current = true;
    apiClient
      .get<EventRequestsResponse>("/api/v1/event-requests")
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

  async function openRequest(request: EventRequest) {
    setError(null);
    try {
      const latest = await apiClient.get<EventRequest>(`/api/v1/event-requests/${request.id}`);
      setActiveRequest(latest);
      setSelected([]);
      setComment("");
      setInvalidFields([]);
      setScreen("review");
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  function toggleSection(section: ClarificationSection) {
    setSelected((current) =>
      current.includes(section) ? current.filter((item) => item !== section) : [...current, section],
    );
    setInvalidFields((current) => current.filter((field) => field !== "sections"));
    setError(null);
  }

  async function sendClarification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeRequest) return;
    setSending(true);
    setError(null);
    setInvalidFields([]);
    const sections = SECTIONS.map((section) => section.key).filter((key) => selected.includes(key));
    try {
      const result = await apiClient.post<ClarificationSent>(
        `/api/v1/event-requests/${activeRequest.id}/clarifications`,
        { sections, comment },
      );
      setRequests((current) =>
        current.map((request) => (request.id === activeRequest.id ? { ...request, status: result.status } : request)),
      );
      setActiveRequest({ ...activeRequest, status: result.status });
      setSent(result);
      setScreen("sent");
    } catch (reason) {
      setError(errorMessage(reason));
      if (reason instanceof ApiError) setInvalidFields(reason.fields);
    } finally {
      setSending(false);
    }
  }

  function backToQueue() {
    setScreen("queue");
    setActiveRequest(null);
    setSent(null);
    setError(null);
  }

  const canClarify = activeRequest !== null && CLARIFIABLE_STATUSES.has(activeRequest.status);
  const sectionsInvalid = invalidFields.includes("sections");
  const commentInvalid = invalidFields.includes("comment");

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <p className="request-page__eyebrow">EVENT MANAGEMENT / REVIEW</p>
          <h1>{screen === "queue" ? "Requests to review" : screen === "review" ? "Review request" : "Clarification sent"}</h1>
        </div>
        {screen !== "queue" && (
          <button className="request-button request-button--quiet" type="button" onClick={backToQueue}>
            Back to review queue
          </button>
        )}
      </div>

      {error && <div className="request-alert" role="alert">{error}</div>}

      {screen === "queue" && (
        <section aria-label="Requests to review" className="request-list">
          {loading ? (
            <p className="request-empty" role="status">Loading requests…</p>
          ) : requests.length === 0 ? (
            <div className="request-empty">
              <p>No submitted requests to review.</p>
            </div>
          ) : (
            requests.map((request) => (
              <button
                className="request-row"
                key={request.id}
                type="button"
                onClick={() => void openRequest(request)}
              >
                <span className="request-row__main">
                  <strong>{request.name || "Untitled event request"}</strong>
                  <span>{request.event_category || "Category not set"}</span>
                </span>
                <span className={`request-status request-status--${request.status}`}>{statusLabel(request.status)}</span>
                {request.request_reference && <code className="request-row__reference">{request.request_reference}</code>}
                <span className="request-row__arrow" aria-hidden="true">›</span>
              </button>
            ))
          )}
        </section>
      )}

      {screen === "review" && activeRequest && (
        <form className="request-form" noValidate onSubmit={(event) => void sendClarification(event)}>
          <div className="clarify-summary">
            <strong>{activeRequest.name || "Untitled event request"}</strong>
            {activeRequest.request_reference && <code>{activeRequest.request_reference}</code>}
            <span className={`request-status request-status--${activeRequest.status}`}>{statusLabel(activeRequest.status)}</span>
          </div>

          <fieldset className={`clarify-sections${sectionsInvalid ? " clarify-sections--invalid" : ""}`} disabled={!canClarify}>
            <legend>Sections needing clarification</legend>
            {SECTIONS.map((section) => (
              <div className={`clarify-section${selected.includes(section.key) ? " clarify-section--selected" : ""}`} key={section.key}>
                <label className="clarify-section__pick">
                  <input
                    type="checkbox"
                    checked={selected.includes(section.key)}
                    onChange={() => toggleSection(section.key)}
                  />
                  {section.label}
                </label>
                <dl>
                  {section.fields.map(([field, label]) => (
                    <div key={field}>
                      <dt>{label}</dt>
                      <dd>{displayValue(activeRequest[field])}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </fieldset>

          {canClarify ? (
            <>
              <label className={`request-field request-field--wide${commentInvalid ? " request-field--invalid" : ""}`}>
                Comment for the organiser
                <textarea
                  aria-invalid={commentInvalid}
                  rows={4}
                  value={comment}
                  onChange={(event) => {
                    setComment(event.target.value);
                    setInvalidFields((current) => current.filter((field) => field !== "comment"));
                  }}
                />
              </label>
              <div className="request-form__actions">
                <button className="request-button request-button--quiet" type="button" onClick={backToQueue}>
                  Cancel
                </button>
                <button className="request-button request-button--primary" type="submit" disabled={sending}>
                  {sending ? "Sending…" : "Send clarification request"}
                </button>
              </div>
            </>
          ) : (
            <p className="request-notice">
              Clarification requests can only be sent while a request is submitted or under review. This one is{" "}
              {statusLabel(activeRequest.status)}.
            </p>
          )}
        </form>
      )}

      {screen === "sent" && sent && activeRequest && (
        <section className="request-confirmation" aria-labelledby="clarification-sent-title">
          <span className="request-confirmation__mark" aria-hidden="true">✓</span>
          <p className="request-page__eyebrow">ROUND {sent.clarification.round}</p>
          <h2 id="clarification-sent-title">Clarification request sent</h2>
          <p>
            {activeRequest.name || "The request"} is now{" "}
            <strong>{statusLabel(sent.status)}</strong>.
          </p>
          <ul className="clarify-sent-sections" aria-label="Sections sent">
            {(sent.clarification.sections ?? []).map((key) => (
              <li key={key}>{sectionLabel(key)}</li>
            ))}
          </ul>
          <button className="request-button request-button--primary" type="button" onClick={backToQueue}>
            Back to review queue
          </button>
        </section>
      )}
    </main>
  );
}
