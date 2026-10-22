import { useState, type FormEvent } from "react";
import { describeCriteria, hhmm, venueApi, venueErrorMessage, venueFieldErrors } from "./api";
import { ACCESSIBILITY_FEATURES, FACILITIES, tagLabel } from "./tags";
import type { VenueSearchForm, VenueSearchResponse } from "./types";
import "../eventRequest/eventRequests.css";
import "./venues.css";

const EMPTY_FORM: VenueSearchForm = {
  date: "",
  startTime: "",
  endTime: "",
  attendees: "",
  location: "",
  facilities: [],
  accessibility: [],
};

function toggle(list: string[], tag: string): string[] {
  return list.includes(tag) ? list.filter((t) => t !== tag) : [...list, tag];
}

/**
 * US2 (SCRUM-7): an Event Coordinator searches for venues free for a date, time and attendance,
 * narrowed by location, facilities and accessibility. The API applies every rule (capacity,
 * operating hours, holds, bookings and blocks), so this screen only shows what comes back.
 */
export function VenueSearch() {
  const [form, setForm] = useState<VenueSearchForm>(EMPTY_FORM);
  const [result, setResult] = useState<VenueSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [searching, setSearching] = useState(false);

  function update<K extends keyof VenueSearchForm>(key: K, value: VenueSearchForm[K], apiField?: string) {
    setForm((current) => ({ ...current, [key]: value }));
    if (apiField) setFieldErrors(({ [apiField]: _cleared, ...rest }) => rest);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearching(true);
    setError(null);
    setFieldErrors({});
    try {
      setResult(await venueApi.search(form));
    } catch (reason) {
      setResult(null);
      setError(venueErrorMessage(reason));
      setFieldErrors(venueFieldErrors(reason));
    } finally {
      setSearching(false);
    }
  }

  function field(label: string, key: "date" | "startTime" | "endTime" | "attendees", apiField: string, type: string) {
    const message = fieldErrors[apiField];
    const errorId = `venue-search-${apiField}-error`;
    return (
      <div className={`request-field${message ? " request-field--invalid" : ""}`}>
        <label htmlFor={`venue-search-${apiField}`}>{label}</label>
        <input
          id={`venue-search-${apiField}`}
          type={type}
          min={type === "number" ? 1 : undefined}
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? errorId : undefined}
          value={form[key]}
          onChange={(event) => update(key, event.target.value, apiField)}
        />
        {message && (
          <span id={errorId} className="venue-field-error">
            {message}
          </span>
        )}
      </div>
    );
  }

  return (
    <section className="venue-search" aria-labelledby="venue-search-title">
      <h2 id="venue-search-title">Find an available venue</h2>
      <form className="venue-filters" noValidate onSubmit={(event) => void handleSubmit(event)}>
        {field("Date", "date", "date", "date")}
        {field("Start time", "startTime", "start_time", "time")}
        {field("End time", "endTime", "end_time", "time")}
        {field("Expected attendance", "attendees", "attendees", "number")}
        <label className="request-field">
          Location
          <input
            type="text"
            value={form.location}
            placeholder="e.g. Library"
            onChange={(event) => update("location", event.target.value)}
          />
        </label>
        <fieldset className="venue-filters__tags">
          <legend>Required facilities</legend>
          {FACILITIES.map((tag) => (
            <label key={tag} className="venue-check">
              <input
                type="checkbox"
                checked={form.facilities.includes(tag)}
                onChange={() => update("facilities", toggle(form.facilities, tag), "facilities")}
              />
              {tagLabel(tag)}
            </label>
          ))}
        </fieldset>
        <fieldset className="venue-filters__tags">
          <legend>Accessibility requirements</legend>
          {ACCESSIBILITY_FEATURES.map((tag) => (
            <label key={tag} className="venue-check">
              <input
                type="checkbox"
                checked={form.accessibility.includes(tag)}
                onChange={() => update("accessibility", toggle(form.accessibility, tag), "accessibility")}
              />
              {tagLabel(tag)}
            </label>
          ))}
        </fieldset>
        <div className="request-form__actions venue-search__actions">
          <button type="button" className="request-button request-button--quiet" onClick={() => {
            setForm(EMPTY_FORM);
            setResult(null);
            setError(null);
            setFieldErrors({});
          }}>
            Clear
          </button>
          <button type="submit" className="request-button request-button--primary" disabled={searching}>
            {searching ? "Searching…" : "Search venues"}
          </button>
        </div>
      </form>

      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}

      {result &&
        (result.venues.length === 0 ? (
          <div className="request-empty venue-search__empty" role="status">
            <p>
              <strong>No matching venues.</strong> Nothing is free that fits all of these:
            </p>
            <ul aria-label="Criteria applied">
              {describeCriteria(result.criteria).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p>Try another date or time, fewer attendees, or fewer requirements.</p>
          </div>
        ) : (
          <>
            <p className="request-notice" role="status">
              {result.venues.length} {result.venues.length === 1 ? "venue is" : "venues are"} available, smallest first.
            </p>
            <ul className="venue-list" aria-label="Available venues">
              {result.venues.map((venue) => (
                <li key={venue.id} className="venue-card" aria-label={venue.name}>
                  <div className="venue-card__head">
                    <h3>{venue.name}</h3>
                  </div>
                  <p className="venue-card__location">{venue.location}</p>
                  <dl className="venue-card__facts">
                    <div>
                      <dt>Capacity</dt>
                      <dd>{venue.capacity}</dd>
                    </div>
                    <div>
                      <dt>Hours</dt>
                      <dd>
                        {hhmm(venue.opens_at)}–{hhmm(venue.closes_at)}
                      </dd>
                    </div>
                    <div>
                      <dt>Facilities</dt>
                      <dd>{venue.facilities.length ? venue.facilities.map(tagLabel).join(", ") : "None listed"}</dd>
                    </div>
                    <div>
                      <dt>Accessibility</dt>
                      <dd>
                        {venue.accessibility_features.length
                          ? venue.accessibility_features.map(tagLabel).join(", ")
                          : "None listed"}
                      </dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          </>
        ))}
    </section>
  );
}
