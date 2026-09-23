import type { CampusEvent } from "./types";

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
});

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
});

export function formatEventDate(event: CampusEvent): string {
  return dateFormatter.format(new Date(event.startsAt));
}

export function formatEventTime(event: CampusEvent): string {
  return timeFormatter.format(new Date(event.startsAt));
}

export function formatEventTimeRange(event: CampusEvent): string {
  return `${timeFormatter.format(new Date(event.startsAt))} – ${timeFormatter.format(new Date(event.endsAt))}`;
}

export function isEventExpired(event: CampusEvent, now = new Date()): boolean {
  return new Date(event.endsAt).getTime() < now.getTime();
}

export function compareEventStart(a: CampusEvent, b: CampusEvent): number {
  const diff = new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime();
  return diff !== 0 ? diff : a.title.localeCompare(b.title);
}
