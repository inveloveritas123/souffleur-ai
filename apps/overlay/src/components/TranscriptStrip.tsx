/**
 * TranscriptStrip — knapper Transkript-Kontext (letzte Zeilen) unter dem Consent-Banner.
 * Reine Anzeige des zuletzt bestätigten (`transcript.final`) Verlaufs; kein eigener State
 * jenseits dessen, was `useLiveSession` liefert.
 */
import type { TranscriptLine } from "../lib/types";

const SPEAKER_LABEL: Record<string, string> = {
  coach: "Coach",
  counterpart: "Gegenüber",
  unknown: "?",
};

export function TranscriptStrip({ lines }: { lines: TranscriptLine[] }) {
  if (lines.length === 0) return null;
  return (
    <ul className="transcript-strip" data-testid="transcript-strip">
      {lines.map((line) => (
        <li key={`${line.tsMs}-${line.speaker}`} className="transcript-strip__line">
          <span className="transcript-strip__speaker">{SPEAKER_LABEL[line.speaker] ?? line.speaker}:</span>{" "}
          <span className="transcript-strip__text">{line.text}</span>
        </li>
      ))}
    </ul>
  );
}
