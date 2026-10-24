import { useState, type FormEvent, type ReactNode } from "react";
import { SIGN_UP_ROLES, signUpOutcome, validateSignUp, type SignUpFields } from "./signUp";
import { supabase } from "./supabase";
import "../features/eventRequest/eventRequests.css";
import "./auth.css";

interface SignUpPageProps {
  onShowLogin: () => void;
}

const EMPTY: SignUpFields = { full_name: "", email: "", password: "", role: "" };

// SCRUM-106: Organisers and Attendees sign themselves up (US16a AC 6); staff accounts are seeded (AC 7).
export function SignUpPage({ onShowLogin }: SignUpPageProps) {
  const [fields, setFields] = useState<SignUpFields>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof SignUpFields, string>>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  function set<K extends keyof SignUpFields>(name: K, value: SignUpFields[K]) {
    setFields((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validateSignUp(fields);
    setErrors(found);
    setError(null);
    if (Object.keys(found).length > 0 || !supabase) return;

    setBusy(true);
    const result = await supabase.auth.signUp({
      email: fields.email.trim(),
      password: fields.password,
      // Read back at the first login to create the profile; the confirmation link returns to this app.
      options: { data: { full_name: fields.full_name.trim(), role: fields.role }, emailRedirectTo: window.location.origin },
    });
    setBusy(false);
    const outcome = signUpOutcome(result);
    if (outcome.kind === "check_email") setSent(true);
    else if (outcome.kind === "already_registered") setError("An account with this email already exists. Log in instead.");
    else setError(outcome.message);
  }

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <span className="request-page__eyebrow">CONNECTSPHERE</span>
          <h1>Create an account</h1>
        </div>
      </div>
      {sent ? (
        <div className="request-notice" role="status">
          <strong>Check your email to confirm your account</strong>
          <p>We sent a link to {fields.email.trim()}. Open it, then log in.</p>
        </div>
      ) : (
        <form className="request-form" onSubmit={handleSubmit} aria-label="Create an account" noValidate>
          {error && (
            <div className="request-alert" role="alert">
              {error}
            </div>
          )}
          <div className="request-form__section">
            <Field label="Name" errorId="sign-up-full_name-error" error={errors.full_name}>
              <input
                autoComplete="name"
                value={fields.full_name}
                aria-invalid={errors.full_name ? true : undefined}
                aria-describedby={errors.full_name ? "sign-up-full_name-error" : undefined}
                onChange={(e) => set("full_name", e.target.value)}
              />
            </Field>
            <Field label="Email" errorId="sign-up-email-error" error={errors.email}>
              <input
                type="email"
                autoComplete="email"
                value={fields.email}
                aria-invalid={errors.email ? true : undefined}
                aria-describedby={errors.email ? "sign-up-email-error" : undefined}
                onChange={(e) => set("email", e.target.value)}
              />
            </Field>
            <Field label="Password" errorId="sign-up-password-error" error={errors.password}>
              <input
                type="password"
                autoComplete="new-password"
                value={fields.password}
                aria-invalid={errors.password ? true : undefined}
                aria-describedby={errors.password ? "sign-up-password-error" : undefined}
                onChange={(e) => set("password", e.target.value)}
              />
            </Field>
            <fieldset
              className="request-field auth-roles"
              aria-invalid={errors.role ? true : undefined}
              aria-describedby={errors.role ? "sign-up-role-error" : undefined}
            >
              <legend>I'm signing up as</legend>
              {SIGN_UP_ROLES.map((role) => (
                <label key={role.value}>
                  <input
                    type="radio"
                    name="role"
                    value={role.value}
                    checked={fields.role === role.value}
                    onChange={() => set("role", role.value)}
                  />{" "}
                  {role.label}
                </label>
              ))}
              {errors.role && (
                <span id="sign-up-role-error" className="auth-field-error">
                  {errors.role}
                </span>
              )}
            </fieldset>
          </div>
          <div className="request-form__actions">
            <button type="submit" className="request-button request-button--primary" disabled={busy}>
              {busy ? "Creating account…" : "Create account"}
            </button>
          </div>
        </form>
      )}
      <p>
        Already have an account?{" "}
        <button type="button" className="request-button request-button--secondary" onClick={onShowLogin}>
          Log in
        </button>
      </p>
    </main>
  );
}

// The error sits after the label, not inside it, so the field's accessible name stays its label.
function Field({ label, errorId, error, children }: { label: string; errorId: string; error?: string; children: ReactNode }) {
  return (
    <div>
      <label className="request-field">
        {label}
        {children}
      </label>
      {error && (
        <span id={errorId} className="auth-field-error">
          {error}
        </span>
      )}
    </div>
  );
}
