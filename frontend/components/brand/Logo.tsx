import Image from "next/image";

/**
 * The Aureus mark, in one place.
 *
 * Every brand surface renders through this rather than each page
 * hardcoding its own <Image> — otherwise the four places the wordmark
 * appears drift apart the first time the logo is revised, which is
 * exactly what happened to the tier feature list.
 *
 * WHICH FILE GETS USED
 * The transparent variant is the default. The source PNG has its own
 * #151515 background baked in, which no longer matches --panel at all
 * now that panels sit at #191d12, so the solid version would render as
 * a visibly darker square on any surface. The transparent cut lets the mark sit on whatever is
 * behind it — and is the only version that will work when a light
 * marketing page or an emailed invoice needs it.
 *
 * The solid version stays for favicon and app-store use, where a
 * background is mandatory rather than optional.
 */

interface Props {
  /** Rendered size in px. 2x assets are served automatically. */
  size?: number;
  /** Show the "Aureus" wordmark beside the mark. */
  withWordmark?: boolean;
  /** Wordmark size — defaults to a proportion of `size`. */
  wordmarkClassName?: string;
  /** Small caps line under the wordmark, e.g. "Intelligence Platform". */
  tagline?: string;
  className?: string;
}

/** Pick the smallest rendered asset that still covers a 2x display. */
function assetFor(size: number): string {
  const need = size * 2;
  const available = [64, 96, 192, 256, 512];
  const chosen = available.find((a) => a >= need) ?? 1024;
  return `/brand/mark-transparent-${chosen}.png`;
}

export default function Logo({
  size = 32,
  withWordmark = false,
  wordmarkClassName = "text-xl",
  tagline,
  className = "",
}: Props) {
  const mark = (
    <Image
      src={assetFor(size)}
      alt="Aureus Intelligence"
      width={size}
      height={size}
      // The mark is decorative wherever a wordmark sits beside it; the
      // alt above still carries the name for the standalone case.
      priority
      style={{ width: size, height: size }}
    />
  );

  if (!withWordmark) {
    return <span className={className}>{mark}</span>;
  }

  // The tagline sits BELOW the mark-and-wordmark row rather than beside
  // the mark. Nested under the wordmark it only had the column width left
  // over after the mark, which in the 224px sidebar wrapped "Intelligence
  // Platform" onto two lines. Spanning the full width fits it on one.
  return (
    <div className={className}>
      <div className="flex items-center gap-2.5">
        {mark}
        <div
          className={`font-display text-aureus-gold tracking-wide leading-none ${wordmarkClassName}`}
          style={{ fontWeight: 600 }}
        >
          Aureus
        </div>
      </div>
      {tagline && (
        <div className="text-aureus-muted text-[10px] mt-1.5 tracking-widest uppercase leading-none whitespace-nowrap">
          {tagline}
        </div>
      )}
    </div>
  );
}
