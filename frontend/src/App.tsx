import { useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { ApiError, DEV_USER_IDS, apiClient, getDevRole, setDevRole, type DevRole } from "./api/client";
import { LoginPage } from "./auth/LoginPage";
import { accountErrorMessage } from "./auth/messages";
import { SignUpPage } from "./auth/SignUpPage";
import { rememberRole, startingRole } from "./auth/currentRole";
import { completeProfile, profileFromMetadata, type Profile } from "./auth/signUp";
import { screensFor } from "./auth/screens";
import { DEV_AUTH, supabase } from "./auth/supabase";
import { SiteHeader, type View } from "./components/SiteHeader";
import { EquipmentQueue } from "./features/equipment/EquipmentQueue";
import { EventEquipment } from "./features/equipment/EventEquipment";
import { EventHealthCheck } from "./features/event/EventHealthCheck";
import { EventRegistrationsPage } from "./features/eventRegistrations/EventRegistrationsPage";
import { AssignmentQueuePage } from "./features/eventRequest/AssignmentQueuePage";
import { ClarificationReviewPage } from "./features/eventRequest/ClarificationReviewPage";
import { EventRequestsPage } from "./features/eventRequest/EventRequestsPage";
import { EventsBoard } from "./features/registration/EventsBoard";
import { MyEventsView } from "./features/registration/MyEventsView";
import { useEventRegistry } from "./features/registration/useEventRegistry";
import { VenuesPage } from "./features/venue/VenuesPage";

// GET /api/v1/me (SCRUM-105): who is logged in, with every role they hold (US16b, SCRUM-121). A role can
// be one this frontend has no screens for yet (the Safety officer's).
type Me = Profile;

/** The held roles that have screens, in /me's order: the ones a user can work in (US16b AC 2). */
function workableRoles(me: Me): string[] {
  return me.roles.filter((role) => screensFor(role));
}

// The last screen, so a refresh comes back to it (TC-US16A-35).
const VIEW_KEY = "connectsphere.view";
const VIEWS: View[] = ["discovery", "my-events", "event-requests", "registrations", "venues", "equipment"];

function storedView(): View {
  try {
    const stored = localStorage.getItem(VIEW_KEY) as View | null;
    return stored && VIEWS.includes(stored) ? stored : "discovery";
  } catch {
    return "discovery";
  }
}

function App() {
  // undefined while Supabase restores a saved session on load.
  const [session, setSession] = useState<Session | null | undefined>(supabase ? undefined : null);
  // GET /api/v1/me's answer for one login, and the role they're working in (US16b AC 2); ignored once a
  // different user (or nobody) is logged in.
  const [account, setAccount] = useState<{ userId: string; me?: Me; role?: string; error?: string } | null>(null);
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

  // Without a login: the login page, or the sign-up page it links to (SCRUM-106).
  const [authScreen, setAuthScreen] = useState<"login" | "sign-up">("login");

  const userId = session?.user.id;
  // The name and role saved at sign-up, for the first login after confirming (SCRUM-106).
  const signUpMetadata = session?.user.user_metadata;
  useEffect(() => {
    if (!userId) return;
    // A late answer for a previous login must not move the next user's screen.
    let current = true;
    apiClient
      .get<Me>("/api/v1/me")
      .catch((reason: unknown) => {
        // First login after confirming the email: create the profile from what sign-up saved, then
        // open the role's home screen (TC-US16A-40, 41). Anyone else without a profile keeps the message.
        if (reason instanceof ApiError && reason.code === "PROFILE_REQUIRED" && profileFromMetadata(signUpMetadata)) {
          goHome.current = true;
          return completeProfile(signUpMetadata);
        }
        throw reason;
      })
      .then((me) => {
        if (!current) return;
        const role = startingRole(userId, workableRoles(me));
        setAccount({ userId, me, role });
        const screens = role ? screensFor(role) : undefined;
        if (goHome.current && screens) {
          goHome.current = false;
          setView(screens[0]);
        }
      })
      .catch((reason: unknown) => {
        if (current) setAccount({ userId, error: accountErrorMessage(reason) });
      });
    return () => {
      current = false;
    };
    // Re-read only when a different user logs in, not on every token refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);
  const current = account && account.userId === userId ? account : null;
  const me = current?.me ?? null;
  const meError = current?.error ?? null;

  // US16b AC 2: switching role opens the new role's home screen, and is remembered for this user.
  function switchRole(role: string) {
    if (!current?.me || !userId) return;
    rememberRole(userId, role);
    setAccount({ ...current, role });
    const screens = screensFor(role);
    if (screens) setView(screens[0]);
  }

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
    if (authScreen === "sign-up") return <SignUpPage onShowLogin={() => setAuthScreen("login")} />;
    return <LoginPage onLoggedIn={() => (goHome.current = true)} onShowSignUp={() => setAuthScreen("sign-up")} />;
  }
  // A user whose roles have no screens yet (the Safety officer's, US16b) can only log out (TC-US16B-21).
  const blocked = me && !current?.role ? "Your account's role doesn't have any screens yet." : meError;
  if (session && (!me || blocked)) {
    return (
      <main className="request-page">
        {blocked ?? "Loading your account…"}
        {logOutError && (
          <div className="request-alert" role="alert">
            {logOutError}
          </div>
        )}
        {blocked && (
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
      <Workspace
        me={me}
        role={current?.role ?? null}
        onRoleChange={switchRole}
        view={view}
        onNavigate={setView}
        onLogOut={session ? logOut : undefined}
      />
    </>
  );
}

interface WorkspaceProps {
  // Null in dev mode without a login, where "Acting as" picks the user instead.
  me: Me | null;
  // The role a logged-in user is working in; null in dev mode.
  role: string | null;
  onRoleChange: (role: string) => void;
  view: View;
  onNavigate: (view: View) => void;
  onLogOut?: () => void;
}

// Mounted only once someone is identified, so its data loads with their identity.
function Workspace({ me, role: currentRole, onRoleChange, view, onNavigate, onLogOut }: WorkspaceProps) {
  // The current role's screens; dev mode without a login keeps every screen, as before. App mounts this
  // only once a logged-in user has a role with screens.
  const views = (currentRole && screensFor(currentRole)) || VIEWS;
  // A screen saved by someone else on this browser falls back to this user's home screen.
  const shown = views.includes(view) ? view : views[0];
  const registry = useEventRegistry(views.includes("discovery"));
  const [search, setSearch] = useState("");
  const [devRole, setDevRoleState] = useState<DevRole>(getDevRole);
  const role = currentRole ? (currentRole as DevRole | "attendee") : devRole;

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
        roles={me ? workableRoles(me) : undefined}
        currentRole={currentRole ?? undefined}
        onRoleChange={onRoleChange}
        onDevRoleChange={(role) => {
          setDevRole(role);
          setDevRoleState(role);
        }}
        onLogOut={onLogOut}
      />

      {shown === "venues" ? (
        <VenuesPage
          key={role}
          staff={role === "venue_staff"}
          canSearch={role === "coordinator" || role === "venue_staff"}
          calendar={role === "coordinator" || role === "coordinator_lead" || role === "venue_staff"}
        />
      ) : shown === "event-requests" ? (
        role === "coordinator" ? (
          <ClarificationReviewPage key="coordinator" userId={me?.id ?? DEV_USER_IDS.coordinator} />
        ) : role === "coordinator_lead" ? (
          <AssignmentQueuePage key="coordinator_lead" />
        ) : role === "venue_staff" || role === "tech_support" ? (
          <main className="request-page">
            <p className="request-empty">
              Event requests aren't part of the {role === "venue_staff" ? "Venue staff" : "Tech support"} role. Switch Acting as
              to see them.
            </p>
          </main>
        ) : (
          <EventRequestsPage key="organiser" />
        )
      ) : shown === "equipment" ? (
        role === "coordinator" ? (
          <EventEquipment key="coordinator" />
        ) : role === "tech_support" ? (
          <EquipmentQueue key="tech_support" />
        ) : (
          <main className="request-page">
            <p className="request-empty">Equipment requests are for Coordinators and Tech support. Switch Acting as to see them.</p>
          </main>
        )
      ) : shown === "registrations" ? (
        role === "organiser" || role === "coordinator" ? (
          <EventRegistrationsPage key={role} />
        ) : (
          <main className="request-page">
            <p className="request-empty">Registrations are for organisers and coordinators. Switch Acting as to see them.</p>
          </main>
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
