import { describe, expect, it } from "vitest";
import { screensFor } from "./screens";

// Which screens each logged-in role gets, home first (SCRUM-105, AC 2; PR #62 review).
describe("screensFor", () => {
  it("TC-US16A-32, 33: gives each role its home screen first", () => {
    expect(screensFor("organiser")).toEqual(["event-requests", "venues"]);
    expect(screensFor("coordinator")?.[0]).toBe("event-requests");
    expect(screensFor("coordinator_lead")?.[0]).toBe("event-requests");
    expect(screensFor("operations_manager")).toEqual(["venues"]);
    expect(screensFor("attendee")).toEqual(["discovery", "my-events"]);
  });

  it("gives a role the frontend doesn't know yet no screens", () => {
    expect(screensFor("tech_support")).toBeUndefined();
    expect(screensFor("toString")).toBeUndefined();
  });
});
