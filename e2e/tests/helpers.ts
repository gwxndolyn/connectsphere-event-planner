import type { Page } from "@playwright/test";

// The review queue's heading, matched exactly: without exact, "Requests to review" also matches the
// "Change requests to review (N)" heading once a parallel test leaves a change request (SCRUM-145).
export function reviewQueueHeading(page: Page) {
  return page.getByRole("heading", { name: "Requests to review", exact: true });
}
