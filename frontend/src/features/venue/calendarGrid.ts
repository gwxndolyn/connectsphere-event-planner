import type { CalendarItem, CalendarVenue } from "./types";

// US21 (SCRUM-88, PR 2 SCRUM-123): the venue calendar's date maths. Days are Singapore days as
// "YYYY-MM-DD" (D9, D61). Singapore is +08:00 all year, so day arithmetic in UTC is exact.

export type CalendarView = "week" | "month";

/** The days drawn, both included: what the API is asked for (`from`, `to`). */
export interface DayRange {
  from: string;
  to: string;
}

/** The hours a week view draws, as whole hours from midnight (0 to 24). */
export interface HourSpan {
  start: number;
  end: number;
}

/** An item's occupied window on one day, in minutes from that day's midnight. */
export interface Segment {
  item: CalendarItem;
  startMinute: number;
  endMinute: number;
  // The part of the booking's setup and turnaround on this day (US13 AC 2); 0 for a block.
  setupMinutes: number;
  turnaroundMinutes: number;
  // Side by side when items overlap on the day.
  lane: number;
  lanes: number;
}

/** Minutes the venue is closed within the hours drawn, shaded "Closed". */
export interface Band {
  startMinute: number;
  endMinute: number;
}

const MINUTE = 60_000;
const DAY_MINUTES = 24 * 60;
const SINGAPORE_OFFSET_MINUTES = 8 * 60;

const monthTitle = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
const dayTitle = new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });

function utcDate(day: string): Date {
  return new Date(`${day}T00:00:00Z`);
}

function toDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** Today in Singapore. */
export function singaporeToday(now: number = Date.now()): string {
  return toDay(new Date(now + SINGAPORE_OFFSET_MINUTES * MINUTE));
}

export function addDays(day: string, days: number): string {
  const date = utcDate(day);
  date.setUTCDate(date.getUTCDate() + days);
  return toDay(date);
}

/** A day as the screens name it, e.g. "Mon, Oct 12". */
export function dayLabel(day: string): string {
  return dayTitle.format(utcDate(day));
}

function monday(day: string): string {
  // getUTCDay: Sunday 0. Weeks start on Monday.
  return addDays(day, -((utcDate(day).getUTCDay() + 6) % 7));
}

function daysFrom(first: string, count: number): string[] {
  return Array.from({ length: count }, (_, i) => addDays(first, i));
}

/** Monday to Sunday of the week holding `day`. */
export function weekDays(day: string): string[] {
  return daysFrom(monday(day), 7);
}

/** The full Monday-to-Sunday weeks covering `day`'s month: 28 to 42 days, within the API's limit. */
export function monthDays(day: string): string[] {
  const first = `${day.slice(0, 7)}-01`;
  const next = utcDate(first);
  next.setUTCMonth(next.getUTCMonth() + 1);
  const last = addDays(toDay(next), -1);
  const start = monday(first);
  const end = addDays(monday(last), 6);
  return daysFrom(start, (utcDate(end).getTime() - utcDate(start).getTime()) / (DAY_MINUTES * MINUTE) + 1);
}

function daysOf(view: CalendarView, anchor: string): string[] {
  return view === "week" ? weekDays(anchor) : monthDays(anchor);
}

export function rangeFor(view: CalendarView, anchor: string): DayRange {
  const days = daysOf(view, anchor);
  return { from: days[0], to: days[days.length - 1] };
}

/** Previous or next: a week either way, or the first of the month before or after. */
export function step(view: CalendarView, anchor: string, by: 1 | -1): string {
  if (view === "week") return addDays(anchor, 7 * by);
  const date = utcDate(`${anchor.slice(0, 7)}-01`);
  date.setUTCMonth(date.getUTCMonth() + by);
  return toDay(date);
}

/** "Mon, Oct 12 – Sun, Oct 18", or "October 2026". */
export function rangeTitle(view: CalendarView, anchor: string): string {
  if (view === "month") return monthTitle.format(utcDate(anchor));
  const days = weekDays(anchor);
  return `${dayLabel(days[0])} – ${dayLabel(days[6])}`;
}

/** Minutes from `day`'s Singapore midnight to an instant (negative before it). */
function minutesInto(day: string, iso: string): number {
  return (Date.parse(iso) - Date.parse(`${day}T00:00:00+08:00`)) / MINUTE;
}

/** An instant `minute` minutes after `day`'s Singapore midnight, for showing a clipped time. */
export function instantAt(day: string, minute: number): string {
  return new Date(Date.parse(`${day}T00:00:00+08:00`) + minute * MINUTE).toISOString();
}

function clip(minute: number): number {
  return Math.min(Math.max(minute, 0), DAY_MINUTES);
}

/**
 * The items occupying part of `day`, each clipped to the day, so one past midnight shows on both
 * days. Items overlapping on the day get lanes, earliest first.
 */
export function daySegments(items: CalendarItem[], day: string): Segment[] {
  const segments: Segment[] = [];
  for (const item of items) {
    const occupiedStart = minutesInto(day, item.occupied.starts_at);
    const occupiedEnd = minutesInto(day, item.occupied.ends_at);
    if (occupiedEnd <= 0 || occupiedStart >= DAY_MINUTES) continue;
    const ownStart = minutesInto(day, item.starts_at);
    const ownEnd = minutesInto(day, item.ends_at);
    segments.push({
      item,
      startMinute: clip(occupiedStart),
      endMinute: clip(occupiedEnd),
      setupMinutes: Math.max(0, clip(ownStart) - clip(occupiedStart)),
      turnaroundMinutes: Math.max(0, clip(occupiedEnd) - clip(ownEnd)),
      lane: 0,
      lanes: 1,
    });
  }
  segments.sort((a, b) => a.startMinute - b.startMinute);
  const laneEnds: number[] = [];
  for (const segment of segments) {
    const free = laneEnds.findIndex((end) => end <= segment.startMinute);
    segment.lane = free === -1 ? laneEnds.length : free;
    laneEnds[segment.lane] = segment.endMinute;
  }
  for (const segment of segments) segment.lanes = laneEnds.length;
  return segments;
}

function timeMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

/** The venue's hours in minutes; a close at or before the opening means midnight. */
function openMinutes(venue: CalendarVenue): Band {
  const opens = timeMinutes(venue.opens_at);
  const closes = timeMinutes(venue.closes_at);
  return { startMinute: opens, endMinute: closes > opens ? closes : DAY_MINUTES };
}

/** An hour either side of the opening hours, widened to fit every segment, so nothing is cut off. */
export function hourSpan(venue: CalendarVenue, segments: Segment[]): HourSpan {
  const open = openMinutes(venue);
  const first = Math.min(open.startMinute - 60, ...segments.map((s) => s.startMinute));
  const last = Math.max(open.endMinute + 60, ...segments.map((s) => s.endMinute));
  return { start: Math.max(0, Math.floor(first / 60)), end: Math.min(24, Math.ceil(last / 60)) };
}

/** Before opening and after closing, within the hours drawn (D61: hours are shaded, not items). */
export function closedBands(venue: CalendarVenue, span: HourSpan): Band[] {
  const open = openMinutes(venue);
  const bands = [
    { startMinute: span.start * 60, endMinute: open.startMinute },
    { startMinute: open.endMinute, endMinute: span.end * 60 },
  ];
  return bands.filter((band) => band.endMinute > band.startMinute);
}

/** Top and height as percentages of the hours drawn. */
export function place(startMinute: number, endMinute: number, span: HourSpan): { top: number; height: number } {
  const total = (span.end - span.start) * 60;
  return {
    top: ((startMinute - span.start * 60) / total) * 100,
    height: ((endMinute - startMinute) / total) * 100,
  };
}
