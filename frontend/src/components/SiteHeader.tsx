import type { DevRole } from "../api/client";
import "./SiteHeader.css";

export type View = "discovery" | "my-events" | "event-requests" | "venues" | "equipment";

interface SiteHeaderProps {
  search: string;
  onSearchChange: (value: string) => void;
  view: View;
  onNavigate: (view: View) => void;
  // Shown only in dev mode without a login (VITE_DEV_AUTH, TC-US16A-38).
  devRole?: DevRole;
  onDevRoleChange: (role: DevRole) => void;
  // Shown while logged in (AC 5).
  onLogOut?: () => void;
  // The screens this user may open, home first; every screen in dev mode without a login.
  views: View[];
}

export function SiteHeader({
  search,
  onSearchChange,
  view,
  onNavigate,
  devRole,
  onDevRoleChange,
  onLogOut,
  views,
}: SiteHeaderProps) {
  const attendeeScreens = views.includes("discovery");
  return (
    <header className="site-header">
      <div className="site-header__bar">
        <button
          type="button"
          className="site-header__logo"
          onClick={() => onNavigate(views[0])}
        >
          <span className="site-header__logo-mark" aria-hidden="true" />
          ConnectSphere
        </button>

        {attendeeScreens && (
          <div className="site-header__search">
            <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
              <path
                fill="currentColor"
                d="M13.6 12.2a6 6 0 1 0-1.4 1.4l4 4 1.4-1.4zM3 8a5 5 0 1 1 10 0A5 5 0 0 1 3 8"
              />
            </svg>
            <input
              type="search"
              placeholder="Search campus events"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              aria-label="Search campus events"
            />
          </div>
        )}

        <div className="site-header__location">
          <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
            <path
              fill="currentColor"
              d="M10 1a6 6 0 0 0-6 6c0 4.5 6 12 6 12s6-7.5 6-12a6 6 0 0 0-6-6m0 8.5A2.5 2.5 0 1 1 10 4a2.5 2.5 0 0 1 0 5.5"
            />
          </svg>
          Main Campus
        </div>

        {attendeeScreens && (
          <button
            type="button"
            className="site-header__nav-link"
            onClick={() => onNavigate(view === "my-events" ? "discovery" : "my-events")}
          >
            {view === "my-events" ? "Browse events" : "My events"}
          </button>
        )}
        {views.includes("event-requests") && (
          <button
            type="button"
            className="site-header__nav-link"
            aria-current={view === "event-requests" ? "page" : undefined}
            onClick={() => onNavigate("event-requests")}
          >
            Event requests
          </button>
        )}
        {views.includes("venues") && (
          <button
            type="button"
            className="site-header__nav-link"
            aria-current={view === "venues" ? "page" : undefined}
            onClick={() => onNavigate("venues")}
          >
            Venues
          </button>
        )}
        {views.includes("equipment") && (
          <button
            type="button"
            className="site-header__nav-link"
            aria-current={view === "equipment" ? "page" : undefined}
            onClick={() => onNavigate("equipment")}
          >
            Equipment
          </button>
        )}
        {/* Dev-only stand-in for login (D12): picks which seeded user's X-User-Id is sent. */}
        {devRole && (
          <label className="site-header__role">
            Acting as
            <select value={devRole} onChange={(event) => onDevRoleChange(event.target.value as DevRole)}>
              <option value="organiser">Organiser</option>
              <option value="coordinator">Coordinator</option>
              <option value="coordinator_lead">Coordinator Lead</option>
              <option value="venue_staff">Venue staff</option>
              <option value="tech_support">Tech support</option>
            </select>
          </label>
        )}
        {onLogOut && (
          <button type="button" className="site-header__nav-link" onClick={onLogOut}>
            Log out
          </button>
        )}
      </div>
    </header>
  );
}
