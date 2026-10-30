import { type CSSProperties, useEffect, useId, useState } from "react";
import { statusLabel } from "../eventRequest/clarificationSections";
import { formatInstantTime } from "../registration/datetime";
import { calendarErrorMessage, venueApi, venueErrorMessage } from "./api";
import { bookingStatusLabel, eventName, formatBookingWindow, formatVenueTime, formatWindowTimes } from "./bookingApi";
import {
  type CalendarView,
  type HourSpan,
  type Segment,
  closedBands,
  dayLabel,
  daySegments,
  hourSpan,
  instantAt,
  monthDays,
  place,
  rangeFor,
  rangeTitle,
  singaporeToday,
  step,
  weekDays,
} from "./calendarGrid";
import type { CalendarItem, CalendarVenue, Venue, VenueCalendar as Calendar, VenueFilters } from "./types";
import "../registration/registration.css";
import "./venues.css";

// Every venue the reader may list: Venue staff see inactive ones too (US20 AC 6).
const ALL_VENUES: VenueFilters = { q: "", minCapacity: "", facilities: [], accessibility: [], active: "all" };

/** "Booking", "Booking (requested)" for a pending request (D57), or "Unavailable" for a block. */
function itemLabel(item: CalendarItem): string {
  return item.booking?.status === "requested" ? `${item.label} (requested)` : item.label;
}

/** The event's name for a booking (D58), the note for a block. */
function itemTitle(item: CalendarItem): string {
  return item.booking ? eventName(item.booking.event) : item.note || "Venue closed";
}

/** What a screen reader hears for an item: its label, what it is, its times and, for a booking, its occupied window. */
function itemName(item: CalendarItem): string {
  const name = `${itemLabel(item)}: ${itemTitle(item)}, ${formatWindowTimes(item)}`;
  return item.booking ? `${name}, occupied ${formatWindowTimes(item.occupied)}` : name;
}

function itemClass(item: CalendarItem): string {
  return [
    "venue-calendar__item",
    `venue-calendar__item--${item.kind}`,
    item.booking?.status === "requested" ? "venue-calendar__item--pending" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

/** The segment's own part of the day, e.g. "9:45 AM – 12:15 PM", clipped at midnight. */
function segmentTimes(day: string, segment: Segment): string {
  return `${formatInstantTime(instantAt(day, segment.startMinute))} – ${formatInstantTime(instantAt(day, segment.endMinute))}`;
}

interface VenueCalendarProps {
  // Venue Staff also see inactive venues in the picker.
  staff: boolean;
  // Today's Singapore day; tests fix it.
  today?: string;
}

/**
 * US21 (SCRUM-88, PR 2 SCRUM-123): a venue's bookings and closures on a week or month calendar, for
 * Coordinators, Leads and Venue staff (D56). Bookings span their occupied window with setup and
 * turnaround marked (AC 2), Requested ones marked pending (D57); closed hours are shaded (D61).
 */
export function VenueCalendar({ staff, today = singaporeToday() }: VenueCalendarProps) {
  const titleId = useId();
  const [venues, setVenues] = useState<Venue[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [venueId, setVenueId] = useState("");
  const [view, setView] = useState<CalendarView>("week");
  const [anchor, setAnchor] = useState(today);
  // The answer for one venue and range; anything else is still loading.
  const [result, setResult] = useState<{ key: string; calendar?: Calendar; error?: string } | null>(null);
  const [selected, setSelected] = useState<CalendarItem | null>(null);

  useEffect(() => {
    let current = true;
    venueApi
      .list(ALL_VENUES, staff)
      .then((list) => {
        if (current) setVenues(list);
      })
      .catch((reason: unknown) => {
        if (current) setListError(venueErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, [staff]);

  const range = rangeFor(view, anchor);
  const key = `${venueId}|${range.from}|${range.to}`;

  useEffect(() => {
    if (!venueId) return;
    // A late answer for a previous venue or range must not replace this one's.
    let current = true;
    const requested = `${venueId}|${range.from}|${range.to}`;
    venueApi
      .calendar(venueId, range.from, range.to)
      .then((calendar) => {
        if (current) setResult({ key: requested, calendar });
      })
      .catch((reason: unknown) => {
        if (current) setResult({ key: requested, error: calendarErrorMessage(reason) });
      });
    return () => {
      current = false;
    };
  }, [venueId, range.from, range.to]);

  const answer = result?.key === key ? result : null;

  return (
    <section className="venue-calendar" aria-labelledby={titleId}>
      <h2 id={titleId} className="venue-catalogue__title">
        Availability calendar
      </h2>

      <div className="venue-calendar__controls">
        <label className="request-field">
          Venue
          <select value={venueId} onChange={(event) => setVenueId(event.target.value)}>
            <option value="">Choose a venue</option>
            {venues.map((venue) => (
              <option key={venue.id} value={venue.id}>
                {venue.is_active ? venue.name : `${venue.name} (inactive)`}
              </option>
            ))}
          </select>
        </label>
        <div className="venue-calendar__buttons" role="group" aria-label="View">
          {(["week", "month"] as const).map((option) => (
            <button
              key={option}
              type="button"
              className={`request-button ${view === option ? "request-button--primary" : "request-button--secondary"}`}
              aria-pressed={view === option}
              onClick={() => setView(option)}
            >
              {option === "week" ? "Week" : "Month"}
            </button>
          ))}
        </div>
        <div className="venue-calendar__buttons">
          <button type="button" className="request-button request-button--quiet" onClick={() => setAnchor(step(view, anchor, -1))}>
            Previous
          </button>
          <button type="button" className="request-button request-button--quiet" onClick={() => setAnchor(today)}>
            Today
          </button>
          <button type="button" className="request-button request-button--quiet" onClick={() => setAnchor(step(view, anchor, 1))}>
            Next
          </button>
        </div>
      </div>
      <h3 className="venue-calendar__range">{rangeTitle(view, anchor)}</h3>

      {listError && (
        <div className="request-alert" role="alert">
          {listError}
        </div>
      )}
      {!venueId ? (
        <p className="request-empty">Choose a venue to see its calendar.</p>
      ) : !answer ? (
        <p className="request-empty" role="status">
          Loading calendar…
        </p>
      ) : answer.error || !answer.calendar ? (
        <div className="request-alert" role="alert">
          {answer.error}
        </div>
      ) : (
        <CalendarBody calendar={answer.calendar} view={view} anchor={anchor} onOpen={setSelected} />
      )}

      {selected && <ItemDetails item={selected} onClose={() => setSelected(null)} />}
    </section>
  );
}

interface CalendarBodyProps {
  calendar: Calendar;
  view: CalendarView;
  anchor: string;
  onOpen: (item: CalendarItem) => void;
}

function CalendarBody({ calendar, view, anchor, onOpen }: CalendarBodyProps) {
  // DECISION-PENDING: D59 — holds aren't drawn until US25 (SCRUM-93) adds them; none come back yet.
  const items = calendar.items.filter((item) => item.kind !== "hold");
  return (
    <>
      {items.length === 0 && (
        <p className="request-empty">
          Nothing booked or blocked at {calendar.venue.name} this {view}.
        </p>
      )}
      {view === "week" ? (
        <WeekGrid venue={calendar.venue} days={weekDays(anchor)} items={items} onOpen={onOpen} />
      ) : (
        <MonthGrid days={monthDays(anchor)} month={anchor.slice(0, 7)} items={items} onOpen={onOpen} />
      )}
    </>
  );
}

interface WeekGridProps {
  venue: CalendarVenue;
  days: string[];
  items: CalendarItem[];
  onOpen: (item: CalendarItem) => void;
}

// Tall enough that a 15-minute setup or turnaround (16px) holds its one-line label; bands keep their
// true length rather than a minimum height.
const HOUR_HEIGHT_PX = 64;

function WeekGrid({ venue, days, items, onOpen }: WeekGridProps) {
  const byDay = days.map((day) => ({ day, segments: daySegments(items, day) }));
  const span: HourSpan = hourSpan(
    venue,
    byDay.flatMap((d) => d.segments),
  );
  const hours = Array.from({ length: span.end - span.start }, (_, i) => span.start + i);
  const bands = closedBands(venue, span);
  const height = { height: `${hours.length * HOUR_HEIGHT_PX}px` };

  return (
    <div className="venue-calendar__week" style={{ "--hour-height": `${HOUR_HEIGHT_PX}px` } as CSSProperties}>
      <div className="venue-calendar__rail" aria-hidden="true">
        <div className="venue-calendar__day-head" />
        <div className="venue-calendar__day-body" style={height}>
          {hours.map((hour) => (
            <span key={hour} className="venue-calendar__hour" style={{ top: `${place(hour * 60, hour * 60, span).top}%` }}>
              {formatVenueTime(`${String(hour).padStart(2, "0")}:00:00`)}
            </span>
          ))}
        </div>
      </div>
      {byDay.map(({ day, segments }) => (
        <div key={day} className="venue-calendar__day" role="group" aria-label={dayLabel(day)}>
          <div className="venue-calendar__day-head" aria-hidden="true">
            {dayLabel(day)}
          </div>
          <div className="venue-calendar__day-body" style={height}>
            {bands.map((band) => {
              const { top, height: bandHeight } = place(band.startMinute, band.endMinute, span);
              return (
                <div key={band.startMinute} className="venue-calendar__closed" style={{ top: `${top}%`, height: `${bandHeight}%` }}>
                  Closed
                </div>
              );
            })}
            {segments.map((segment, index) => {
              const { item } = segment;
              const { top, height: itemHeight } = place(segment.startMinute, segment.endMinute, span);
              const length = segment.endMinute - segment.startMinute;
              return (
                <button
                  key={`${item.booking?.id ?? item.starts_at}-${index}`}
                  type="button"
                  className={itemClass(item)}
                  aria-label={itemName(item)}
                  style={{
                    top: `${top}%`,
                    height: `${itemHeight}%`,
                    left: `${(segment.lane / segment.lanes) * 100}%`,
                    width: `${100 / segment.lanes}%`,
                  }}
                  onClick={() => onOpen(item)}
                >
                  {segment.setupMinutes > 0 && (
                    <span className="venue-calendar__buffer" style={{ height: `${(segment.setupMinutes / length) * 100}%` }}>
                      Setup {segment.setupMinutes} min
                    </span>
                  )}
                  <span className="venue-calendar__item-main">
                    <strong>{itemLabel(item)}</strong> <span>{itemTitle(item)}</span>{" "}
                    <span className="venue-calendar__item-time">{segmentTimes(day, segment)}</span>
                  </span>
                  {segment.turnaroundMinutes > 0 && (
                    <span
                      className="venue-calendar__buffer venue-calendar__buffer--end"
                      style={{ height: `${(segment.turnaroundMinutes / length) * 100}%` }}
                    >
                      Turnaround {segment.turnaroundMinutes} min
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

interface MonthGridProps {
  days: string[];
  // "YYYY-MM": days outside it are muted.
  month: string;
  items: CalendarItem[];
  onOpen: (item: CalendarItem) => void;
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function MonthGrid({ days, month, items, onOpen }: MonthGridProps) {
  return (
    <div className="venue-calendar__month">
      {WEEKDAYS.map((weekday) => (
        <div key={weekday} className="venue-calendar__weekday" aria-hidden="true">
          {weekday}
        </div>
      ))}
      {days.map((day) => (
        <div
          key={day}
          className={`venue-calendar__cell${day.startsWith(month) ? "" : " venue-calendar__cell--outside"}`}
          role="group"
          aria-label={dayLabel(day)}
        >
          <span className="venue-calendar__date" aria-hidden="true">
            {Number(day.slice(8))}
          </span>
          <ul className="venue-calendar__chips">
            {daySegments(items, day).map((segment, index) => (
              <li key={`${segment.item.booking?.id ?? segment.item.starts_at}-${index}`}>
                <button
                  type="button"
                  className={itemClass(segment.item)}
                  aria-label={itemName(segment.item)}
                  onClick={() => onOpen(segment.item)}
                >
                  <strong>{itemLabel(segment.item)}</strong> <span>{segmentTimes(day, segment)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

interface ItemDetailsProps {
  item: CalendarItem;
  onClose: () => void;
}

/** AC 3: what an item is. The reference only when the API gives it (D58); no link into the request. */
function ItemDetails({ item, onClose }: ItemDetailsProps) {
  const titleId = useId();
  const { booking } = item;

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(e) => e.stopPropagation()}>
        <button type="button" className="dialog__close" onClick={onClose} aria-label="Close" autoFocus>
          ×
        </button>
        <h3 id={titleId} className="reg-form__title">
          {itemLabel(item)}
        </h3>
        <dl className="venue-calendar__details">
          {booking && (
            <>
              <div>
                <dt>Event</dt>
                <dd>{eventName(booking.event)}</dd>
              </div>
              <div>
                <dt>Event status</dt>
                <dd>{statusLabel(booking.event.status)}</dd>
              </div>
              <div>
                <dt>Booking status</dt>
                <dd>{bookingStatusLabel(booking.status)}</dd>
              </div>
            </>
          )}
          <div>
            <dt>Time</dt>
            <dd>{formatBookingWindow(item)}</dd>
          </div>
          {booking && (
            <div>
              <dt>Occupied</dt>
              <dd>{formatWindowTimes(item.occupied)} with setup and turnaround</dd>
            </div>
          )}
          {booking?.reference && (
            <div>
              <dt>Reference</dt>
              <dd>{booking.reference}</dd>
            </div>
          )}
          {!booking && item.note && (
            <div>
              <dt>Note</dt>
              <dd>{item.note}</dd>
            </div>
          )}
        </dl>
      </div>
    </div>
  );
}
