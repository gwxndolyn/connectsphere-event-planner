import { useEffect, useState } from "react";
import { venueApi, venueErrorMessage } from "./api";
import { ACCESSIBILITY_FEATURES, FACILITIES, tagLabel } from "./tags";
import type { ActiveFilter, Venue, VenueFilters } from "./types";
import { PendingBookings } from "./PendingBookings";
import { VenueCalendar } from "./VenueCalendar";
import { VenueForm } from "./VenueForm";
import { VenueSearch } from "./VenueSearch";
import "../eventRequest/eventRequests.css";
import "./venues.css";

const EMPTY_FILTERS: VenueFilters = { q: "", minCapacity: "", facilities: [], accessibility: [], active: "all" };

function toggle(list: string[], tag: string): string[] {
  return list.includes(tag) ? list.filter((t) => t !== tag) : [...list, tag];
}

function hours(venue: Venue): string {
  return `${venue.opens_at.slice(0, 5)}–${venue.closes_at.slice(0, 5)}`;
}

interface VenuesPageProps {
  // Venue Staff may add, edit, deactivate and reactivate; everyone else reads active venues (AC 6).
  staff: boolean;
  // US2: coordinators search for an available venue above the catalogue (D20).
  canSearch?: boolean;
  // US21 (SCRUM-88): Coordinators, Leads and Venue staff see a venue's availability calendar (D56).
  calendar?: boolean;
}

export function VenuesPage({ staff, canSearch = false, calendar = false }: VenuesPageProps) {
  const [filters, setFilters] = useState<VenueFilters>(EMPTY_FILTERS);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  // undefined: the list; null: the add form; a venue: its edit form.
  const [editing, setEditing] = useState<Venue | null | undefined>(undefined);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let current = true;
    venueApi
      .list(filters, staff)
      .then((result) => {
        if (current) {
          setVenues(result);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (current) setError(venueErrorMessage(reason));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [filters, staff, reloadKey]);

  async function setActive(venue: Venue, active: boolean) {
    setError(null);
    try {
      const saved = await venueApi.setActive(venue.id, active);
      setNotice(`${saved.name} is ${active ? "active again" : "deactivated"}.`);
      setReloadKey((key) => key + 1);
    } catch (reason: unknown) {
      setError(venueErrorMessage(reason));
    }
  }

  if (editing !== undefined) {
    return (
      <main className="request-page">
        <div className="request-page__heading">
          <div>
            <span className="request-page__eyebrow">VENUE CATALOGUE</span>
            <h1>{editing ? `Edit ${editing.name}` : "Add a venue"}</h1>
          </div>
        </div>
        <VenueForm
          key={editing?.id ?? "new"}
          venue={editing}
          onCancel={() => setEditing(undefined)}
          onSaved={(saved) => {
            setNotice(`${saved.name} saved.`);
            setEditing(undefined);
            setReloadKey((key) => key + 1);
          }}
        />
      </main>
    );
  }

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <span className="request-page__eyebrow">VENUE CATALOGUE</span>
          <h1>Venues</h1>
        </div>
        {staff && (
          <button
            type="button"
            className="request-button request-button--primary"
            onClick={() => {
              setNotice("");
              setEditing(null);
            }}
          >
            Add venue
          </button>
        )}
      </div>

      {notice && (
        <p className="request-notice" role="status">
          {notice}
        </p>
      )}
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}

      {staff && <PendingBookings />}
      {canSearch && <VenueSearch />}
      {calendar && <VenueCalendar staff={staff} />}

      {(canSearch || calendar) && <h2 className="venue-catalogue__title">All venues</h2>}
      <section className="venue-filters" aria-label="Venue filters">
        <label className="request-field">
          Search by name
          <input
            type="search"
            value={filters.q}
            onChange={(event) => setFilters({ ...filters, q: event.target.value })}
            placeholder="e.g. Seminar"
          />
        </label>
        <label className="request-field">
          Minimum capacity
          <input
            type="number"
            min={1}
            value={filters.minCapacity}
            onChange={(event) => setFilters({ ...filters, minCapacity: event.target.value })}
          />
        </label>
        {staff && (
          <label className="request-field">
            Status
            <select
              value={filters.active}
              onChange={(event) => setFilters({ ...filters, active: event.target.value as ActiveFilter })}
            >
              <option value="all">All venues</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
        )}
        <fieldset className="venue-filters__tags">
          <legend>Facilities</legend>
          {FACILITIES.map((tag) => (
            <label key={tag} className="venue-check">
              <input
                type="checkbox"
                checked={filters.facilities.includes(tag)}
                onChange={() => setFilters({ ...filters, facilities: toggle(filters.facilities, tag) })}
              />
              {tagLabel(tag)}
            </label>
          ))}
        </fieldset>
        <fieldset className="venue-filters__tags">
          <legend>Accessibility</legend>
          {ACCESSIBILITY_FEATURES.map((tag) => (
            <label key={tag} className="venue-check">
              <input
                type="checkbox"
                checked={filters.accessibility.includes(tag)}
                onChange={() => setFilters({ ...filters, accessibility: toggle(filters.accessibility, tag) })}
              />
              {tagLabel(tag)}
            </label>
          ))}
        </fieldset>
      </section>

      {loading && venues.length === 0 ? (
        <p className="request-empty">Loading venues…</p>
      ) : venues.length === 0 ? (
        <p className="request-empty">No venues match these filters.</p>
      ) : (
        <ul className="venue-list" aria-label="Venues">
          {venues.map((venue) => (
            <li key={venue.id} className="venue-card" aria-label={venue.name}>
              <div className="venue-card__head">
                <h2>{venue.name}</h2>
                {!venue.is_active && <span className="venue-badge">Inactive</span>}
              </div>
              <p className="venue-card__location">{venue.location}</p>
              <dl className="venue-card__facts">
                <div>
                  <dt>Capacity</dt>
                  <dd>{venue.capacity}</dd>
                </div>
                <div>
                  <dt>Hours</dt>
                  <dd>{hours(venue)}</dd>
                </div>
                <div>
                  <dt>Setup / turnaround</dt>
                  <dd>
                    {venue.setup_minutes} / {venue.turnaround_minutes} min
                  </dd>
                </div>
              </dl>
              <ul className="venue-chips" aria-label="Tags">
                {[...venue.facilities, ...venue.accessibility_features, ...venue.room_layouts].map((tag) => (
                  <li key={tag}>{tagLabel(tag)}</li>
                ))}
              </ul>
              {staff && (
                <div className="venue-card__actions">
                  <button
                    type="button"
                    className="request-button request-button--secondary"
                    onClick={() => {
                      setNotice("");
                      setEditing(venue);
                    }}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="request-button request-button--quiet"
                    onClick={() => setActive(venue, !venue.is_active)}
                  >
                    {venue.is_active ? "Deactivate" : "Reactivate"}
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
