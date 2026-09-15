/**
 * Aureus glyphs.
 *
 * A small, deliberate set drawn for this product, replacing the icon
 * library that shipped with the starter. That library's rounded caps and
 * friendly curves are recognisable on sight, and they read as "generic web
 * app" on a surface that should read as an instrument.
 *
 * Drawing rules, so anything added later belongs to the same family:
 *   · 16-unit grid, 1.25 stroke, no fills.
 *   · Square caps and mitred joins. Nothing is rounded that does not have
 *     to be (a magnifier lens and a clock face are the only circles).
 *   · Glyphs exist for affordances only: close, navigate, expand, search,
 *     lock, alert. Nothing here is decoration. Where an icon would merely
 *     restate a label, the label stands alone.
 */
import * as React from "react";

export interface IconProps extends Omit<React.SVGProps<SVGSVGElement>, "children"> {
  size?: number;
  /** Accessible name. Omit when a visible label already says it. */
  title?: string;
}

export type IconComponent = React.FC<IconProps>;

function glyph(name: string, body: React.ReactNode): IconComponent {
  const Glyph: IconComponent = ({ size = 16, strokeWidth = 1.25, title, ...rest }) => (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="square"
      strokeLinejoin="miter"
      focusable="false"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      {...rest}
    >
      {title && <title>{title}</title>}
      {body}
    </svg>
  );
  Glyph.displayName = name;
  return Glyph;
}

// ── Navigation and disclosure ─────────────────────────────────────────

export const IconArrowRight = glyph("IconArrowRight", <path d="M2.5 8H13M9.5 4.5 13 8l-3.5 3.5" />);
export const IconArrowLeft = glyph("IconArrowLeft", <path d="M13.5 8H3M6.5 4.5 3 8l3.5 3.5" />);
export const IconArrowUpRight = glyph("IconArrowUpRight", <path d="M4 12 12 4M6 4h6v6" />);
export const IconArrowDownRight = glyph("IconArrowDownRight", <path d="M4 4l8 8M12 6v6H6" />);
export const IconChevronRight = glyph("IconChevronRight", <path d="M6 3.5 10.5 8 6 12.5" />);
export const IconChevronLeft = glyph("IconChevronLeft", <path d="M10 3.5 5.5 8l4.5 4.5" />);
export const IconChevronDown = glyph("IconChevronDown", <path d="M3.5 6 8 10.5 12.5 6" />);
export const IconChevronUp = glyph("IconChevronUp", <path d="M3.5 10 8 5.5l4.5 4.5" />);
export const IconExternal = glyph("IconExternal", <path d="M9.5 2.5h4v4M13.5 2.5l-6 6M11.5 9.5v4h-9v-9h4" />);
/** Three rules, the last one short: a menu that is recognisably not the stock hamburger. */
export const IconMenu = glyph("IconMenu", <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h6.5" />);

// ── Actions ───────────────────────────────────────────────────────────

export const IconClose = glyph("IconClose", <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />);
export const IconCheck = glyph("IconCheck", <path d="M3 8.5 6.5 12 13 4.5" />);
export const IconPlus = glyph("IconPlus", <path d="M8 3v10M3 8h10" />);
export const IconMinus = glyph("IconMinus", <path d="M3 8h10" />);
export const IconSearch = glyph("IconSearch", <><circle cx="7" cy="7" r="4.25" /><path d="M10.25 10.25 13.5 13.5" /></>);
export const IconTrash = glyph("IconTrash", <path d="M2.5 4.5h11M6 4.5v-2h4v2M4 4.5l.75 9h6.5l.75-9M6.75 7v4M9.25 7v4" />);
export const IconCopy = glyph("IconCopy", <path d="M5.5 5.5h8v8h-8zM3 10.5v-8h7.5" />);
export const IconRefresh = glyph("IconRefresh", <path d="M13 3v3.5H9.5M12.6 6.5A5 5 0 1 0 13 9.5" />);
export const IconLogout = glyph("IconLogout", <path d="M6.5 2.5h-4v11h4M6 8h7.5M10.5 5l3 3-3 3" />);
export const IconBackspace = glyph("IconBackspace", <path d="M5.5 3.5h8v9h-8L2 8zM7.75 6l3.5 4M11.25 6l-3.5 4" />);

// ── State ─────────────────────────────────────────────────────────────

/** Square shackle: the one lock glyph that does not look borrowed. */
export const IconLock = glyph("IconLock", <path d="M3.5 7.5h9v6h-9zM5.5 7.5V3.5h5v4M8 10v1.5" />);
/** An angular bell, drawn from straight segments. */
export const IconBell = glyph("IconBell", <path d="M4 11.5V6.5L6 3.5h4l2 3v5M2.5 11.5h11M6.5 13.5h3" />);
export const IconBellOff = glyph("IconBellOff", <path d="M4 11.5V6.5L6 3.5h4l2 3v5M2.5 11.5h11M6.5 13.5h3M2 2l12 12" />);
export const IconWarning = glyph("IconWarning", <path d="M8 2.5 14 13.5H2zM8 6.5v3M8 11.25v.5" />);
export const IconInfo = glyph("IconInfo", <path d="M2.5 2.5h11v11h-11zM8 7v4.5M8 4.75v.5" />);
export const IconClock = glyph("IconClock", <><circle cx="8" cy="8" r="5.5" /><path d="M8 5v3h2.5" /></>);
export const IconCalendar = glyph("IconCalendar", <path d="M2.5 3.5h11v10h-11zM2.5 6.5h11M5.5 2v2.5M10.5 2v2.5" />);

// ── Media ─────────────────────────────────────────────────────────────

export const IconMic = glyph("IconMic", <path d="M6 2.5h4v7H6zM3.5 7v2.5l2 2h5l2-2V7M8 11.5V14M5.5 14h5" />);
export const IconPlay = glyph("IconPlay", <path d="M5 3.5 12 8l-7 4.5z" />);
export const IconStop = glyph("IconStop", <path d="M4 4h8v8H4z" />);

// ── Direction ─────────────────────────────────────────────────────────

export const IconTrendUp = glyph("IconTrendUp", <path d="M2.5 11.5l4-4L9 10l4.5-4.5M10 5.5h3.5V9" />);
export const IconTrendDown = glyph("IconTrendDown", <path d="M2.5 4.5l4 4L9 6l4.5 4.5M10 10.5h3.5V7" />);
