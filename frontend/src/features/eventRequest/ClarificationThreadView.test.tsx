import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClarificationThreadView } from "./ClarificationThreadView";
import type { Clarification } from "./types";

function message(overrides: Partial<Clarification>): Clarification {
  return {
    id: `${overrides.round}-${overrides.kind}`,
    event_id: "e1",
    round: 1,
    kind: "request",
    sections: null,
    comment: "",
    author_user_id: "u1",
    created_at: "2026-10-01T02:00:00Z",
    ...overrides,
  };
}

describe("ClarificationThreadView", () => {
  it("shows each round's question with the reply beneath it, oldest round first (US8c AC 1, 3)", () => {
    render(
      <ClarificationThreadView
        messages={[
          message({ round: 2, kind: "request", sections: ["equipment"], comment: "Which projector?" }),
          message({ round: 1, kind: "request", sections: ["attendance", "layout"], comment: "Final headcount?" }),
          message({ round: 1, kind: "response", comment: "40, in rows." }),
        ]}
      />,
    );

    const rounds = screen.getAllByRole("listitem", { name: /^Round \d$/ });
    expect(rounds.map((round) => round.getAttribute("aria-label"))).toEqual(["Round 1", "Round 2"]);

    const first = within(rounds[0]);
    expect(first.getByRole("list", { name: "Round 1 sections" })).toHaveTextContent("AttendanceRoom layout");
    expect(first.getByText("Final headcount?")).toBeInTheDocument();
    expect(first.getByText("Organiser replied")).toBeInTheDocument();
    expect(first.getByText("40, in rows.")).toBeInTheDocument();
    // The question comes before the reply in the document.
    const question = first.getByText("Final headcount?");
    const reply = first.getByText("40, in rows.");
    expect(question.compareDocumentPosition(reply) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("marks an unanswered round as waiting", () => {
    render(<ClarificationThreadView messages={[message({ round: 1, comment: "Final headcount?" })]} />);
    expect(screen.getByText("Waiting for the organiser's response.")).toBeInTheDocument();
  });

  it("uses the given title as its region name", () => {
    render(<ClarificationThreadView messages={[]} title="Earlier rounds" />);
    expect(screen.getByRole("region", { name: "Earlier rounds" })).toBeInTheDocument();
  });
});
