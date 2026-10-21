import { useState } from "react";
import { getDevRole, setDevRole, type DevRole } from "./api/client";
import { SiteHeader, type View } from "./components/SiteHeader";
import { EventHealthCheck } from "./features/event/EventHealthCheck";
import { ClarificationReviewPage } from "./features/eventRequest/ClarificationReviewPage";
import { EventRequestsPage } from "./features/eventRequest/EventRequestsPage";
import { EventsBoard } from "./features/registration/EventsBoard";
import { MyEventsView } from "./features/registration/MyEventsView";
import { useEventRegistry } from "./features/registration/useEventRegistry";
import { VenuesPage } from "./features/venue/VenuesPage";

function App() {
  const registry = useEventRegistry();
  const [view, setView] = useState<View>("discovery");
  const [search, setSearch] = useState("");
  const [devRole, setDevRoleState] = useState<DevRole>(getDevRole);

  return (
    <div>
      <SiteHeader
        search={search}
        onSearchChange={(value) => {
          setSearch(value);
          setView("discovery");
        }}
        view={view}
        onNavigate={setView}
        devRole={devRole}
        onDevRoleChange={(role) => {
          setDevRole(role);
          setDevRoleState(role);
        }}
      />

      {view === "venues" ? (
        <VenuesPage key={devRole} staff={devRole === "venue_staff"} />
      ) : view === "event-requests" ? (
        devRole === "coordinator" ? (
          <ClarificationReviewPage key="coordinator" />
        ) : devRole === "venue_staff" ? (
          <main className="request-page">
            <p className="request-empty">Event requests aren't part of the Venue staff role. Switch Acting as to see them.</p>
          </main>
        ) : (
          <EventRequestsPage key="organiser" />
        )
      ) : view === "discovery" ? (
        <EventsBoard registry={registry} search={search} />
      ) : (
        <MyEventsView registry={registry} onBrowse={() => setView("discovery")} />
      )}

      <footer className="app-footer">
        <EventHealthCheck />
      </footer>
    </div>
  );
}

export default App;
