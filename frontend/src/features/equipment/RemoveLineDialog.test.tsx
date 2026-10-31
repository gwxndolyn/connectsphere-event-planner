import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RemoveLineDialog } from "./RemoveLineDialog";
import type { EquipmentLine } from "./types";

const LINE: EquipmentLine = {
  id: "line-1",
  event: { id: "event-1", name: "Equipment Request Demo", start_at: "2026-11-07T02:00:00Z" },
  equipment_type: { id: "type-1", name: "HDMI cable" },
  quantity: 1,
  notes: null,
  status: "pending",
  review_note: null,
  requested_by_user_id: "coordinator-id",
  reviewed_by_user_id: null,
  reviewed_at: null,
  availability_check: null,
  created_at: "2026-10-01T02:00:00Z",
  updated_at: "2026-10-01T02:00:00Z",
};

// US26 AC 2 (SCRUM-110): removing asks first (PR #69's pattern).
describe("RemoveLineDialog", () => {
  it("says what removing does", () => {
    render(<RemoveLineDialog line={LINE} onConfirm={vi.fn()} onClose={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Remove this equipment line?" })).toHaveTextContent(
      "The line is deleted and Tech support stops seeing it.",
    );
  });

  it("can't be closed while the removal is in flight (PR #78 review)", async () => {
    const onClose = vi.fn();
    // Never settles, so the dialog stays mid-removal.
    const onConfirm = vi.fn(() => new Promise<void>(() => {}));
    const { container } = render(<RemoveLineDialog line={LINE} onConfirm={onConfirm} onClose={onClose} />);

    await userEvent.click(screen.getByRole("button", { name: "Remove line" }));
    expect(screen.getByRole("button", { name: "Removing…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();
    await userEvent.click(container.querySelector(".dialog-overlay")!);

    expect(onClose).not.toHaveBeenCalled();
  });
});
