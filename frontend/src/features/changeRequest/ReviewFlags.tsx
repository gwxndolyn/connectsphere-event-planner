import { useEffect, useState } from "react";
import { formatInstantDateTime } from "../registration/datetime";
import { changeReviewApi, flagErrorMessage, reviewLabel } from "./changeRequestApi";
import type { ReviewFlag } from "./types";
import "./changeRequests.css";

interface ReviewFlagsProps {
  eventId: string;
  // Called after a flag is marked reviewed, so the readiness list is read again.
  onChanged: () => void;
}

const RESOLVED: Record<ReviewFlag["kind"], string> = {
  venue_booking: "Resolved: the booking is no longer live, so there is nothing to review.",
  equipment_reservation: "Resolved: the reservation was released, so there is nothing to review.",
  registrations: "Resolved.",
};

/**
 * US29b AC 3 (SCRUM-143, D104): what an approved significant change flagged on the event, for its coordinator to
 * review. Nothing on the booking, reservation or registrations changed; Mark reviewed records that someone looked.
 * A flag whose booking was withdrawn or whose reservation was released reads as resolved. Confirming waits until
 * none is open (the readiness item). Deviation 71: under the readiness list, where confirming is decided.
 */
export function ReviewFlags({ eventId, onChanged }: ReviewFlagsProps) {
  const [flags, setFlags] = useState<ReviewFlag[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    changeReviewApi
      .flags(eventId)
      .then((found) => {
        if (current) setFlags(found);
      })
      .catch((reason: unknown) => {
        if (current) setError(flagErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, [eventId]);

  if (error) return <div className="request-alert" role="alert">{error}</div>;
  if (!flags || flags.length === 0) return null;
  return (
    <section className="review-flags" aria-labelledby="review-flags-title">
      <h3 id="review-flags-title">Review after change</h3>
      <p className="request-notice">
        An approved change may have overtaken these arrangements. Nothing on them changed: check each, then mark it
        reviewed.
      </p>
      <ul className="review-flags__list">
        {flags.map((flag) => (
          <FlagRow
            key={flag.id}
            flag={flag}
            onCleared={(cleared) => {
              setFlags((current) => current?.map((f) => (f.id === cleared.id ? cleared : f)) ?? null);
              onChanged();
            }}
          />
        ))}
      </ul>
    </section>
  );
}

function FlagRow({ flag, onCleared }: { flag: ReviewFlag; onCleared: (flag: ReviewFlag) => void }) {
  const [marking, setMarking] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const label = flag.kind === "registrations" ? "Registrations" : (flag.target?.label ?? flag.kind);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      onCleared(await changeReviewApi.clearFlag(flag.id, note));
      setMarking(false);
    } catch (reason) {
      setError(flagErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={`review-flags__item${flag.open ? " review-flags__item--open" : ""}`}>
      <strong>{label}</strong>
      <span>
        Changed: {flag.fields.map(reviewLabel).join(", ")} · flagged {formatInstantDateTime(flag.raised_at)}
      </span>
      {flag.cleared_at ? (
        <span>
          Reviewed by {flag.cleared_by?.name ?? "the coordinator"} on {formatInstantDateTime(flag.cleared_at)}
          {flag.cleared_note ? `: ${flag.cleared_note}` : "."}
        </span>
      ) : flag.resolved ? (
        <span>{RESOLVED[flag.kind]}</span>
      ) : marking ? (
        <span className="review-flags__mark">
          <label className="request-field request-field--wide">
            Note (optional)
            <textarea rows={2} value={note} onChange={(changed) => setNote(changed.target.value)} />
          </label>
          {error && <span className="request-alert" role="alert">{error}</span>}
          <span className="request-form__actions">
            <button className="request-button request-button--quiet" type="button" disabled={busy} onClick={() => setMarking(false)}>
              Cancel
            </button>
            <button className="request-button request-button--primary" type="button" disabled={busy} onClick={() => void save()}>
              {busy ? "Saving…" : "Save review"}
            </button>
          </span>
        </span>
      ) : (
        <span className="request-form__actions">
          <button className="request-button request-button--quiet" type="button" onClick={() => setMarking(true)}>
            Mark reviewed
          </button>
        </span>
      )}
    </li>
  );
}
