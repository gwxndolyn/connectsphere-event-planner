import { useEffect, useState } from "react";
import { apiClient } from "../../api/client";

export function EventHealthCheck() {
  const [status, setStatus] = useState("checking...");

  useEffect(() => {
    apiClient
      .get("/api/events/health")
      .then((message) => setStatus(message))
      .catch(() => setStatus("backend unreachable"));
  }, []);

  return (
    <div>
      <strong>Backend status:</strong> {status}
    </div>
  );
}
