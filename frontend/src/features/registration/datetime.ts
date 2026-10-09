// Every event is in Singapore (TC-X-01), so times show in Asia/Singapore whatever the browser's
// zone, and the board agrees with My Events, whose date/time strings the API already gives in SGT.
const EVENT_TIME_ZONE = "Asia/Singapore";

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
  timeZone: EVENT_TIME_ZONE,
});

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
  timeZone: EVENT_TIME_ZONE,
});

interface Timed {
  startsAt: string;
  endsAt: string;
}

export function formatEventDate(event: Timed): string {
  return dateFormatter.format(new Date(event.startsAt));
}

export function formatEventTime(event: Timed): string {
  return timeFormatter.format(new Date(event.startsAt));
}

export function formatEventTimeRange(event: Timed): string {
  return `${timeFormatter.format(new Date(event.startsAt))} – ${timeFormatter.format(new Date(event.endsAt))}`;
}

export function formatInstantTime(iso: string): string {
  return timeFormatter.format(new Date(iso));
}

/** My Events rows: `date` (YYYY-MM-DD) and `HH:MM` times, already Singapore wall-clock values. */
export function toTimed(date: string, startTime: string, endTime: string): Timed {
  return { startsAt: `${date}T${startTime}:00+08:00`, endsAt: `${date}T${endTime}:00+08:00` };
}
