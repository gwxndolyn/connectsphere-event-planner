import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { decisionErrorMessage, impactParts } from "./changeRequestApi";

// US29b (SCRUM-143), Calvin's #127 review: the wording of what approving does, and of a refused decision.
describe("changeRequestApi wording (US29b)", () => {
  it("TC-US29B-27: names the event's registrations, with their count, as one flag", () => {
    const impact = { status_after: "planning", venue_bookings: 1, equipment_reservations: 0, registrations: 45, safety_review_required: false };
    expect(impactParts(impact, "confirmed")).toEqual([
      "moves this event back to Planning",
      "flags 1 venue booking and the event's registrations (45) for review",
    ]);
    expect(impactParts({ ...impact, venue_bookings: 0 }, "planning")).toEqual(["flags the event's registrations (45) for review"]);
  });

  it("TC-US29B-30: says a role can't take the action when the API answers FORBIDDEN", () => {
    expect(decisionErrorMessage(new ApiError(403, "FORBIDDEN"))).toBe("This isn't an action your role can take.");
  });
});
