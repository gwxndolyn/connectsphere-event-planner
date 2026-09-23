import { EventHealthCheck } from "./features/event/EventHealthCheck";
import { EventsBoard } from "./features/registration/EventsBoard";

function App() {
  return (
    <div>
      <EventsBoard />
      <footer className="app-footer">
        <EventHealthCheck />
      </footer>
    </div>
  );
}

export default App;
