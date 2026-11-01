import { describe, expect, it } from "vitest";
import { screensFor } from "./screens";

// Which screens each logged-in role gets, home first (SCRUM-105, AC 2; PR #62 review).
describe("screensFor", () => {
  it("TC-US16A-32, 33: gives each role its home screen first", () => {
    expect(screensFor("organiser")).toEqual(["event-requests", "registrations", "venues"]);
    expect(screensFor("coordinator")?.[0]).toBe("event-requests");
    expect(screensFor("coordinator_lead")?.[0]).toBe("event-requests");
    expect(screensFor("venue_staff")).toEqual(["venues"]);
    expect(screensFor("attendee")).toEqual(["discovery", "my-events"]);
  });

  it("TC-US26-16, 17: gives the coordinator Equipment, and Tech support Equipment as home (SCRUM-110)", () => {
    expect(screensFor("coordinator")).toEqual(["event-requests", "events", "registrations", "venues", "equipment"]);
    expect(screensFor("tech_support")).toEqual(["equipment"]);
    expect(screensFor("organiser")).not.toContain("equipment");
    expect(screensFor("venue_staff")).not.toContain("equipment");
  });

  it("TC-US28-18: gives the organiser and coordinator Registrations, and no other role (SCRUM-96)", () => {
    for (const role of ["organiser", "coordinator"]) expect(screensFor(role)).toContain("registrations");
    for (const role of ["coordinator_lead", "venue_staff", "tech_support", "attendee"]) {
      expect(screensFor(role)).not.toContain("registrations");
    }
  });

  it("gives a role the frontend doesn't know yet no screens", () => {
    expect(screensFor("auditor")).toBeUndefined();
    expect(screensFor("toString")).toBeUndefined();
  });

  it("TC-US30A-40: gives the Safety officer Safety reviews as their only screen (SCRUM-99)", () => {
    expect(screensFor("safety_officer")).toEqual(["safety-reviews"]);
    for (const role of ["organiser", "coordinator", "coordinator_lead", "venue_staff", "tech_support", "attendee"]) {
      expect(screensFor(role)).not.toContain("safety-reviews");
    }
  });
});
