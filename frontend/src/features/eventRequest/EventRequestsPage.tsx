import { useEffect, useState, type FormEvent } from "react";
import { ApiError, apiClient } from "../../api/client";
import { sectionLabel, statusLabel } from "./clarificationSections";
import type {
  Clarification,
  ClarificationSent,
  ClarificationThread,
  EventRequest,
  EventRequestsResponse,
  EventRequestWrite,
} from "./types";
import "./eventRequests.css";
import "./clarifications.css";

type Screen = "list" | "form" | "confirmation" | "respond" | "responded";
type RequestField = keyof EventRequestWrite;

const FIELD_LABELS: Record<RequestField, string> = {
  name: "Event name",
  event_category: "Event category",
  purpose: "Purpose / description",
  preferred_dates: "Preferred date",
  preferred_start_time: "Preferred start time",
  preferred_end_time: "Preferred end time",
  expected_attendees: "Expected attendees",
  room_layout_preference: "Room layout preference",
  accessibility_needs: "Accessibility needs",
  equipment_needs: "Equipment needs",
  registration_required: "Attendee registration",
};

function emptyRequest(): EventRequestWrite {
  return {
    name: "",
    event_category: "",
    purpose: "",
    preferred_dates: [],
    preferred_start_time: null,
    preferred_end_time: null,
    expected_attendees: null,
    room_layout_preference: "",
    accessibility_needs: "",
    equipment_needs: "",
    registration_required: null,
  };
}

function requestFields(request: EventRequest): EventRequestWrite {
  return {
    name: request.name,
    event_category: request.event_category,
    purpose: request.purpose,
    preferred_dates: request.preferred_dates,
    preferred_start_time: request.preferred_start_time,
    preferred_end_time: request.preferred_end_time,
    expected_attendees: request.expected_attendees,
    room_layout_preference: request.room_layout_preference,
    accessibility_needs: request.accessibility_needs,
    equipment_needs: request.equipment_needs,
    registration_required: request.registration_required,
  };
}

function includePendingDate(fields: EventRequestWrite, dateDraft: string): EventRequestWrite {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateDraft)) return fields;

  const parsedDate = new Date(`${dateDraft}T00:00:00.000Z`);
  if (Number.isNaN(parsedDate.valueOf()) || parsedDate.toISOString().slice(0, 10) !== dateDraft) {
    return fields;
  }

  const preferredDates = fields.preferred_dates ?? [];
  if (preferredDates.includes(dateDraft)) return fields;
  return { ...fields, preferred_dates: [...preferredDates, dateDraft] };
}

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "The request could not be completed. Check the backend connection and try again.";
  if (error.code === "UNAUTHENTICATED") return "Set VITE_DEV_USER_ID to the seeded organiser ID, then restart the frontend.";
  if (error.code === "NOT_FOUND") return "This request is no longer available to your account.";
  if (error.code === "EVENT_REQUEST_LOCKED") return "This request has been submitted and can no longer be edited.";
  if (error.code === "MISSING_REQUIRED_FIELD") return "Complete the fields marked below before submitting.";
  if (error.code === "INVALID_EVENT_REQUEST") return "Review the fields marked below and try again.";
  if (error.code === "NO_OPEN_CLARIFICATION") return "This clarification has already been answered.";
  return `The backend rejected the request (${error.status}).`;
}

export function EventRequestsPage() {
  const [requests, setRequests] = useState<EventRequest[]>([]);
  const [screen, setScreen] = useState<Screen>("list");
  const [activeRequest, setActiveRequest] = useState<EventRequest | null>(null);
  const [fields, setFields] = useState<EventRequestWrite>(emptyRequest);
  const [dateDraft, setDateDraft] = useState("");
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // US8c: the coordinator's open question, and the organiser's answer to it (SCRUM-78).
  const [openQuestion, setOpenQuestion] = useState<Clarification | null>(null);
  const [answer, setAnswer] = useState("");
  const [answerInvalid, setAnswerInvalid] = useState(false);
  const [responded, setResponded] = useState<ClarificationSent | null>(null);

  useEffect(() => {
    let current = true;
    apiClient
      .get<EventRequestsResponse>("/api/v1/me/event-requests")
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

  function openNewRequest() {
    setActiveRequest(null);
    setFields(emptyRequest());
    setDateDraft("");
    setMissingFields([]);
    setError(null);
    setNotice("");
    setScreen("form");
  }

  async function openRequest(request: EventRequest) {
    setError(null);
    setNotice("");
    if (request.status === "awaiting_clarification") {
      try {
        const thread = await apiClient.get<ClarificationThread>(`/api/v1/event-requests/${request.id}/clarifications`);
        const questions = thread.clarifications.filter((message) => message.kind === "request");
        setActiveRequest(request);
        setOpenQuestion(questions[questions.length - 1] ?? null);
        setAnswer("");
        setAnswerInvalid(false);
        setScreen("respond");
      } catch (reason) {
        setError(errorMessage(reason));
      }
      return;
    }
    if (request.status !== "draft") {
      setActiveRequest(request);
      setScreen("confirmation");
      return;
    }

    try {
      const latest = await apiClient.get<EventRequest>(`/api/v1/event-requests/${request.id}`);
      setActiveRequest(latest);
      setFields(requestFields(latest));
      setDateDraft(latest.preferred_dates?.[0] ?? "");
      setMissingFields([]);
      setScreen("form");
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  function updateField<K extends RequestField>(field: K, value: EventRequestWrite[K]) {
    setFields((current) => ({ ...current, [field]: value }));
    setMissingFields((current) => current.filter((missing) => missing !== field));
    setError(null);
  }

  function addDate() {
    if (!dateDraft) return;
    const dates = fields.preferred_dates ?? [];
    if (!dates.includes(dateDraft)) updateField("preferred_dates", [...dates, dateDraft]);
    setDateDraft("");
  }

  function removeDate(date: string) {
    updateField("preferred_dates", (fields.preferred_dates ?? []).filter((item) => item !== date));
  }

  function replaceInList(saved: EventRequest) {
    setRequests((current) => {
      const exists = current.some((request) => request.id === saved.id);
      return exists
        ? current.map((request) => (request.id === saved.id ? saved : request))
        : [saved, ...current];
    });
    setActiveRequest(saved);
    setFields(requestFields(saved));
  }

  async function persistDraft(): Promise<EventRequest | null> {
    setSaving(true);
    setError(null);
    setMissingFields([]);
    const requestFields = includePendingDate(fields, dateDraft);
    try {
      const saved = activeRequest
        ? await apiClient.patch<EventRequest>(
            `/api/v1/event-requests/${activeRequest.id}`,
            requestFields,
          )
        : await apiClient.post<EventRequest>("/api/v1/event-requests", requestFields);
      replaceInList(saved);
      return saved;
    } catch (reason) {
      setError(errorMessage(reason));
      if (reason instanceof ApiError && reason.fields.length > 0) {
        setMissingFields(reason.fields);
      }
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function saveDraft() {
    const saved = await persistDraft();
    if (saved) setNotice("Draft saved");
  }

  async function submitRequest() {
    const draft = await persistDraft();
    if (!draft) return;
    setSaving(true);
    try {
      const submitted = await apiClient.post<EventRequest>(
        `/api/v1/event-requests/${draft.id}/submit`,
        {},
      );
      replaceInList(submitted);
      setScreen("confirmation");
    } catch (reason) {
      setError(errorMessage(reason));
      if (reason instanceof ApiError && reason.fields.length > 0) {
        setMissingFields(reason.fields);
      }
    } finally {
      setSaving(false);
    }
  }

  function handleFormSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitRequest();
  }

  async function sendResponse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeRequest) return;
    setSaving(true);
    setError(null);
    setAnswerInvalid(false);
    try {
      const result = await apiClient.post<ClarificationSent>(
        `/api/v1/event-requests/${activeRequest.id}/clarifications/response`,
        { comment: answer },
      );
      const updated = { ...activeRequest, status: result.status };
      setRequests((current) => current.map((request) => (request.id === updated.id ? updated : request)));
      setActiveRequest(updated);
      setResponded(result);
      setScreen("responded");
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "MISSING_REQUIRED_FIELD") {
        setError("Write a response before sending it.");
        setAnswerInvalid(true);
      } else {
        setError(errorMessage(reason));
      }
    } finally {
      setSaving(false);
    }
  }

  function backToList() {
    setScreen("list");
    setActiveRequest(null);
    setOpenQuestion(null);
    setResponded(null);
    setError(null);
    setNotice("");
  }

  const headings: Record<Screen, string> = {
    list: "My event requests",
    form: "Event request",
    confirmation: "Submission confirmed",
    respond: "Clarification requested",
    responded: "Response sent",
  };
  const dateFieldInvalid = missingFields.includes("preferred_dates");

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <p className="request-page__eyebrow">EVENT MANAGEMENT / REQUESTS</p>
          <h1>{headings[screen]}</h1>
        </div>
        {screen === "list" && (
          <button className="request-button request-button--primary" type="button" onClick={openNewRequest}>
            <span aria-hidden="true">+</span> Create request
          </button>
        )}
        {screen !== "list" && (
          <button className="request-button request-button--quiet" type="button" onClick={backToList}>
            Back to my requests
          </button>
        )}
      </div>

      {error && <div className="request-alert" role="alert">{error}</div>}

      {screen === "list" && (
        <section aria-label="Your event requests" className="request-list">
          {loading ? (
            <p className="request-empty" role="status">Loading requests…</p>
          ) : requests.length === 0 ? (
            <div className="request-empty">
              <p>No requests yet.</p>
              <button className="request-button request-button--primary" type="button" onClick={openNewRequest}>
                Create your first request
              </button>
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

      {screen === "form" && (
        <form className="request-form" noValidate onSubmit={handleFormSubmit}>
          <div className="request-form__section">
            <h2>Event details</h2>
            <label className={`request-field${missingFields.includes("name") ? " request-field--invalid" : ""}`}>
              Event name
              <input
                aria-invalid={missingFields.includes("name")}
                value={fields.name ?? ""}
                onChange={(event) => updateField("name", event.target.value)}
              />
            </label>
            <label className={`request-field${missingFields.includes("event_category") ? " request-field--invalid" : ""}`}>
              Event category
              <input
                aria-invalid={missingFields.includes("event_category")}
                value={fields.event_category ?? ""}
                onChange={(event) => updateField("event_category", event.target.value)}
              />
            </label>
            <label className={`request-field request-field--wide${missingFields.includes("purpose") ? " request-field--invalid" : ""}`}>
              Purpose / description
              <textarea
                aria-invalid={missingFields.includes("purpose")}
                rows={4}
                value={fields.purpose ?? ""}
                onChange={(event) => updateField("purpose", event.target.value)}
              />
            </label>
          </div>

          <div className="request-form__section">
            <h2>Preferred schedule</h2>
            <div className={`request-date-entry${dateFieldInvalid ? " request-field--invalid" : ""}`}>
              <label className="request-field" htmlFor="preferred-date">Preferred date</label>
              <div className="request-date-entry__controls">
                <input
                  id="preferred-date"
                  aria-invalid={dateFieldInvalid}
                  type="date"
                  value={dateDraft}
                  onChange={(event) => setDateDraft(event.target.value)}
                />
                <button className="request-button request-button--quiet" type="button" onClick={addDate}>
                  Add date
                </button>
              </div>
              {!!fields.preferred_dates?.length && (
                <ul className="request-dates" aria-label="Selected preferred dates">
                  {fields.preferred_dates.map((date) => (
                    <li key={date}>
                      <span>{date}</span>
                      <button type="button" aria-label={`Remove ${date}`} onClick={() => removeDate(date)}>×</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <label className={`request-field${missingFields.includes("preferred_start_time") ? " request-field--invalid" : ""}`}>
              Preferred start time
              <input
                aria-invalid={missingFields.includes("preferred_start_time")}
                type="time"
                value={fields.preferred_start_time ?? ""}
                onChange={(event) => updateField("preferred_start_time", event.target.value || null)}
              />
            </label>
            <label className={`request-field${missingFields.includes("preferred_end_time") ? " request-field--invalid" : ""}`}>
              Preferred end time
              <input
                aria-invalid={missingFields.includes("preferred_end_time")}
                type="time"
                value={fields.preferred_end_time ?? ""}
                onChange={(event) => updateField("preferred_end_time", event.target.value || null)}
              />
            </label>
          </div>

          <div className="request-form__section">
            <h2>Planning requirements</h2>
            <label className={`request-field${missingFields.includes("expected_attendees") ? " request-field--invalid" : ""}`}>
              Expected attendees
              <input
                aria-invalid={missingFields.includes("expected_attendees")}
                type="number"
                min="1"
                value={fields.expected_attendees ?? ""}
                onChange={(event) => updateField("expected_attendees", event.target.value === "" ? null : Number(event.target.value))}
              />
            </label>
            <label className="request-field">
              Room layout preference
              <input
                value={fields.room_layout_preference ?? ""}
                onChange={(event) => updateField("room_layout_preference", event.target.value)}
              />
            </label>
            <label className="request-field">
              Accessibility needs
              <textarea
                rows={2}
                value={fields.accessibility_needs ?? ""}
                onChange={(event) => updateField("accessibility_needs", event.target.value)}
              />
            </label>
            <label className="request-field">
              Equipment needs
              <textarea
                rows={2}
                value={fields.equipment_needs ?? ""}
                onChange={(event) => updateField("equipment_needs", event.target.value)}
              />
            </label>
            <label className="request-field">
              Attendee registration
              <select
                value={fields.registration_required === null ? "" : String(fields.registration_required)}
                onChange={(event) => updateField("registration_required", event.target.value === "" ? null : event.target.value === "true")}
              >
                <option value="">Not decided</option>
                <option value="true">Required</option>
                <option value="false">Not required</option>
              </select>
            </label>
          </div>

          {notice && <p className="request-notice" role="status">{notice}</p>}
          {missingFields.length > 0 && (
            <div className="request-missing" aria-live="polite">
              <strong>Fields to complete</strong>
              <ul>
                {missingFields.map((field) => (
                  <li key={field}>{FIELD_LABELS[field as RequestField] ?? field}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="request-form__actions">
            <button className="request-button request-button--quiet" type="button" onClick={backToList}>
              Cancel
            </button>
            <button className="request-button request-button--secondary" type="button" disabled={saving} onClick={() => void saveDraft()}>
              Save draft
            </button>
            <button className="request-button request-button--primary" type="submit" disabled={saving}>
              {saving ? "Saving…" : "Submit request"}
            </button>
          </div>
        </form>
      )}

      {screen === "respond" && activeRequest && (
        <form className="request-form" noValidate onSubmit={(event) => void sendResponse(event)}>
          <div className="clarify-summary">
            <strong>{activeRequest.name || "Untitled event request"}</strong>
            {activeRequest.request_reference && <code>{activeRequest.request_reference}</code>}
            <span className={`request-status request-status--${activeRequest.status}`}>{statusLabel(activeRequest.status)}</span>
          </div>

          {openQuestion ? (
            <section className="clarify-question" aria-labelledby="clarify-question-title">
              <h2 id="clarify-question-title">The coordinator asks</h2>
              <ul className="clarify-sent-sections" aria-label="Sections in question">
                {(openQuestion.sections ?? []).map((key) => (
                  <li key={key}>{sectionLabel(key)}</li>
                ))}
              </ul>
              <blockquote>{openQuestion.comment}</blockquote>
              <p className="clarify-question__meta">
                Round {openQuestion.round} · {new Date(openQuestion.created_at).toLocaleString()}
              </p>
            </section>
          ) : (
            <p className="request-notice">The coordinator's question couldn't be loaded.</p>
          )}

          <label className={`request-field request-field--wide${answerInvalid ? " request-field--invalid" : ""}`}>
            Your response
            <textarea
              aria-invalid={answerInvalid}
              rows={5}
              value={answer}
              onChange={(event) => {
                setAnswer(event.target.value);
                setAnswerInvalid(false);
              }}
            />
          </label>
          <div className="request-form__actions">
            <button className="request-button request-button--quiet" type="button" onClick={backToList}>
              Cancel
            </button>
            <button className="request-button request-button--primary" type="submit" disabled={saving}>
              {saving ? "Sending…" : "Send response"}
            </button>
          </div>
        </form>
      )}

      {screen === "responded" && activeRequest && responded && (
        <section className="request-confirmation" aria-labelledby="response-sent-title">
          <span className="request-confirmation__mark" aria-hidden="true">✓</span>
          <p className="request-page__eyebrow">ROUND {responded.clarification.round}</p>
          <h2 id="response-sent-title">Response sent</h2>
          <p>
            {activeRequest.name || "Your request"} is back <strong>{statusLabel(responded.status)}</strong>.
          </p>
          <button className="request-button request-button--primary" type="button" onClick={backToList}>
            Back to my requests
          </button>
        </section>
      )}

      {screen === "confirmation" && activeRequest && (
        <section className="request-confirmation" aria-labelledby="request-confirmation-title">
          <span className="request-confirmation__mark" aria-hidden="true">✓</span>
          <p className="request-page__eyebrow">REQUEST RECEIVED</p>
          <h2 id="request-confirmation-title">Submission confirmed</h2>
          <p>Your event request has been received.</p>
          <div className="request-confirmation__reference">
            <span>Tracking reference</span>
            <code>{activeRequest.request_reference}</code>
          </div>
          <button className="request-button request-button--primary" type="button" onClick={backToList}>
            Back to my requests
          </button>
        </section>
      )}
    </main>
  );
}