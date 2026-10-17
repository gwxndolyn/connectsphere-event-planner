import { useId, useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { venueApi, venueErrorMessage, venueFieldErrors } from "./api";
import { ACCESSIBILITY_FEATURES, FACILITIES, ROOM_LAYOUTS, tagLabel } from "./tags";
import type { Venue, VenueField, VenueWrite } from "./types";

type TagField = "facilities" | "accessibility_features" | "room_layouts";

const TAG_GROUPS: { field: TagField; legend: string; tags: readonly string[] }[] = [
  { field: "facilities", legend: "Facilities", tags: FACILITIES },
  { field: "accessibility_features", legend: "Accessibility features", tags: ACCESSIBILITY_FEATURES },
  { field: "room_layouts", legend: "Room layouts", tags: ROOM_LAYOUTS },
];

// Number inputs are held as text so an empty box reaches the API as null (MISSING_REQUIRED_FIELD).
interface FormState {
  name: string;
  location: string;
  capacity: string;
  facilities: string[];
  accessibility_features: string[];
  room_layouts: string[];
  opens_at: string;
  closes_at: string;
  setup_minutes: string;
  turnaround_minutes: string;
}

function initialState(venue: Venue | null): FormState {
  if (!venue) {
    return {
      name: "",
      location: "",
      capacity: "",
      facilities: [],
      accessibility_features: [],
      room_layouts: [],
      opens_at: "08:00",
      closes_at: "22:00",
      setup_minutes: "0",
      turnaround_minutes: "0",
    };
  }
  return {
    name: venue.name,
    location: venue.location,
    capacity: String(venue.capacity),
    facilities: venue.facilities,
    accessibility_features: venue.accessibility_features,
    room_layouts: venue.room_layouts,
    opens_at: venue.opens_at.slice(0, 5),
    closes_at: venue.closes_at.slice(0, 5),
    setup_minutes: String(venue.setup_minutes),
    turnaround_minutes: String(venue.turnaround_minutes),
  };
}

function toNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

function toBody(state: FormState): VenueWrite {
  return {
    name: state.name,
    location: state.location,
    capacity: toNumber(state.capacity),
    facilities: state.facilities,
    accessibility_features: state.accessibility_features,
    room_layouts: state.room_layouts,
    opens_at: state.opens_at || null,
    closes_at: state.closes_at || null,
    setup_minutes: toNumber(state.setup_minutes),
    turnaround_minutes: toNumber(state.turnaround_minutes),
  };
}

interface VenueFormProps {
  venue: Venue | null;
  onSaved: (venue: Venue) => void;
  onCancel: () => void;
}

export function VenueForm({ venue, onSaved, onCancel }: VenueFormProps) {
  const [state, setState] = useState<FormState>(() => initialState(venue));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [buffersLocked, setBuffersLocked] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const formId = useId();

  function update<K extends keyof FormState>(field: K, value: FormState[K]) {
    setState((current) => ({ ...current, [field]: value }));
  }

  function toggleTag(field: TagField, tag: string) {
    setState((current) => ({
      ...current,
      [field]: current[field].includes(tag) ? current[field].filter((t) => t !== tag) : [...current[field], tag],
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setFieldErrors({});
    setBuffersLocked(null);
    try {
      const body = toBody(state);
      onSaved(venue ? await venueApi.update(venue.id, body) : await venueApi.create(body));
    } catch (reason: unknown) {
      if (reason instanceof ApiError && reason.code === "VENUE_BUFFERS_LOCKED") {
        setBuffersLocked(venueErrorMessage(reason));
      } else {
        setError(venueErrorMessage(reason));
        setFieldErrors(venueFieldErrors(reason));
      }
    } finally {
      setSaving(false);
    }
  }

  function textField(field: VenueField & keyof FormState, label: string, type = "text") {
    const message = fieldErrors[field];
    const inputId = `${formId}-${field}`;
    // The message stays outside the <label> so the input's accessible name is just the label.
    return (
      <div className={`request-field${message ? " request-field--invalid" : ""}`}>
        <label htmlFor={inputId}>{label}</label>
        <input
          id={inputId}
          type={type}
          min={type === "number" ? 0 : undefined}
          aria-invalid={Boolean(message)}
          aria-describedby={message ? `${inputId}-error` : undefined}
          value={state[field] as string}
          onChange={(event) => update(field, event.target.value)}
        />
        {message && (
          <span id={`${inputId}-error`} className="venue-field-error">
            {message}
          </span>
        )}
      </div>
    );
  }

  return (
    <form className="request-form" noValidate onSubmit={handleSubmit} aria-label={venue ? "Edit venue" : "Add venue"}>
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}

      <div className="request-form__section">
        <h2>Venue details</h2>
        {textField("name", "Venue name")}
        {textField("location", "Location")}
        {textField("capacity", "Capacity", "number")}
      </div>

      <div className="request-form__section">
        <h2>Operating hours and buffers</h2>
        {textField("opens_at", "Opens at", "time")}
        {textField("closes_at", "Closes at", "time")}
        {buffersLocked && (
          <div className="request-alert venue-form__wide" role="alert">
            {buffersLocked}
          </div>
        )}
        {textField("setup_minutes", "Setup minutes", "number")}
        {textField("turnaround_minutes", "Turnaround minutes", "number")}
      </div>

      {TAG_GROUPS.map(({ field, legend, tags }) => (
        <fieldset key={field} className="request-form__section venue-tags">
          <legend>{legend}</legend>
          {fieldErrors[field] && <span className="venue-field-error venue-form__wide">{fieldErrors[field]}</span>}
          <div className="venue-tags__options">
            {tags.map((tag) => (
              <label key={tag} className="venue-check">
                <input type="checkbox" checked={state[field].includes(tag)} onChange={() => toggleTag(field, tag)} />
                {tagLabel(tag)}
              </label>
            ))}
          </div>
        </fieldset>
      ))}

      <div className="request-form__actions">
        <button type="button" className="request-button request-button--secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="request-button request-button--primary" disabled={saving}>
          {saving ? "Saving…" : venue ? "Save changes" : "Add venue"}
        </button>
      </div>
    </form>
  );
}
