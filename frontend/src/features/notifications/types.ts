// US31 (SCRUM-107): what GET /api/v1/me/notifications returns.
export interface AppNotification {
  id: string;
  kind: string;
  event_id: string | null;
  event_name: string | null;
  message: string;
  created_at: string;
  read: boolean;
  // Whether the recipient may open the event's request; the notice names the event either way.
  can_open: boolean;
}

export interface NotificationList {
  // Newest first.
  notifications: AppNotification[];
  // Every unread one, not only the ones listed.
  unread_count: number;
}

export interface ReadAll {
  updated: number;
  unread_count: number;
}
