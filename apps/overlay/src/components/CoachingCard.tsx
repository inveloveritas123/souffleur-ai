/**
 * CoachingCard — baut sich gestreamt auf (`card.streamed`-Deltas, siehe `useLiveSession`)
 * und respektiert den Anzeige-Cooldown (`CARD_MIN_DWELL_MS`, dort implementiert). Zeigt
 * Karten-Typ + laufend wachsenden Text; "complete" markiert den Empfang von `card.proposed`.
 */
import type { CoachingCardState } from "../lib/types";

const CARD_TYPE_LABEL: Record<string, string> = {
  einwand: "Einwand",
  frage: "Vertiefende Frage",
  strukturhinweis: "Strukturhinweis",
};

export function CoachingCard({ card }: { card: CoachingCardState | null }) {
  if (!card) {
    return <div className="coaching-card coaching-card--empty" data-testid="coaching-card-empty" />;
  }

  const label = card.cardType ? CARD_TYPE_LABEL[card.cardType] ?? card.cardType : "Coaching-Hinweis";

  return (
    <div
      className={`coaching-card ${card.complete ? "coaching-card--complete" : "coaching-card--streaming"}`}
      data-testid="coaching-card"
    >
      <div className="coaching-card__type">{label}</div>
      <div className="coaching-card__text">
        {card.text || "…"}
        {!card.complete && <span className="coaching-card__cursor" aria-hidden="true" />}
      </div>
    </div>
  );
}
