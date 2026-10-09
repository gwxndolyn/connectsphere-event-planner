import { useState } from "react";
import { getDevRole, setDevRole, type DevRole } from "./api/client";
import { SiteHeader } from "./components/SiteHeader";
import { EventHealthCheck } from "./features/event/EventHealthCheck";
import { ClarificationReviewPage } from "./features/eventRequest/ClarificationReviewPage";
import { EventRequestsPage } from "./features/eventRequest/EventRequestsPage";
import { EventsBoard } from "./features/registration/EventsBoard";
import { mockEvents } from "./features/registration/mockEvents";
import { MyEventsView } from "./features/registration/MyEventsView";
import { useEventRegistry } from "./features/registration/useEventRegistry";

type View = "discovery" | "my-events" | "event-requests";

function App() {
  const registry = useEventRegistry(mockEvents);
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

      {view === "event-requests" ? (
        devRole === "coordinator" ? <ClarificationReviewPage key="coordinator" /> : <EventRequestsPage key="organiser" />
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
