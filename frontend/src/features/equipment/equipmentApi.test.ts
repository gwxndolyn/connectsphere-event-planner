import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { equipmentErrorMessage, equipmentFieldErrors, lineStatusLabel, toLineBody } from "./equipmentApi";

// US26 screens (SCRUM-110): what a line form sends, and how SCRUM-109's refusals read.
describe("toLineBody", () => {
  it("sends the type, a whole-number quantity and trimmed notes", () => {
    expect(toLineBody({ typeId: "type-1", quantity: " 2 ", notes: "  Front of the room  " })).toEqual({
      equipment_type_id: "type-1",
      quantity: 2,
      notes: "Front of the room",
    });
  });

  it("sends 0 and negatives as numbers, so the API names the quantity (TC-US26-16)", () => {
    expect(toLineBody({ typeId: "type-1", quantity: "0", notes: "" }).quantity).toBe(0);
    expect(toLineBody({ typeId: "type-1", quantity: "-1", notes: "" }).quantity).toBe(-1);
  });

  it("sends anything else as typed, and leaves out blanks, so the API names the field", () => {
    expect(toLineBody({ typeId: "type-1", quantity: "1.5", notes: "" }).quantity).toBe("1.5");
    expect(toLineBody({ typeId: "", quantity: "", notes: "  " })).toEqual({ notes: null });
  });
});

describe("equipmentErrorMessage", () => {
  it("explains each SCRUM-109 refusal", () => {
    expect(equipmentErrorMessage(new ApiError(422, "INVALID_EQUIPMENT_LINE", ["quantity"]))).toBe(
      "Review the fields marked below and try again.",
    );
    expect(
      equipmentErrorMessage(new ApiError(409, "LINE_NOT_PENDING", [], { code: "LINE_NOT_PENDING", status: "approved" })),
    ).toBe("This line has already been reviewed (it's approved now), so it can't be changed.");
    expect(
      equipmentErrorMessage(new ApiError(409, "EVENT_NOT_ELIGIBLE", [], { code: "EVENT_NOT_ELIGIBLE", status: "completed" })),
    ).toBe("Equipment can only be requested for events in planning or confirmed; this one is completed.");
    expect(equipmentErrorMessage(new ApiError(403, "FORBIDDEN"))).toBe(
      "Equipment requests are for Coordinators and Tech support. Switch Acting as to one of them.",
    );
    expect(equipmentErrorMessage(new Error("network"))).toBe(
      "The request could not be completed. Check the backend connection and try again.",
    );
  });

  it("uses the API's own message for a duplicate type (D41)", () => {
    const message = "This event already has a pending or approved line for that equipment type. Change its quantity instead.";
    expect(
      equipmentErrorMessage(
        new ApiError(409, "DUPLICATE_EQUIPMENT_TYPE", ["equipment_type_id"], { code: "DUPLICATE_EQUIPMENT_TYPE", message }),
      ),
    ).toBe(message);
  });
});

describe("equipmentFieldErrors", () => {
  it("puts INVALID_EQUIPMENT_LINE's messages on their fields", () => {
    const error = new ApiError(422, "INVALID_EQUIPMENT_LINE", ["quantity"], {
      code: "INVALID_EQUIPMENT_LINE",
      fields: ["quantity"],
      errors: { quantity: "Quantity must be a whole number of at least 1." },
    });
    expect(equipmentFieldErrors(error)).toEqual({ quantity: "Quantity must be a whole number of at least 1." });
  });

  it("puts a duplicate type on the type field", () => {
    const error = new ApiError(409, "DUPLICATE_EQUIPMENT_TYPE", ["equipment_type_id"], {
      code: "DUPLICATE_EQUIPMENT_TYPE",
      message: "Already requested.",
    });
    expect(equipmentFieldErrors(error)).toEqual({ equipment_type_id: "Already requested." });
  });

  it("has nothing for other refusals", () => {
    expect(equipmentFieldErrors(new ApiError(404, "NOT_FOUND"))).toEqual({});
  });
});

describe("lineStatusLabel", () => {
  it("names each status", () => {
    expect(["pending", "approved", "rejected"].map((status) => lineStatusLabel(status as "pending"))).toEqual([
      "Pending",
      "Approved",
      "Rejected",
    ]);
  });
});
