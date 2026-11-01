import { useEffect, useState } from "react";
import { ApiError, apiClient } from "../../api/client";
import { formatInstantDateTime } from "../registration/datetime";
import type { AppNotification, NotificationList, ReadAll } from "./types";
import "../eventRequest/eventRequests.css";
import "./notifications.css";

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "The request could not be completed. Check the backend connection and try again.";
  if (error.code === "UNAUTHENTICATED") return "Log in to see your notifications.";
  return `The backend rejected the request (${error.status}).`;
}

interface NotificationsPageProps {
  // Called with the new unread count after the list loads or the user reads some, so the header link follows.
  onUnreadChange: (count: number) => void;
  // AC 5: opens the event's request. Offered only on a notification the user may open; the app decides where.
  onOpen?: (notification: AppNotification) => void;
}

/**
 * US31 (SCRUM-107): the user's own notifications, newest first (AC 2), the unread ones marked (AC 3), each
 * markable as read, or all of them (AC 4), and a link to the event where the user's role allows it (AC 5).
 */
export function NotificationsPage({ onUnreadChange, onOpen }: NotificationsPageProps) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let current = true;
    apiClient
      .get<NotificationList>("/api/v1/me/notifications")
      .then((result) => {
        if (!current) return;
        setItems(result.notifications);
        setUnread(result.unread_count);
        onUnreadChange(result.unread_count);
      })
      .catch((reason: unknown) => {
        if (current) setError(errorMessage(reason));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
    // The list is read once when the screen opens; reading some updates it in place.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function markRead(notification: AppNotification) {
    if (notification.read) return;
    setError(null);
    try {
      await apiClient.post<AppNotification>(`/api/v1/me/notifications/${notification.id}/read`, {});
      setItems((current) => current.map((item) => (item.id === notification.id ? { ...item, read: true } : item)));
      setUnread((current) => {
        const next = Math.max(0, current - 1);
        onUnreadChange(next);
        return next;
      });
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function markAllRead() {
    setBusy(true);
    setError(null);
    try {
      const result = await apiClient.post<ReadAll>("/api/v1/me/notifications/read-all", {});
      setItems((current) => current.map((item) => ({ ...item, read: true })));
      setUnread(result.unread_count);
      onUnreadChange(result.unread_count);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function open(notification: AppNotification) {
    await markRead(notification);
    onOpen?.(notification);
  }

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <p className="request-page__eyebrow">ACCOUNT / NOTIFICATIONS</p>
          <h1>Notifications</h1>
        </div>
      </div>

      {error && <div className="request-alert" role="alert">{error}</div>}

      <div className="notifications-toolbar">
        <p role="status">{loading ? "Loading notifications…" : unread === 0 ? "You're all caught up." : `${unread} unread`}</p>
        <button
          className="request-button request-button--secondary"
          type="button"
          disabled={busy || unread === 0}
          onClick={() => void markAllRead()}
        >
          Mark all as read
        </button>
      </div>

      {!loading && items.length === 0 ? (
        <div className="request-empty">
          <p>You have no notifications yet.</p>
        </div>
      ) : (
        <ul className="notification-list" aria-label="Notifications">
          {items.map((item) => (
            <li className={`notification${item.read ? "" : " notification--unread"}`} key={item.id}>
              <div className="notification__head">
                <span className="notification__event">{item.event_name || "An event"}</span>
                <span className="notification__time">
                  {!item.read && <strong>Unread · </strong>}
                  {formatInstantDateTime(item.created_at)}
                </span>
              </div>
              <p className="notification__message">{item.message}</p>
              <div className="notification__actions">
                {item.can_open && onOpen && (
                  <button className="request-button request-button--primary" type="button" onClick={() => void open(item)}>
                    Open request
                  </button>
                )}
                {!item.read && (
                  <button className="request-button request-button--quiet" type="button" onClick={() => void markRead(item)}>
                    Mark as read
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
