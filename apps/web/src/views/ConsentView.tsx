import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { CONSENT_TEXT_VERSION, useConsent } from "../state/ConsentContext";

/**
 * Schritt 1 (verbindlich, §201 StGB): explizite, dokumentierte Einwilligung
 * VOR jeder Aufnahme/Verarbeitung. Ohne Bestätigung hier gibt es keinen Zugang
 * zum Upload-Schritt (siehe RequireConsent + Backend-ConsentGate, HTTP 403).
 */
export function ConsentView() {
  const { hasConsent, consent, status, error, confirmConsent } = useConsent();
  const [acknowledged, setAcknowledged] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await confirmConsent(acknowledged);
  }

  return (
    <section data-testid="consent-view" aria-labelledby="consent-heading">
      <h1 id="consent-heading">Einwilligung zur Aufnahme und Verarbeitung</h1>
      <p>
        Bevor ein Gespräch aufgenommen oder ein bestehendes Audio hochgeladen werden darf, ist
        nach § 201 StGB die ausdrückliche, dokumentierte Einwilligung aller Beteiligten
        erforderlich. Souffleur AI verarbeitet das Gespräch ausschließlich nach Bestätigung
        dieser Einwilligung.
      </p>
      <ul>
        <li>Die Aufnahme wird zur Transkription (Diarisation) und Zusammenfassung verarbeitet.</li>
        <li>Verarbeitung erfolgt EU-souverän (Mistral, Paris) — keine Drittlandübermittlung.</li>
        <li>Jede Verarbeitung wird unveränderlich im Audit-Log vermerkt.</li>
        <li>Diese Einwilligung gilt für die aktuelle Sitzung (Textfassung {CONSENT_TEXT_VERSION}).</li>
      </ul>

      {hasConsent && consent ? (
        <p role="status" data-testid="consent-success">
          Einwilligung dokumentiert ({consent.consentRef}) am{" "}
          {new Date(consent.acceptedAt).toLocaleString("de-DE")}. Du kannst jetzt fortfahren.
        </p>
      ) : null}

      <form onSubmit={handleSubmit} data-testid="consent-form">
        <label htmlFor="consent-checkbox" className="consent-checkbox-label">
          <input
            id="consent-checkbox"
            type="checkbox"
            data-testid="consent-checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          Ich bestätige, dass alle Gesprächsteilnehmenden der Aufnahme und Verarbeitung
          ausdrücklich zugestimmt haben.
        </label>

        <button
          type="submit"
          data-testid="consent-confirm-button"
          disabled={!acknowledged || status === "submitting"}
        >
          {status === "submitting" ? "Wird dokumentiert …" : "Einwilligung bestätigen"}
        </button>

        {error ? (
          <p role="alert" data-testid="consent-error">
            {error}
          </p>
        ) : null}
      </form>

      {hasConsent ? (
        <button
          type="button"
          data-testid="consent-continue-button"
          onClick={() => navigate("/upload")}
        >
          Weiter zum Upload
        </button>
      ) : null}
    </section>
  );
}
