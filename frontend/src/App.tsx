import { useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { apiClient, getDevRole, setDevRole, type DevRole } from "./api/client";
import { LoginPage } from "./auth/LoginPage";
import { accountErrorMessage } from "./auth/messages";
import { DEV_AUTH, supabase } from "./auth/supabase";
import { SiteHeader, type View } from "./components/SiteHeader";
import { EventHealthCheck } from "./features/event/EventHealthCheck";
import { AssignmentQueuePage } from "./features/eventRequest/AssignmentQueuePage";
import { ClarificationReviewPage } from "./features/eventRequest/ClarificationReviewPage";
import { EventRequestsPage } from "./features/eventRequest/EventRequestsPage";
import { EventsBoard } from "./features/registration/EventsBoard";
import { MyEventsView } from "./features/registration/MyEventsView";
import { useEventRegistry } from "./features/registration/useEventRegistry";
import { VenuesPage } from "./features/venue/VenuesPage";

// GET /api/v1/me (SCRUM-105): who is logged in.
interface Me {
  id: string;
  email: string;
  full_name: string | null;
  role: "organiser" | "coordinator" | "coordinator_lead" | "operations_manager" | "attendee";
}

// Which screens a logged-in user gets; `operations_manager` stands in for Venue staff (D19).
const SCREEN_ROLE: Record<Me["role"], DevRole | "attendee"> = {
  organiser: "organiser",
  coordinator: "coordinator",
  coordinator_lead: "coordinator_lead",
  operations_manager: "venue_staff",
  attendee: "attendee",
};

// The last screen, so a refresh comes back to it (TC-US16A-35).
const VIEW_KEY = "connectsphere.view";
const VIEWS: View[] = ["discovery", "my-events", "event-requests", "venues"];

function storedView(): View {
  try {
    const stored = localStorage.getItem(VIEW_KEY) as View | null;
    return stored && VIEWS.includes(stored) ? stored : "discovery";
  } catch {
    return "discovery";
  }
}

// The screens each logged-in role may open, its home screen first (AC 2). Staff get no attendee
// screens, so the attendee routes are never called with a staff token (PR #62 review).
const SCREENS: Record<Me["role"], View[]> = {
  organiser: ["event-requests", "venues"],
  coordinator: ["event-requests", "venues"],
  coordinator_lead: ["event-requests", "venues"],
  operations_manager: ["venues"],
  attendee: ["discovery", "my-events"],
};

function homeFor(role: Me["role"]): View {
  return SCREENS[role][0];
}

function App() {
  // undefined while Supabase restores a saved session on load.
  const [session, setSession] = useState<Session | null | undefined>(supabase ? undefined : null);
  // GET /api/v1/me's answer for one login; ignored once a different user (or nobody) is logged in.
  const [account, setAccount] = useState<{ userId: string; me?: Me; error?: string } | null>(null);
  // Set by the login page, so only a fresh login (not a refresh) opens the role's home screen.
  const goHome = useRef(false);
  const [view, setViewState] = useState<View>(storedView);

  function setView(next: View) {
    setViewState(next);
    try {
      localStorage.setItem(VIEW_KEY, next);
    } catch {
      // Storage can be unavailable (private windows); the screen then resets on refresh.
    }
  }

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);

  const userId = session?.user.id;
  useEffect(() => {
    if (!userId) return;
    // A late answer for a previous login must not move the next user's screen.
    let current = true;
    apiClient
      .get<Me>("/api/v1/me")
      .then((me) => {
        if (!current) return;
        setAccount({ userId, me });
        if (goHome.current) {
          goHome.current = false;
          setView(homeFor(me.role));
        }
      })
      .catch((reason: unknown) => {
        if (current) setAccount({ userId, error: accountErrorMessage(reason) });
      });
    return () => {
      current = false;
    };
  }, [userId]);
  const current = account && account.userId === userId ? account : null;
  const me = current?.me ?? null;
  const meError = current?.error ?? null;

  const [logOutError, setLogOutError] = useState<string | null>(null);

  // Logs out of this browser only; other devices stay logged in (PR #62 review).
  async function logOut() {
    if (!supabase) return;
    setLogOutError(null);
    const { error } = await supabase.auth.signOut({ scope: "local" });
    if (error) setLogOutError("Couldn't log out. Try again.");
  }

  if (session === undefined) {
    return <main className="request-page">Loading…</main>;
  }
  if (!session && !DEV_AUTH) {
    return <LoginPage onLoggedIn={() => (goHome.current = true)} />;
  }
  if (session && !me) {
    return (
      <main className="request-page">
        {meError ?? "Loading your account…"}
        {meError && (
          <p>
            <button type="button" className="request-button request-button--secondary" onClick={logOut}>
              Log out
            </button>
          </p>
        )}
      </main>
    );
  }
  return (
    <>
      {logOutError && (
        <div className="request-alert" role="alert">
          {logOutError}
        </div>
      )}
      <Workspace me={me} view={view} onNavigate={setView} onLogOut={session ? logOut : undefined} />
    </>
  );
}

interface WorkspaceProps {
  // Null in dev mode without a login, where "Acting as" picks the user instead.
  me: Me | null;
  view: View;
  onNavigate: (view: View) => void;
  onLogOut?: () => void;
}

// Mounted only once someone is identified, so its data loads with their identity.
function Workspace({ me, view, onNavigate, onLogOut }: WorkspaceProps) {
  // Dev mode without a login keeps every screen, as before.
  const views = me ? SCREENS[me.role] : VIEWS;
  // A screen saved by someone else on this browser falls back to this user's home screen.
  const shown = views.includes(view) ? view : views[0];
  const registry = useEventRegistry(views.includes("discovery"));
  const [search, setSearch] = useState("");
  const [devRole, setDevRoleState] = useState<DevRole>(getDevRole);
  const role = me ? SCREEN_ROLE[me.role] : devRole;

  return (
    <div>
      <SiteHeader
        search={search}
        onSearchChange={(value) => {
          setSearch(value);
          onNavigate("discovery");
        }}
        view={shown}
        onNavigate={onNavigate}
        views={views}
        devRole={me ? undefined : devRole}
        onDevRoleChange={(role) => {
          setDevRole(role);
          setDevRoleState(role);
        }}
        onLogOut={onLogOut}
      />

      {shown === "venues" ? (
        <VenuesPage key={role} staff={role === "venue_staff"} canSearch={role === "coordinator" || role === "venue_staff"} />
      ) : shown === "event-requests" ? (
        role === "coordinator" ? (
          <ClarificationReviewPage key="coordinator" />
        ) : role === "coordinator_lead" ? (
          <AssignmentQueuePage key="coordinator_lead" />
        ) : role === "venue_staff" ? (
          <main className="request-page">
            <p className="request-empty">Event requests aren't part of the Venue staff role. Switch Acting as to see them.</p>
          </main>
        ) : (
          <EventRequestsPage key="organiser" />
        )
      ) : shown === "discovery" ? (
        <EventsBoard registry={registry} search={search} />
      ) : (
        <MyEventsView registry={registry} onBrowse={() => onNavigate("discovery")} />
      )}

      <footer className="app-footer">
        <EventHealthCheck />
      </footer>
    </div>
  );
}

export default App;
