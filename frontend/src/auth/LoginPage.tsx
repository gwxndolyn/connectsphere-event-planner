import { useState, type FormEvent } from "react";
import { loginErrorMessage } from "./messages";
import { supabase } from "./supabase";
import "../features/eventRequest/eventRequests.css";

interface LoginPageProps {
  onLoggedIn: () => void;
  // SCRUM-106: Organisers and Attendees can create their own account.
  onShowSignUp: () => void;
}

export function LoginPage({ onLoggedIn, onShowSignUp }: LoginPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (signInError) {
      setError(loginErrorMessage(signInError));
      return;
    }
    // The session listener in App takes over; this asks it to open the role's home screen.
    onLoggedIn();
  }

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <span className="request-page__eyebrow">CONNECTSPHERE</span>
          <h1>Log in</h1>
        </div>
      </div>
      {!supabase ? (
        <div className="request-alert" role="alert">
          Login isn't set up: add VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY to frontend/.env, then restart
          the frontend.
        </div>
      ) : (
        <form className="request-form" onSubmit={handleSubmit} aria-label="Log in">
          {error && (
            <div className="request-alert" role="alert">
              {error}
            </div>
          )}
          <div className="request-form__section">
            <label className="request-field">
              Email
              <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="request-field">
              Password
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
          </div>
          <div className="request-form__actions">
            <button type="submit" className="request-button request-button--primary" disabled={busy}>
              {busy ? "Logging in…" : "Log in"}
            </button>
          </div>
        </form>
      )}
      {supabase && (
        <p>
          New to ConnectSphere?{" "}
          <button type="button" className="request-button request-button--secondary" onClick={onShowSignUp}>
            Create an account
          </button>
        </p>
      )}
    </main>
  );
}
