import { useState } from "react";
import { SiteHeader } from "./components/SiteHeader";
import { EventHealthCheck } from "./features/event/EventHealthCheck";
import { EventsBoard } from "./features/registration/EventsBoard";
import { mockEvents } from "./features/registration/mockEvents";
import { MyEventsView } from "./features/registration/MyEventsView";
import { useEventRegistry } from "./features/registration/useEventRegistry";

type View = "discovery" | "my-events";

function App() {
  const registry = useEventRegistry(mockEvents);
  const [view, setView] = useState<View>("discovery");
  const [search, setSearch] = useState("");

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
      />

      {view === "discovery" ? (
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
