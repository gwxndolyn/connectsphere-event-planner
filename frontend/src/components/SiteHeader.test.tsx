import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SiteHeader } from "./SiteHeader";

function renderHeader(props: Partial<Parameters<typeof SiteHeader>[0]> = {}) {
  const handlers = { onSearchChange: vi.fn(), onNavigate: vi.fn(), onDevRoleChange: vi.fn() };
  render(<SiteHeader search="" view="discovery" devRole="organiser" {...handlers} {...props} />);
  return handlers;
}

describe("SiteHeader", () => {
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
