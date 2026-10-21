import { describe, expect, it } from "vitest";
import { SECTIONS, displayValue, sectionLabel, statusLabel } from "./clarificationSections";

describe("SECTIONS", () => {
  it("lists D13's seven sections in the backend's order", () => {
    expect(SECTIONS.map((section) => section.key)).toEqual([
      "details",
      "schedule",
      "attendance",
      "layout",
      "accessibility",
      "equipment",
      "registration",
    ]);
  });
});

describe("sectionLabel", () => {
  it("returns the human label", () => {
    expect(sectionLabel("layout")).toBe("Room layout");
  });

  it("falls back to the key for an unknown section", () => {
    expect(sectionLabel("catering")).toBe("catering");
  });
});

describe("displayValue", () => {
  it.each([
    [null, "Not provided"],
    ["", "Not provided"],
    [[], "Not provided"],
  ])("shows %j as Not provided", (value, expected) => {
    expect(displayValue(value)).toBe(expected);
  });

  it("joins dates", () => {
    expect(displayValue(["2026-11-01", "2026-11-02"])).toBe("2026-11-01, 2026-11-02");
  });

  it("tells required apart from not required", () => {
    expect(displayValue(true)).toBe("Required");
    expect(displayValue(false)).toBe("Not required");
  });

  it("trims the API's HH:MM:SS times to HH:MM", () => {
    expect(displayValue("14:00:00")).toBe("14:00");
  });

  it("shows other values as text", () => {
    expect(displayValue(40)).toBe("40");
    expect(displayValue("Workshop")).toBe("Workshop");
  });
});

describe("statusLabel", () => {
  it("replaces every underscore", () => {
    expect(statusLabel("awaiting_clarification")).toBe("awaiting clarification");
    expect(statusLabel("draft")).toBe("draft");
  });
});
