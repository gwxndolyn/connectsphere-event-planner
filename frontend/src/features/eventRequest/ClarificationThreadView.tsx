import { sectionLabel } from "./clarificationSections";
import type { Clarification } from "./types";

interface ClarificationThreadViewProps {
  messages: Clarification[];
  title?: string;
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString();
}

// US8c AC 1, 3: every round's question with the organiser's answer beneath it (SCRUM-58).
// The API already returns the thread oldest round first, question before reply.
export function ClarificationThreadView({ messages, title = "Clarification thread" }: ClarificationThreadViewProps) {
  const rounds = [...new Set(messages.map((message) => message.round))].sort((a, b) => a - b);

  return (
    <section className="clarify-thread" aria-label={title}>
      <h2>{title}</h2>
      <ol className="clarify-thread__rounds">
        {rounds.map((round) => {
          const question = messages.find((message) => message.round === round && message.kind === "request");
          const reply = messages.find((message) => message.round === round && message.kind === "response");
          return (
            <li className="clarify-thread__round" key={round} aria-label={`Round ${round}`}>
              <p className="clarify-thread__round-label">Round {round}</p>
              {question && (
                <article className="clarify-message clarify-message--question">
                  <header>
                    <strong>Coordinator asked</strong>
                    <time dateTime={question.created_at}>{formatTime(question.created_at)}</time>
                  </header>
                  <ul className="clarify-sent-sections" aria-label={`Round ${round} sections`}>
                    {(question.sections ?? []).map((key) => (
                      <li key={key}>{sectionLabel(key)}</li>
                    ))}
                  </ul>
                  <p>{question.comment}</p>
                </article>
              )}
              {reply ? (
                <article className="clarify-message clarify-message--reply">
                  <header>
                    <strong>Organiser replied</strong>
                    <time dateTime={reply.created_at}>{formatTime(reply.created_at)}</time>
                  </header>
                  <p>{reply.comment}</p>
                </article>
              ) : (
                <p className="clarify-thread__waiting">Waiting for the organiser's response.</p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
