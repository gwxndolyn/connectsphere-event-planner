import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SiteHeader, type View } from "./SiteHeader";

function renderHeader(props: Partial<Parameters<typeof SiteHeader>[0]> = {}) {
  const handlers = { onSearchChange: vi.fn(), onNavigate: vi.fn(), onDevRoleChange: vi.fn() };
  const views: View[] = ["discovery", "my-events", "event-requests", "venues"];
  render(<SiteHeader search="" view="discovery" devRole="organiser" views={views} {...handlers} {...props} />);
  return handlers;
}

describe("SiteHeader", () => {
  it("shows a logged-in user only their own screens (TC-US16A-32, 33)", async () => {
    const { onNavigate } = renderHeader({ view: "event-requests", views: ["event-requests", "venues"] });
    expect(screen.queryByRole("button", { name: "My events" })).not.toBeInTheDocument();
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Venues" })).toBeInTheDocument();
    // The logo opens the user's home screen.
    await userEvent.click(screen.getByRole("button", { name: "ConnectSphere" }));
    expect(onNavigate).toHaveBeenCalledWith("event-requests");
  });

  it("shows an attendee no staff screens", () => {
    renderHeader({ views: ["discovery", "my-events"] });
    expect(screen.getByRole("button", { name: "My events" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Event requests" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Venues" })).not.toBeInTheDocument();
  });

  it("reports each search keystroke", async () => {
    const { onSearchChange } = renderHeader();
    await userEvent.type(screen.getByRole("searchbox", { name: "Search campus events" }), "y");
    expect(onSearchChange).toHaveBeenCalledWith("y");
  });

  it("toggles between My events and Browse events", async () => {
    const { onNavigate } = renderHeader();
    await userEvent.click(screen.getByRole("button", { name: "My events" }));
    expect(onNavigate).toHaveBeenCalledWith("my-events");
  });

  it("offers Browse events while on My events", async () => {
    const { onNavigate } = renderHeader({ view: "my-events" });
    await userEvent.click(screen.getByRole("button", { name: "Browse events" }));
    expect(onNavigate).toHaveBeenCalledWith("discovery");
  });

  it("marks Event requests as the current page when it is", () => {
    renderHeader({ view: "event-requests" });
    expect(screen.getByRole("button", { name: "Event requests" })).toHaveAttribute("aria-current", "page");
  });

  it("goes home from the logo", async () => {
    const { onNavigate } = renderHeader({ view: "my-events" });
    await userEvent.click(screen.getByRole("button", { name: "ConnectSphere" }));
    expect(onNavigate).toHaveBeenCalledWith("discovery");
  });

  it("switches Acting as (D12)", async () => {
    const { onDevRoleChange } = renderHeader();
    await userEvent.selectOptions(screen.getByLabelText("Acting as"), "coordinator");
    expect(onDevRoleChange).toHaveBeenCalledWith("coordinator");
  });
});
