import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import type { EventRequest } from "../eventRequest/types";
import { venueApi, venueErrorMessage } from "./api";
import { bookingApi, bookingErrorMessage, bookingFieldErrors, missingForVenue, toBookingBody } from "./bookingApi";
import type { BookingFormValues, VenueBookingCreated } from "./bookingTypes";
import { ACCESSIBILITY_FEATURES, FACILITIES, ROOM_LAYOUTS, tagLabel } from "./tags";
import type { Venue } from "./types";
import "../eventRequest/eventRequests.css";
import "./venues.css";

const ACTIVE_VENUES = { q: "", minCapacity: "", facilities: [], accessibility: [], active: "all" as const };

function toggle(list: string[], tag: string): string[] {
  return list.includes(tag) ? list.filter((t) => t !== tag) : [...list, tag];
}

/** The event's own preferences (US1) as a starting point; the coordinator can change any of them. */
function initialValues(event: EventRequest): BookingFormValues {
  return {
    venueId: "",
    date: event.preferred_dates?.[0] ?? "",
    startTime: event.preferred_start_time?.slice(0, 5) ?? "",
    endTime: event.preferred_end_time?.slice(0, 5) ?? "",
    attendees: event.expected_attendees ? String(event.expected_attendees) : "",
    roomLayout: "",
    facilities: [],
    accessibility: [],
    specialRequirements: "",
  };
}

interface VenueBookingFormProps {
  event: EventRequest;
  onBooked: (booking: VenueBookingCreated) => void;
  onCancel: () => void;
}

/**
 * US22 AC 2 (SCRUM-113): request a venue for an approved event. Warns before sending when the venue
 * lacks something asked for, but still sends (AC 3). The API applies every rule (capacity, overlap,
 * blocks, the event's status) and its refusals are shown on the fields they concern.
 */
export function VenueBookingForm({ event, onBooked, onCancel }: VenueBookingFormProps) {
  const [form, setForm] = useState<BookingFormValues>(() => initialValues(event));
  const [venues, setVenues] = useState<Venue[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Keyed by the API's field names (venue_id, starts_at, …), as the errors arrive.
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let current = true;
    venueApi
      .list(ACTIVE_VENUES, false)
      .then((result) => {
        if (current) setVenues(result);
      })
      .catch((reason: unknown) => {
        if (current) setError(venueErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, []);

  const venue = venues.find((v) => v.id === form.venueId);
  const missing = venue ? missingForVenue(form, venue) : [];

  function update<K extends keyof BookingFormValues>(key: K, value: BookingFormValues[K], ...apiFields: string[]) {
    setForm((current) => ({ ...current, [key]: value }));
    if (apiFields.length > 0) {
      setFieldErrors((current) => Object.fromEntries(Object.entries(current).filter(([field]) => !apiFields.includes(field))));
    }
  }

  async function handleSubmit(submitted: FormEvent<HTMLFormElement>) {
    submitted.preventDefault();
    setSending(true);
    setError(null);
    setFieldErrors({});
    try {
      onBooked(await bookingApi.create(toBookingBody(event.id, form)));
    } catch (reason) {
      setError(bookingErrorMessage(reason));
      setFieldErrors(bookingFieldErrors(reason));
    } finally {
      setSending(false);
    }
  }

  function invalid(apiField: string) {
    const message = fieldErrors[apiField];
    return message
      ? { "aria-invalid": true as const, "aria-describedby": `venue-booking-${apiField}-error` }
      : { "aria-invalid": undefined, "aria-describedby": undefined };
  }

  function field(label: string, apiField: string, control: ReactNode, id = `venue-booking-${apiField}`) {
    const message = fieldErrors[apiField];
    return (
      <div className={`request-field${message ? " request-field--invalid" : ""}`}>
        <label htmlFor={id}>{label}</label>
        {control}
        {message && (
          <span id={`venue-booking-${apiField}-error`} className="venue-field-error">
            {message}
          </span>
        )}
      </div>
    );
  }

  return (
    <form className="venue-booking-form" noValidate onSubmit={(submitted) => void handleSubmit(submitted)}>
      <h3>Request a venue</h3>
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      <div className="venue-filters">
        {field(
          "Venue",
          "venue_id",
          <select
            id="venue-booking-venue_id"
            value={form.venueId}
            onChange={(changed) => update("venueId", changed.target.value, "venue_id", "expected_attendees", "starts_at")}
            {...invalid("venue_id")}
          >
            <option value="">Choose a venue</option>
            {venues.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} (capacity {v.capacity})
              </option>
            ))}
          </select>,
        )}
        {field(
          "Date",
          "date",
          <input
            id="venue-booking-date"
            type="date"
            value={form.date}
            onChange={(changed) => update("date", changed.target.value, "starts_at", "ends_at")}
          />,
        )}
        {field(
          "Start time",
          "starts_at",
          <input
            id="venue-booking-starts_at"
            type="time"
            value={form.startTime}
            onChange={(changed) => update("startTime", changed.target.value, "starts_at")}
            {...invalid("starts_at")}
          />,
        )}
        {field(
          "End time",
          "ends_at",
          <input
            id="venue-booking-ends_at"
            type="time"
            value={form.endTime}
            onChange={(changed) => update("endTime", changed.target.value, "ends_at")}
            {...invalid("ends_at")}
          />,
        )}
        {field(
          "Expected attendance",
          "expected_attendees",
          <input
            id="venue-booking-expected_attendees"
            type="number"
            min={1}
            value={form.attendees}
            onChange={(changed) => update("attendees", changed.target.value, "expected_attendees")}
            {...invalid("expected_attendees")}
          />,
        )}
        {field(
          "Layout",
          "room_layout",
          <select
            id="venue-booking-room_layout"
            value={form.roomLayout}
            onChange={(changed) => update("roomLayout", changed.target.value, "room_layout")}
            {...invalid("room_layout")}
          >
            <option value="">Choose a layout</option>
            {ROOM_LAYOUTS.map((layout) => (
              <option key={layout} value={layout}>
                {tagLabel(layout)}
              </option>
            ))}
          </select>,
        )}
        <fieldset className="venue-filters__tags">
          <legend>Required facilities</legend>
          {FACILITIES.map((tag) => (
            <label key={tag} className="venue-check">
              <input
                type="checkbox"
                checked={form.facilities.includes(tag)}
                onChange={() => update("facilities", toggle(form.facilities, tag), "required_facilities")}
              />
              {tagLabel(tag)}
            </label>
          ))}
          {fieldErrors.required_facilities && <span className="venue-field-error">{fieldErrors.required_facilities}</span>}
        </fieldset>
        <fieldset className="venue-filters__tags">
          <legend>Accessibility requirements</legend>
          {ACCESSIBILITY_FEATURES.map((tag) => (
            <label key={tag} className="venue-check">
              <input
                type="checkbox"
                checked={form.accessibility.includes(tag)}
                onChange={() => update("accessibility", toggle(form.accessibility, tag), "required_accessibility_features")}
              />
              {tagLabel(tag)}
            </label>
          ))}
          {fieldErrors.required_accessibility_features && (
            <span className="venue-field-error">{fieldErrors.required_accessibility_features}</span>
          )}
        </fieldset>
        <label className="request-field venue-form__wide">
          Special requirements
          <textarea
            rows={3}
            value={form.specialRequirements}
            onChange={(changed) => update("specialRequirements", changed.target.value)}
          />
        </label>
      </div>

      {missing.length > 0 && (
        <p className="venue-booking__gaps">
          This venue doesn't have: {missing.join(", ")}. You can still send the request.
        </p>
      )}

      <div className="request-form__actions">
        <button type="button" className="request-button request-button--quiet" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="request-button request-button--primary" disabled={sending}>
          {sending ? "Sending…" : "Send request"}
        </button>
      </div>
    </form>
  );
}
