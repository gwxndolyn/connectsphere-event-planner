import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SignUpPage } from "./SignUpPage";

// SCRUM-106: the sign-up page against a stand-in Supabase client, so no network is used.
const { signUp } = vi.hoisted(() => ({ signUp: vi.fn() }));
vi.mock("./supabase", () => ({
  supabase: { auth: { signUp } },
  DEV_AUTH: true,
  accessToken: async () => null,
}));

async function fillAndSubmit(fields: { name?: string; email?: string; password?: string; role?: "Organiser" | "Attendee" }) {
  const user = userEvent.setup();
  if (fields.name) await user.type(screen.getByLabelText("Name"), fields.name);
  if (fields.email) await user.type(screen.getByLabelText("Email"), fields.email);
  if (fields.password) await user.type(screen.getByLabelText("Password"), fields.password);
  if (fields.role) await user.click(screen.getByRole("radio", { name: fields.role }));
  await user.click(screen.getByRole("button", { name: "Create account" }));
}

describe("SignUpPage", () => {
  beforeEach(() => signUp.mockReset());

  it("TC-US16A-42: offers only Organiser and Attendee", () => {
    render(<SignUpPage onShowLogin={vi.fn()} />);

    expect(screen.getAllByRole("radio").map((radio) => radio.getAttribute("value"))).toEqual(["organiser", "attendee"]);
  });

  it("TC-US16A-44: shows each field's error and sends nothing", async () => {
    render(<SignUpPage onShowLogin={vi.fn()} />);

    await fillAndSubmit({ email: "pat@example.com", password: "12345" });

    expect(screen.getByText("Enter your name.")).toBeInTheDocument();
    expect(screen.getByText("Use at least 6 characters.")).toBeInTheDocument();
    expect(screen.getByText("Choose Organiser or Attendee.")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
    expect(signUp).not.toHaveBeenCalled();
  });

  it("TC-US16A-50: signs up with the name and role, then asks to check email", async () => {
    signUp.mockResolvedValue({ data: { user: { id: "u1", identities: [{ id: "i1" }] }, session: null }, error: null });
    render(<SignUpPage onShowLogin={vi.fn()} />);

    await fillAndSubmit({ name: " Pat Person ", email: "pat@example.com", password: "secret-123", role: "Organiser" });

    expect(await screen.findByText("Check your email to confirm your account")).toBeInTheDocument();
    expect(signUp).toHaveBeenCalledWith({
      email: "pat@example.com",
      password: "secret-123",
      options: { data: { full_name: "Pat Person", role: "organiser" }, emailRedirectTo: window.location.origin },
    });
    expect(screen.queryByRole("button", { name: "Create account" })).not.toBeInTheDocument();
  });

  it("TC-US16A-43: refuses an email that already has an account", async () => {
    signUp.mockResolvedValue({ data: { user: { id: "u1", identities: [] }, session: null }, error: null });
    render(<SignUpPage onShowLogin={vi.fn()} />);

    await fillAndSubmit({ name: "Pat", email: "event.coordinator@smu.edu.sg", password: "secret-123", role: "Attendee" });

    expect(await screen.findByRole("alert")).toHaveTextContent("An account with this email already exists. Log in instead.");
    expect(screen.queryByText("Check your email to confirm your account")).not.toBeInTheDocument();
  });

  it("goes back to the login page", async () => {
    const onShowLogin = vi.fn();
    render(<SignUpPage onShowLogin={onShowLogin} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "Log in" }));

    expect(onShowLogin).toHaveBeenCalled();
  });
});
