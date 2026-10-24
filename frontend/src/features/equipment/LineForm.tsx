import { useState, type FormEvent, type ReactNode } from "react";
import { equipmentErrorMessage, equipmentFieldErrors } from "./equipmentApi";
import type { EquipmentType, LineFormValues } from "./types";
import "../eventRequest/eventRequests.css";
import "../venue/venues.css";

interface LineFormProps {
  // The form's accessible name, e.g. "Add equipment" or "Edit Projector".
  label: string;
  // Keeps field ids unique when an edit form and the add form are both on screen.
  idPrefix: string;
  types: EquipmentType[];
  initial: LineFormValues;
  submitLabel: string;
  // Saves; throws the API's refusal for the form to show on its fields (AC 4).
  onSubmit: (values: LineFormValues) => Promise<void>;
  onCancel?: () => void;
  // After a successful add, so the next line starts blank.
  resetOnSuccess?: boolean;
}

/** A line's type, quantity and notes (US26 AC 1, 2). The API checks them; its errors show beside each field. */
export function LineForm({ label, idPrefix, types, initial, submitLabel, onSubmit, onCancel, resetOnSuccess }: LineFormProps) {
  const [form, setForm] = useState<LineFormValues>(initial);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);

  function update(key: keyof LineFormValues, value: string, apiField?: string) {
    setForm((current) => ({ ...current, [key]: value }));
    if (apiField) setFieldErrors(({ [apiField]: _cleared, ...rest }) => rest);
  }

  async function handleSubmit(submitted: FormEvent<HTMLFormElement>) {
    submitted.preventDefault();
    setSending(true);
    setError(null);
    setFieldErrors({});
    try {
      await onSubmit(form);
      if (resetOnSuccess) setForm(initial);
    } catch (reason) {
      const fields = equipmentFieldErrors(reason);
      setFieldErrors(fields);
      // The field says what's wrong; the alert only points to it.
      setError(Object.keys(fields).length > 0 ? "Review the fields marked below and try again." : equipmentErrorMessage(reason));
    } finally {
      setSending(false);
    }
  }

  function invalid(apiField: string) {
    return fieldErrors[apiField]
      ? { "aria-invalid": true as const, "aria-describedby": `${idPrefix}-${apiField}-error` }
      : { "aria-invalid": undefined, "aria-describedby": undefined };
  }

  function field(text: string, apiField: string, control: ReactNode) {
    const message = fieldErrors[apiField];
    return (
      <div className={`request-field${message ? " request-field--invalid" : ""}`}>
        <label htmlFor={`${idPrefix}-${apiField}`}>{text}</label>
        {control}
        {message && (
          <span id={`${idPrefix}-${apiField}-error`} className="venue-field-error">
            {message}
          </span>
        )}
      </div>
    );
  }

  return (
    <form className="venue-booking-form" aria-label={label} noValidate onSubmit={(submitted) => void handleSubmit(submitted)}>
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      <div className="venue-filters">
        {field(
          "Equipment type",
          "equipment_type_id",
          <select
            id={`${idPrefix}-equipment_type_id`}
            value={form.typeId}
            onChange={(changed) => update("typeId", changed.target.value, "equipment_type_id")}
            {...invalid("equipment_type_id")}
          >
            <option value="">Choose a type</option>
            {types.map((type) => (
              <option key={type.id} value={type.id}>
                {type.name}
              </option>
            ))}
          </select>,
        )}
        {field(
          "Quantity",
          "quantity",
          <input
            id={`${idPrefix}-quantity`}
            type="number"
            min={1}
            step={1}
            value={form.quantity}
            onChange={(changed) => update("quantity", changed.target.value, "quantity")}
            {...invalid("quantity")}
          />,
        )}
        <div className="request-field venue-form__wide">
          <label htmlFor={`${idPrefix}-notes`}>Notes</label>
          <textarea id={`${idPrefix}-notes`} rows={2} value={form.notes} onChange={(changed) => update("notes", changed.target.value)} />
        </div>
      </div>
      <div className="request-form__actions">
        {onCancel && (
          <button type="button" className="request-button request-button--quiet" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="submit" className="request-button request-button--primary" disabled={sending}>
          {sending ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
