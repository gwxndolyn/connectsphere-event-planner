import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../../api/client";

// How often the Notifications link looks for new ones while the app stays open.
const REFRESH_MS = 30_000;

/**
 * US31 (SCRUM-107) AC 3: the unread count for the Notifications link, read when the app opens, when the
 * screen changes, after the user reads some, and every 30 seconds. A failed read keeps the last count: the
 * link is extra to the screen it sits on, so it never shows an error of its own.
 */
export function useUnreadCount(screen: string): { unread: number; setUnread: (count: number) => void; refresh: () => void } {
  const [unread, setUnread] = useState(0);

  const refresh = useCallback(() => {
    apiClient
      .get<{ unread_count: number }>("/api/v1/me/notifications/unread-count")
      .then((result) => setUnread(result.unread_count))
      .catch(() => {
        // Keep the last count.
      });
  }, []);

  useEffect(refresh, [refresh, screen]);
  useEffect(() => {
    const timer = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  return { unread, setUnread, refresh };
}
