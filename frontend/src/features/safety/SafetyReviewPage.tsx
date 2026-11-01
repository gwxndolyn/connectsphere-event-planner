import { useEffect, useState } from "react";
import { ApiError, apiClient } from "../../api/client";
import { formatInstantDateTime } from "../registration/datetime";
import { areaLabel, checklistLabel } from "./checklist";
import type {
  ChecklistAnswer,
  ChecklistResult,
  SafetyQueueRow,
  SafetyReviewDetail,
  SafetyReviewInternal,
} from "./types";
import "../eventRequest/eventRequests.css";
import "./safety.css";

type Screen = "queue" | "review" | "done";

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "The request could not be completed. Check the backend connection and try again.";
  switch (error.code) {
    case "UNAUTHENTICATED":
      return "Set VITE_DEV_SAFETY_OFFICER_ID to the seeded Safety officer's ID, then restart the frontend.";
    case "FORBIDDEN":
      return "Only Safety officers can review events. Switch \"Acting as\" to Safety officer.";
    case "NOT_FOUND":
      return "This event is no longer available for a safety review.";
    case "SELF_DECISION_NOT_ALLOWED":
      return "You can't review an event you created or coordinate.";
    case "CHECKLIST_HAS_ISSUES":
      return "An item is marked Issue, so this can't be approved. Reject the arrangement, or mark the item satisfactory.";
    case "MISSING_REQUIRED_FIELD":
      return "Answer every checklist item, and give comments when rejecting or requesting changes. Tick at least one area when requesting changes.";
    case "SAFETY_REVIEW_NOT_ALLOWED":
      return {
        status: "This event can't be reviewed in its current status.",
        already_approved: "This event's safety has already been approved.",
        awaiting_revision:
          "This arrangement was rejected, or changes were requested. It's reviewed again once the coordinator sends it back.",
        arrangements_incomplete: "Its venue bookings or equipment are no longer all approved, so it isn't ready to review.",
        // US29b (SCRUM-143, D106).
        review_flags_open:
          "This event has arrangements to review after an approved change. It returns to the queue once its coordinator has reviewed them.",
      }[String(error.body.reason)] ?? "This event can't be reviewed right now.";
    default:
      return `The backend rejected the review (${error.status}).`;
  }
}

const OUTCOME_LABELS = { approved: "Approved", rejected: "Rejected", changes_requested: "Changes requested" };
const DONE_EYEBROWS = { approved: "APPROVED", rejected: "REJECTED", changes_requested: "CHANGES REQUESTED" };
const DONE_TITLES = { approved: "Safety approved", rejected: "Safety arrangement rejected", changes_requested: "Changes requested" };

function list(values: string[]): string {
  return values.length > 0 ? values.join(", ") : "None";
}

/**
 * US30a (SCRUM-99): the Safety Officer's queue (AC 1), each event's checklist review (AC 2) and the
 * decision, approve or reject the safety arrangement with comments (AC 3, 4). Internal notes stay with the
 * Safety Officer (AC 7); only the event details a review needs are shown (AC 9). SCRUM-100 (US30b): or
 * request changes, with comments and the areas affected (AC 1).
 */
export function SafetyReviewPage() {
  const [queue, setQueue] = useState<SafetyQueueRow[]>([]);
  const [screen, setScreen] = useState<Screen>("queue");
  const [detail, setDetail] = useState<SafetyReviewDetail | null>(null);
  const [answers, setAnswers] = useState<Record<string, { result?: ChecklistResult; comment: string }>>({});
  const [comments, setComments] = useState("");
  const [internalNotes, setInternalNotes] = useState("");
  const [areas, setAreas] = useState<string[]>([]);
  const [invalid, setInvalid] = useState<string[]>([]);
  const [done, setDone] = useState<SafetyReviewInternal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let current = true;
    apiClient
      .get<{ events: SafetyQueueRow[] }>("/api/v1/safety-reviews")
      .then((response) => {
        if (current) setQueue(response.events);
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

  async function open(row: SafetyQueueRow) {
    setError(null);
    try {
      const loaded = await apiClient.get<SafetyReviewDetail>(`/api/v1/safety-reviews/${row.event_id}`);
      setDetail(loaded);
      setAnswers({});
      setComments("");
      setInternalNotes("");
      setAreas([]);
      setInvalid([]);
      setScreen("review");
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  function answer(key: string, change: Partial<{ result: ChecklistResult; comment: string }>) {
    setAnswers((current) => ({ ...current, [key]: { ...current[key], comment: current[key]?.comment ?? "", ...change } }));
    setInvalid((current) => current.filter((field) => field !== `checklist.${key}`));
    setError(null);
  }

  function toggleArea(key: string) {
    setAreas((current) => (current.includes(key) ? current.filter((area) => area !== key) : [...current, key]));
    setInvalid((current) => current.filter((field) => field !== "areas"));
    setError(null);
  }

  async function submit(outcome: "approved" | "rejected" | "changes_requested") {
    if (!detail) return;
    const unanswered = detail.checklist.filter((item) => !answers[item.key]?.result).map((item) => `checklist.${item.key}`);
    const missing = [...unanswered];
    if (outcome !== "approved" && !comments.trim()) missing.push("comments");
    if (outcome === "changes_requested" && areas.length === 0) missing.push("areas");
    if (missing.length > 0) {
      setInvalid(missing);
      setError(errorMessage(new ApiError(422, "MISSING_REQUIRED_FIELD", missing)));
      return;
    }
    const checklist: Record<string, ChecklistAnswer> = {};
    for (const item of detail.checklist) {
      const given = answers[item.key];
      checklist[item.key] = { result: given.result as ChecklistResult, comment: given.comment.trim() || null };
    }
    setSaving(true);
    setError(null);
    try {
      const saved = await apiClient.post<SafetyReviewInternal>(`/api/v1/safety-reviews/${detail.event.id}`, {
        outcome,
        checklist,
        comments,
        internal_notes: internalNotes,
        ...(outcome === "changes_requested" ? { areas } : {}),
      });
      setQueue((current) => current.filter((row) => row.event_id !== detail.event.id));
      setDone(saved);
      setScreen("done");
    } catch (reason) {
      setError(errorMessage(reason));
      if (reason instanceof ApiError) setInvalid(reason.fields);
    } finally {
      setSaving(false);
    }
  }

  function backToQueue() {
    setScreen("queue");
    setDetail(null);
    setDone(null);
    setError(null);
  }

  // A rejection or a request for changes leaves the event in the status it was reviewed in: Approved or Planning.
  const status = (detail?.event.status ?? "planning").replaceAll("_", " ");

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <p className="request-page__eyebrow">EVENT MANAGEMENT / SAFETY</p>
          <h1>{screen === "queue" ? "Safety reviews" : screen === "review" ? "Safety review" : "Safety review recorded"}</h1>
        </div>
        {screen === "review" && (
          <button className="request-button request-button--quiet" type="button" onClick={backToQueue}>
            Back to safety reviews
          </button>
        )}
      </div>

      {error && <div className="request-alert" role="alert">{error}</div>}

      {screen === "queue" && (
        <section aria-label="Events to review" className="request-list">
          {loading ? (
            <p className="request-empty" role="status">Loading events…</p>
          ) : queue.length === 0 ? (
            <div className="request-empty">
              <p>No events are waiting for a safety review.</p>
            </div>
          ) : (
            queue.map((row) => (
              <button className="request-row" key={row.event_id} type="button" onClick={() => void open(row)}>
                <span className="request-row__main">
                  <strong>{row.name || "Untitled event"}</strong>
                  <span>{list(row.venues)}</span>
                </span>
                {row.resent && <span className="safety-badge">Sent back</span>}
                {row.request_reference && <code className="request-row__reference">{row.request_reference}</code>}
                <span className="request-row__arrow" aria-hidden="true">›</span>
              </button>
            ))
          )}
        </section>
      )}

      {screen === "review" && detail && (
        <form className="request-form" noValidate onSubmit={(event) => event.preventDefault()}>
          <div className="clarify-summary">
            <strong>{detail.event.name || "Untitled event"}</strong>
            {detail.event.request_reference && <code>{detail.event.request_reference}</code>}
          </div>

          <section className="safety-section" aria-label="Event details">
            <h2>Event</h2>
            <dl>
              <dt>Expected attendance</dt>
              <dd>{detail.event.expected_attendees ?? "Not set"}</dd>
              <dt>Room layout preference</dt>
              <dd>{detail.event.room_layout_preference || "Not set"}</dd>
              <dt>Accessibility needs</dt>
              <dd>{detail.event.accessibility_needs || "Not set"}</dd>
              <dt>Equipment needs</dt>
              <dd>{detail.event.equipment_needs || "Not set"}</dd>
            </dl>
          </section>

          {detail.venues.map((venue) => (
            <section className="safety-section" aria-label={`Venue ${venue.venue_name}`} key={venue.booking_reference}>
              <h2>{venue.venue_name}</h2>
              <dl>
                <dt>Location</dt>
                <dd>{venue.location}</dd>
                <dt>Capacity</dt>
                <dd>
                  {venue.venue_capacity} (booked for {venue.expected_attendees})
                </dd>
                <dt>When</dt>
                <dd>
                  {formatInstantDateTime(venue.starts_at)} to {formatInstantDateTime(venue.ends_at)}
                </dd>
                <dt>Layout</dt>
                <dd>{venue.room_layout}</dd>
                <dt>Venue facilities</dt>
                <dd>{list(venue.venue_facilities)}</dd>
                <dt>Venue accessibility</dt>
                <dd>{list(venue.venue_accessibility_features)}</dd>
                <dt>Requested facilities</dt>
                <dd>{list(venue.required_facilities)}</dd>
                <dt>Requested accessibility</dt>
                <dd>{list(venue.required_accessibility_features)}</dd>
                <dt>Special requirements</dt>
                <dd>{venue.special_requirements || "None"}</dd>
              </dl>
            </section>
          ))}

          <section className="safety-section" aria-label="Equipment">
            <h2>Equipment</h2>
            {detail.equipment.length === 0 ? (
              <p>No equipment was requested.</p>
            ) : (
              <ul>
                {detail.equipment.map((line) => (
                  <li key={line.equipment_type}>
                    {line.quantity} × {line.equipment_type}
                    {line.notes ? ` (${line.notes})` : ""}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {detail.history.length > 0 && (
            <section className="safety-section" aria-label="Earlier reviews">
              <h2>Earlier reviews</h2>
              {detail.history.map((review) => (
                <div className="safety-outcome" key={review.id}>
                  <strong>{OUTCOME_LABELS[review.outcome]}</strong> by {review.reviewer.name} on{" "}
                  {formatInstantDateTime(review.created_at)}
                  {review.areas && <p>Areas to review: {review.areas.map(areaLabel).join(", ")}</p>}
                  {review.comments && <p>Comments: {review.comments}</p>}
                  {review.internal_notes && <p>Internal notes: {review.internal_notes}</p>}
                </div>
              ))}
            </section>
          )}

          <h2>Checklist</h2>
          {detail.checklist.map((item) => {
            const marked = invalid.includes(`checklist.${item.key}`);
            return (
              <fieldset className="safety-check" key={item.key} aria-invalid={marked}>
                <legend>{item.label}</legend>
                <div className="safety-check__choices">
                  <label>
                    <input
                      type="radio"
                      name={item.key}
                      checked={answers[item.key]?.result === "satisfactory"}
                      onChange={() => answer(item.key, { result: "satisfactory" })}
                    />
                    Satisfactory
                  </label>
                  <label>
                    <input
                      type="radio"
                      name={item.key}
                      checked={answers[item.key]?.result === "issue"}
                      onChange={() => answer(item.key, { result: "issue" })}
                    />
                    Issue
                  </label>
                </div>
                <label className="request-field request-field--wide">
                  {item.label} comment
                  <input
                    type="text"
                    maxLength={1000}
                    value={answers[item.key]?.comment ?? ""}
                    onChange={(change) => answer(item.key, { comment: change.target.value })}
                  />
                </label>
              </fieldset>
            );
          })}

          <fieldset className="safety-check safety-areas" aria-invalid={invalid.includes("areas")}>
            <legend>Areas affected (tick at least one to request changes)</legend>
            <div className="safety-check__choices">
              {detail.change_areas.map((area) => (
                <label key={area.key}>
                  <input type="checkbox" checked={areas.includes(area.key)} onChange={() => toggleArea(area.key)} />
                  {area.label}
                </label>
              ))}
            </div>
          </fieldset>

          <label className={`request-field request-field--wide${invalid.includes("comments") ? " request-field--invalid" : ""}`}>
            Comments for the coordinator and organiser
            <textarea
              aria-invalid={invalid.includes("comments")}
              rows={4}
              maxLength={2000}
              value={comments}
              onChange={(change) => {
                setComments(change.target.value);
                setInvalid((current) => current.filter((field) => field !== "comments"));
              }}
            />
          </label>
          <label className="request-field request-field--wide">
            Internal notes (not shown to the organiser or coordinator)
            <textarea rows={3} maxLength={2000} value={internalNotes} onChange={(change) => setInternalNotes(change.target.value)} />
          </label>

          <div className="request-form__actions">
            <button
              className="request-button request-button--secondary"
              type="button"
              disabled={saving}
              onClick={() => void submit("rejected")}
            >
              Reject safety arrangement
            </button>
            <button
              className="request-button request-button--secondary"
              type="button"
              disabled={saving}
              onClick={() => void submit("changes_requested")}
            >
              Request changes
            </button>
            <button
              className="request-button request-button--primary"
              type="button"
              disabled={saving}
              onClick={() => void submit("approved")}
            >
              {saving ? "Saving…" : "Approve"}
            </button>
          </div>
        </form>
      )}

      {screen === "done" && done && detail && (
        <section className="request-confirmation" aria-labelledby="safety-done-title">
          <span className="request-confirmation__mark" aria-hidden="true">✓</span>
          <p className="request-page__eyebrow">{DONE_EYEBROWS[done.outcome]}</p>
          <h2 id="safety-done-title">{DONE_TITLES[done.outcome]}</h2>
          <p>
            {detail.event.name || "The event"}{" "}
            {done.outcome === "approved"
              ? "can now be confirmed by its coordinator."
              : done.outcome === "changes_requested"
                ? `stays in ${status} with the areas below marked for review. The coordinator makes the changes and marks them done, and it comes back to your queue.`
                : `stays in ${status}. The coordinator can revise the arrangement and send it for another review.`}
          </p>
          {done.areas && (
            <ul className="clarify-sent-sections" aria-label="Areas to review">
              {done.areas.map((key) => (
                <li key={key}>{areaLabel(key)}</li>
              ))}
            </ul>
          )}
          <ul className="clarify-sent-sections" aria-label="Checklist issues">
            {Object.entries(done.checklist)
              .filter(([, given]) => given.result === "issue")
              .map(([key, given]) => (
                <li key={key}>
                  {checklistLabel(key)}
                  {given.comment ? `: ${given.comment}` : ""}
                </li>
              ))}
          </ul>
          <button className="request-button request-button--primary" type="button" onClick={backToQueue}>
            Back to safety reviews
          </button>
        </section>
      )}
    </main>
  );
}
