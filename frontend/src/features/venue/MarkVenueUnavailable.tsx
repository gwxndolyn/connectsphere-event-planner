import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { venueApi, venueErrorMessage } from "./api";
import {
  BLOCK_REASONS,
  blockApi,
  blockErrorMessage,
  blockFieldErrors,
  blockReasonLabel,
  endBeforeStart,
  formatBlockPeriod,
  toBlockBody,
  type BlockFormValues,
} from "./blockApi";
import { eventName, formatBookingWindow } from "./bookingApi";
import type { VenueBlock } from "./bookingTypes";
import type { Venue } from "./types";
import "../eventRequest/eventRequests.css";
import "./venues.css";

const ACTIVE_VENUES = { q: "", minCapacity: "", facilities: [], accessibility: [], active: "all" as const };
const EMPTY: BlockFormValues = {
  venueId: "",
  startDate: "",
  startTime: "09:00",
  endDate: "",
  endTime: "18:00",
  reason: "",
  note: "",
};

/** What the recorded period did (AC 3, 4): which bookings now need rearranging, and who was told. */
function Recorded({ block }: { block: VenueBlock }) {
  const affected = block.affected_bookings;
  const already = block.already_affected_bookings ?? [];
  return (
    <div className="request-notice venue-block-result" role="status">
      <p>
        {block.venue.name} is unavailable from {formatBlockPeriod(block)}.
      </p>
      {affected.length === 0 ? (
        <p>{already.length === 0 ? "No bookings or holds were affected." : "No other bookings or holds were affected."}</p>
      ) : (
        <>
          <p>
            {affected.length === 1 ? "1 booking needs" : `${affected.length} bookings need`} rearrangement. Each event's
            coordinator and organiser have been told.
          </p>
          <ul aria-label="Bookings needing rearrangement">
            {affected.map((booking) => (
              <li key={booking.id}>
                {booking.reference}: {eventName(booking.event)}, {formatBookingWindow(booking)}
                {booking.status === "held" ? " (hold)" : ""}
              </li>
            ))}
          </ul>
        </>
      )}
      {/* D115: an earlier period already marked these; their people were told then, so not again. */}
      {already.length > 0 && (
        <>
          <p>Already needing rearrangement for an earlier period, so nobody was told again:</p>
          <ul aria-label="Bookings already needing rearrangement">
            {already.map((booking) => (
              <li key={booking.id}>
                {booking.reference}: {eventName(booking.event)}, {formatBookingWindow(booking)}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/**
 * US23a (SCRUM-90) AC 1 to 4: Venue staff mark a venue unavailable from a start to an end for a reason. Bookings and
 * holds the period overlaps need rearrangement, and their coordinators and organisers are told; the API does both.
 * New requests and approvals in the period are refused there too (AC 5).
 */
export function MarkVenueUnavailable() {
  const [open, setOpen] = useState(false);
  const [venues, setVenues] = useState<Venue[] | null>(null);
  const [form, setForm] = useState<BlockFormValues>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);
  const [recorded, setRecorded] = useState<VenueBlock | null>(null);
  // A second click before the first answer arrives would record the period twice (Matt's #133 review).
  const inFlight = useRef(false);

  useEffect(() => {
    if (!open || venues !== null) return;
    let current = true;
    venueApi
      .list(ACTIVE_VENUES, false)
      .then((result) => {
        if (current) setVenues(result);
      })
      .catch((reason: unknown) => {
        if (current) {
          setVenues([]);
          setError(venueErrorMessage(reason));
        }
      });
    return () => {
      current = false;
    };
  }, [open, venues]);

  function update(key: keyof BlockFormValues, value: string, ...apiFields: string[]) {
    setForm((current) => {
      const next = { ...current, [key]: value };
      // Most periods end on the day they start: fill the end date the first time.
      if (key === "startDate" && !current.endDate) next.endDate = value;
      return next;
    });
    setFieldErrors((current) => Object.fromEntries(Object.entries(current).filter(([field]) => !apiFields.includes(field))));
  }

  async function handleSubmit(submitted: FormEvent<HTMLFormElement>) {
    submitted.preventDefault();
    if (inFlight.current) return;
    setError(null);
    if (!form.venueId) {
      setFieldErrors({ venue_id: "Required." });
      setError("Complete the fields marked below.");
      return;
    }
    if (endBeforeStart(form)) {
      setFieldErrors({ ends_at: "The end must be after the start." });
      setError("Review the fields marked below and try again.");
      return;
    }
    setFieldErrors({});
    setSending(true);
    inFlight.current = true;
    try {
      setRecorded(await blockApi.markUnavailable(form.venueId, toBlockBody(form)));
      setOpen(false);
      setForm(EMPTY);
    } catch (reason) {
      setError(blockErrorMessage(reason));
      setFieldErrors(blockFieldErrors(reason));
    } finally {
      inFlight.current = false;
      setSending(false);
    }
  }

  function invalid(apiField: string) {
    return fieldErrors[apiField]
      ? { "aria-invalid": true as const, "aria-describedby": `venue-block-${apiField}-error` }
      : {};
  }

  function field(label: string, apiField: string, id: string, control: ReactNode) {
    const message = fieldErrors[apiField];
    return (
      <div className={`request-field${message ? " request-field--invalid" : ""}`}>
        <label htmlFor={id}>{label}</label>
        {control}
        {message && (
          <span id={`venue-block-${apiField}-error`} className="venue-field-error">
            {message}
          </span>
        )}
      </div>
    );
  }

  return (
    <section className="venue-holds" aria-labelledby="venue-block-title">
      <div className="venue-holds__heading">
        <h2 id="venue-block-title">Mark a venue unavailable</h2>
        {!open && (
          <button
            type="button"
            className="request-button request-button--secondary"
            onClick={() => {
              setOpen(true);
              setRecorded(null);
              if (error) {
                setError(null);
                setVenues(null);
              }
            }}
          >
            Mark unavailable
          </button>
        )}
      </div>
      {recorded && <Recorded block={recorded} />}
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      {open && (
        <form className="venue-booking-form" noValidate onSubmit={(submitted) => void handleSubmit(submitted)}>
          <p className="venue-booking__schedule">
            Bookings and holds in this period will need rearrangement, and their coordinators and organisers are told.
            New requests for the venue in this period are refused.
          </p>
          <div className="venue-filters">
            {field(
              "Venue",
              "venue_id",
              "venue-block-venue",
              <select
                id="venue-block-venue"
                value={form.venueId}
                onChange={(changed) => update("venueId", changed.target.value, "venue_id")}
                {...invalid("venue_id")}
              >
                <option value="">{venues === null ? "Loading venues…" : "Choose a venue"}</option>
                {(venues ?? []).map((venue) => (
                  <option key={venue.id} value={venue.id}>
                    {venue.name}
                  </option>
                ))}
              </select>,
            )}
            {field(
              "Start date",
              "starts_at",
              "venue-block-start-date",
              <input
                id="venue-block-start-date"
                type="date"
                value={form.startDate}
                onChange={(changed) => update("startDate", changed.target.value, "starts_at", "ends_at")}
                {...invalid("starts_at")}
              />,
            )}
            {field(
              "Start time",
              "starts_at_time",
              "venue-block-start-time",
              <input
                id="venue-block-start-time"
                type="time"
                value={form.startTime}
                onChange={(changed) => update("startTime", changed.target.value, "starts_at", "ends_at")}
              />,
            )}
            {field(
              "End date",
              "ends_at",
              "venue-block-end-date",
              <input
                id="venue-block-end-date"
                type="date"
                value={form.endDate}
                onChange={(changed) => update("endDate", changed.target.value, "ends_at")}
                {...invalid("ends_at")}
              />,
            )}
            {field(
              "End time",
              "ends_at_time",
              "venue-block-end-time",
              <input
                id="venue-block-end-time"
                type="time"
                value={form.endTime}
                onChange={(changed) => update("endTime", changed.target.value, "ends_at")}
              />,
            )}
            {field(
              "Reason",
              "reason",
              "venue-block-reason",
              <select
                id="venue-block-reason"
                value={form.reason}
                onChange={(changed) => update("reason", changed.target.value, "reason")}
                {...invalid("reason")}
              >
                <option value="">Choose a reason</option>
                {BLOCK_REASONS.map((reason) => (
                  <option key={reason} value={reason}>
                    {blockReasonLabel(reason)}
                  </option>
                ))}
              </select>,
            )}
          </div>
          {field(
            "Note (optional)",
            "note",
            "venue-block-note",
            <textarea
              id="venue-block-note"
              rows={2}
              maxLength={500}
              value={form.note}
              onChange={(changed) => update("note", changed.target.value, "note")}
              {...invalid("note")}
            />,
          )}
          <div className="request-form__actions">
            <button
              type="button"
              className="request-button request-button--quiet"
              onClick={() => {
                setOpen(false);
                setForm(EMPTY);
                setFieldErrors({});
                setError(null);
              }}
            >
              Cancel
            </button>
            <button type="submit" className="request-button request-button--primary" disabled={sending}>
              {sending ? "Saving…" : "Mark unavailable"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
