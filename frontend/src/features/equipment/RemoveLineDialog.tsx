import { useId, useState } from "react";
import { equipmentErrorMessage } from "./equipmentApi";
import type { EquipmentLine } from "./types";
import "../registration/registration.css";
import "../eventRequest/eventRequests.css";

interface RemoveLineDialogProps {
  line: EquipmentLine;
  // Removes; throws the API's refusal (e.g. LINE_NOT_PENDING) for the dialog to explain.
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

/** US26 AC 2: removing a pending line deletes it, so it asks first, like Withdraw on a venue request (PR #69 review). */
export function RemoveLineDialog({ line, onConfirm, onClose }: RemoveLineDialogProps) {
  const titleId = useId();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    setError(null);
    setSubmitting(true);
    try {
      await onConfirm();
    } catch (reason) {
      setError(equipmentErrorMessage(reason));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(e) => e.stopPropagation()}>
        <button type="button" className="dialog__close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h3 id={titleId} className="reg-form__title">
          Remove this equipment line?
        </h3>
        <p className="reg-form__meta">
          {line.equipment_type.name} · Quantity {line.quantity}
        </p>
        <p className="reg-form__notice">The line is deleted and Tech support stop seeing it. To ask again, add it again.</p>

        {error && (
          <p className="reg-form__error" role="alert">
            {error}
          </p>
        )}

        <div className="withdraw__actions">
          {error ? (
            <button type="button" className="request-button request-button--secondary" onClick={onClose}>
              Back to equipment
            </button>
          ) : (
            <>
              <button type="button" className="request-button request-button--quiet" onClick={onClose}>
                Keep line
              </button>
              <button
                type="button"
                className="request-button request-button--primary"
                onClick={() => void handleConfirm()}
                disabled={submitting}
              >
                {submitting ? "Removing…" : "Remove line"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
