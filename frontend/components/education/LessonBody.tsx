"use client";
import { useMemo } from "react";
import type { GlossaryEntry } from "@/lib/api";

/**
 * Renders lesson prose with two enhancements:
 *
 *  1. **Inline glossary terms.** Any glossary term appearing in the body is
 *     wrapped in a dotted-underline <abbr> carrying its definition, so a
 *     beginner never has to leave the lesson to look up a word. Only the
 *     FIRST occurrence of each term is marked — underlining every instance
 *     of "share" in a lesson about shares would be unreadable.
 *
 *  2. **Minimal markdown.** The content bank uses `**bold**` for emphasis
 *     and blank lines for paragraphs. That's the entire syntax in use, so a
 *     full markdown parser would be a dependency with no payoff.
 *
 * Term matching is done on word boundaries against the longest terms first,
 * so "dividend yield" is matched as one term rather than being broken by an
 * earlier match on "dividend".
 */

interface Props {
  body: string;
  glossary: GlossaryEntry[];
}

type Segment = { text: string; term?: GlossaryEntry; bold?: boolean };

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Split one paragraph into plain text and glossary-term segments. */
function segmentParagraph(
  paragraph: string,
  glossary: GlossaryEntry[],
  used: Set<string>,
): Segment[] {
  const remaining = glossary.filter((g) => !used.has(g.term.toLowerCase()));
  if (remaining.length === 0) return [{ text: paragraph }];

  // Longest-first prevents a short term from splitting a longer one.
  const sorted = [...remaining].sort((a, b) => b.term.length - a.term.length);
  const pattern = new RegExp(`\\b(${sorted.map((g) => escapeRegex(g.term)).join("|")})\\b`, "i");

  const segments: Segment[] = [];
  let rest = paragraph;

  while (rest.length > 0) {
    const match = pattern.exec(rest);
    if (!match || match.index === undefined) {
      segments.push({ text: rest });
      break;
    }
    const matched = match[0];
    const entry = sorted.find((g) => g.term.toLowerCase() === matched.toLowerCase());
    if (!entry || used.has(entry.term.toLowerCase())) {
      // Already used elsewhere in the lesson — emit as plain text and move past it.
      segments.push({ text: rest.slice(0, match.index + matched.length) });
      rest = rest.slice(match.index + matched.length);
      continue;
    }
    if (match.index > 0) segments.push({ text: rest.slice(0, match.index) });
    segments.push({ text: matched, term: entry });
    used.add(entry.term.toLowerCase());
    rest = rest.slice(match.index + matched.length);
  }
  return segments;
}

/**
 * Bold runs are tokenized BEFORE glossary matching, not after.
 *
 * Order matters here and getting it wrong is visible to the user: the body
 * writes some glossary terms inside emphasis, e.g. `**dividend**`. If the
 * glossary segmenter runs first it consumes "dividend" and leaves the
 * surrounding `**` stranded in adjacent text nodes, which then render as
 * literal asterisks. Splitting on `**…**` first means each run is either
 * bold or not, and glossary matching happens safely inside it.
 */
function splitBoldRuns(paragraph: string): { text: string; bold: boolean }[] {
  return paragraph
    .split(/(\*\*[^*]+\*\*)/g)
    .filter((part) => part.length > 0)
    .map((part) =>
      part.startsWith("**") && part.endsWith("**") && part.length > 4
        ? { text: part.slice(2, -2), bold: true }
        : { text: part, bold: false },
    );
}

export default function LessonBody({ body, glossary }: Props) {
  const paragraphs = useMemo(() => {
    const used = new Set<string>();
    return body.split("\n\n").map((p) =>
      splitBoldRuns(p).flatMap((run) =>
        segmentParagraph(run.text, glossary, used).map((seg) => ({ ...seg, bold: run.bold })),
      ),
    );
  }, [body, glossary]);

  return (
    <div className="space-y-4 leading-relaxed text-[15px] text-aureus-text">
      {paragraphs.map((segments, pi) => (
        <p key={pi} className="whitespace-pre-line">
          {segments.map((seg, si) => {
            const key = `${pi}-${si}`;
            const inner = seg.term ? (
              <abbr
                title={seg.term.definition}
                className="cursor-help border-b border-dotted border-aureus-gold/70 text-aureus-gold/95 no-underline"
              >
                {seg.text}
              </abbr>
            ) : (
              seg.text
            );
            return seg.bold ? (
              <strong key={key} className="text-white font-semibold">{inner}</strong>
            ) : (
              <span key={key}>{inner}</span>
            );
          })}
        </p>
      ))}
    </div>
  );
}
