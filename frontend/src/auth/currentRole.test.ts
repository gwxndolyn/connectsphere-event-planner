import { describe, expect, it } from "vitest";
import { rememberRole, roleLabel, startingRole } from "./currentRole";

// US16b AC 2 (SCRUM-121): a user holding several roles works in one at a time. The choice is the
// frontend's (D46), kept per user on this browser.
describe("startingRole", () => {
  it("starts on the first held role when nothing is stored (TC-US16B-18)", () => {
    expect(startingRole("user-1", ["coordinator", "venue_staff"])).toBe("coordinator");
  });

  it("keeps the role this user chose before, across a refresh (TC-US16B-19)", () => {
    rememberRole("user-1", "venue_staff");

    expect(startingRole("user-1", ["coordinator", "venue_staff"])).toBe("venue_staff");
  });

  it("falls back to the first held role for a role the user no longer holds, or another user's choice (TC-US16B-20)", () => {
    rememberRole("user-1", "tech_support");
    expect(startingRole("user-1", ["coordinator", "venue_staff"])).toBe("coordinator");

    rememberRole("someone-else", "venue_staff");
    expect(startingRole("user-1", ["coordinator", "venue_staff"])).toBe("coordinator");
  });

  it("ignores stored text that isn't a remembered choice", () => {
    localStorage.setItem("connectsphere.role", "not json");

    expect(startingRole("user-1", ["coordinator", "venue_staff"])).toBe("coordinator");
  });
});

describe("roleLabel", () => {
  it("names every role the way the screens do", () => {
    expect(["coordinator", "coordinator_lead", "venue_staff", "tech_support", "safety_officer"].map(roleLabel)).toEqual([
      "Coordinator",
      "Coordinator Lead",
      "Venue staff",
      "Tech support",
      "Safety officer",
    ]);
  });
});
