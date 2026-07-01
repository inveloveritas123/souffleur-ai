import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiClientError, getProtocol } from "../api/client";
import type { ProtocolResult } from "../api/types";
import { useConsent } from "../state/ConsentContext";
import { useProtocol } from "../state/ProtocolContext";

function buildMarkdown(protocol: ProtocolResult): string {
  const lines: string[] = [];
  lines.push(`# Coaching-Protokoll ${protocol.protocolId}`);
  lines.push("");
  lines.push(`Erstellt: ${new Date(protocol.createdAt).toLocaleString("de-DE")}`);
  lines.push(`Dauer: ${Math.round(protocol.durationMs / 1000)}s`);
  lines.push("");
  lines.push("## Zusammenfassung");
  lines.push("");
  lines.push(protocol.summary);
  lines.push("");
  lines.push("## Transkript");
  lines.push("");
  for (const segment of protocol.segments) {
    lines.push(`**${segment.speaker}** [${segment.tStartMs}ms–${segment.tEndMs}ms]: ${segment.text}`);
  }
  return lines.join("\n");
}

function downloadTextFile(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/**
 * PDF-Export ohne zusätzliche Abhängigkeit: nutzt den Browser-Druckdialog auf
 * einer eigenen Druckansicht. Für Welle 9 (Playwright-E2E, Akzeptanzkriterium
 * "Export als Markdown und PDF ist auslösbar") reicht ein auslösbarer Trigger;
 * eine dedizierte PDF-Bibliothek kann dort bei Bedarf ergänzt werden.
 */
function exportAsPdf(protocol: ProtocolResult): void {
  const printWindow = window.open("", "_blank");
  if (!printWindow) return;
  const summaryHtml = protocol.summary.replace(/\n/g, "<br />");
  const segmentsHtml = protocol.segments
    .map((segment) => `<p><strong>${segment.speaker}</strong> [${segment.tStartMs}ms]: ${segment.text}</p>`)
    .join("");
  printWindow.document.write(
    `<html><head><title>Protokoll ${protocol.protocolId}</title></head><body>` +
      `<h1>Coaching-Protokoll</h1><h2>Zusammenfassung</h2><p>${summaryHtml}</p>` +
      `<h2>Transkript</h2>${segmentsHtml}</body></html>`,
  );
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}

/** Schritt 3: diarisiertes Transkript + Zusammenfassung anzeigen und exportieren. */
export function ProtocolView() {
  const { protocolId } = useParams<{ protocolId?: string }>();
  const { protocol: contextProtocol, setProtocol } = useProtocol();
  const { consent } = useConsent();
  const [fetchedProtocol, setFetchedProtocol] = useState<ProtocolResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const protocol =
    protocolId && contextProtocol?.protocolId !== protocolId ? fetchedProtocol : contextProtocol;

  useEffect(() => {
    if (!protocolId || contextProtocol?.protocolId === protocolId) return;
    if (!consent?.consentRef) {
      setError("Kein gültiger Einwilligungsnachweis vorhanden. Bitte Einwilligung erneut bestätigen.");
      return;
    }
    setIsLoading(true);
    setError(null);
    getProtocol(protocolId, consent.consentRef)
      .then((result) => {
        setFetchedProtocol(result);
        setProtocol(result);
      })
      .catch((cause: unknown) => {
        setError(
          cause instanceof ApiClientError
            ? cause.message
            : "Protokoll konnte nicht geladen werden.",
        );
      })
      .finally(() => setIsLoading(false));
  }, [protocolId, contextProtocol, consent, setProtocol]);

  if (isLoading) {
    return (
      <section data-testid="protocol-view">
        <p data-testid="protocol-loading">Protokoll wird geladen …</p>
      </section>
    );
  }

  if (error) {
    return (
      <section data-testid="protocol-view">
        <p role="alert" data-testid="protocol-error">
          {error}
        </p>
      </section>
    );
  }

  if (!protocol) {
    return (
      <section data-testid="protocol-view">
        <p data-testid="protocol-empty">
          Noch kein Protokoll vorhanden. <Link to="/upload">Jetzt Audio hochladen.</Link>
        </p>
      </section>
    );
  }

  return (
    <section data-testid="protocol-view" aria-labelledby="protocol-heading">
      <h1 id="protocol-heading">Protokoll</h1>
      <p data-testid="protocol-meta">
        Sitzung {protocol.sessionId} · {Math.round(protocol.durationMs / 1000)}s · Sprecher:{" "}
        {protocol.speakers.join(", ")}
      </p>

      <article data-testid="protocol-summary">
        <h2>Zusammenfassung</h2>
        <p>{protocol.summary}</p>
      </article>

      <article>
        <h2>Diarisiertes Transkript</h2>
        <ol data-testid="protocol-segment-list">
          {protocol.segments.map((segment, index) => (
            <li key={index} data-testid="protocol-segment">
              <strong>{segment.speaker}</strong>{" "}
              <span className="segment-timestamp">
                [{segment.tStartMs}ms–{segment.tEndMs}ms]
              </span>
              : {segment.text}
            </li>
          ))}
        </ol>
      </article>

      <div className="protocol-export-actions">
        <button
          type="button"
          data-testid="export-markdown-button"
          onClick={() => downloadTextFile(`${protocol.protocolId}.md`, buildMarkdown(protocol), "text/markdown")}
        >
          Export als Markdown
        </button>
        <button type="button" data-testid="export-pdf-button" onClick={() => exportAsPdf(protocol)}>
          Export als PDF
        </button>
      </div>
    </section>
  );
}
