"use client";
/**
 * A QR code, drawn as an SVG plate for projecting on a slide.
 *
 * DARK MODULES ON A LIGHT GROUND, deliberately, on a site that is
 * otherwise black. Inverted codes decode on most modern phones and fail
 * on enough older ones that it is not worth the risk in front of a room:
 * the one element here that absolutely has to work on a stranger's
 * three-year-old Android is the one place the house palette gives way.
 * The plate is bone rather than pure white, and the border and caption
 * keep it in the same family as the rest of the interface.
 *
 * The quiet zone is four modules, per the spec. Scanners use it to find
 * the symbol's edge, and cropping it is the most common reason a printed
 * or projected code refuses to read.
 */
import qrcode from "qrcode-generator";
import { useMemo } from "react";
import { cn } from "@/lib/utils";

const QUIET_ZONE = 4;

export default function PresentationQR({
  url,
  size = 320,
  className,
  label,
}: {
  url: string;
  size?: number;
  className?: string;
  label?: string;
}) {
  const path = useMemo(() => {
    if (!url) return null;
    try {
      // Type 0 picks the smallest version that fits. Error correction M
      // (~15%) is the usual compromise: level L saves a little density but
      // gives up the tolerance that matters when a code is photographed
      // off a projector screen at an angle.
      const qr = qrcode(0, "M");
      qr.addData(url);
      qr.make();
      const count = qr.getModuleCount();
      // One path of rectangles rather than thousands of elements: the same
      // drawing with a fraction of the DOM, which matters when this
      // re-renders as someone types a URL.
      let d = "";
      for (let row = 0; row < count; row++) {
        for (let col = 0; col < count; col++) {
          if (qr.isDark(row, col)) d += `M${col + QUIET_ZONE} ${row + QUIET_ZONE}h1v1h-1z`;
        }
      }
      return { d, extent: count + QUIET_ZONE * 2 };
    } catch {
      // Over capacity, or an empty string. The caller renders the URL as
      // text either way, so a missing plate is recoverable.
      return null;
    }
  }, [url]);

  if (!path) {
    return (
      <div
        className={cn("grid place-items-center border border-aureus-rule bg-aureus-panel text-[12px] text-aureus-muted", className)}
        style={{ width: size, height: size }}
      >
        No address to encode
      </div>
    );
  }

  return (
    <figure className={cn("inline-block", className)}>
      <svg
        viewBox={`0 0 ${path.extent} ${path.extent}`}
        width={size}
        height={size}
        role="img"
        aria-label={label ? `${label}: ${url}` : `QR code for ${url}`}
        shapeRendering="crispEdges"
        className="block border border-aureus-rulestrong"
      >
        <rect width={path.extent} height={path.extent} fill="#f2efe7" />
        <path d={path.d} fill="#0b0b0a" />
      </svg>
    </figure>
  );
}
