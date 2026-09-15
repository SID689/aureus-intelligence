import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Badges are typographic: caps, tracked, a hairline border and a faint
 * wash of their own colour. The top tier inverts to bone on ink, the one
 * mark of rank in the product, and it needs no extra hue to say so.
 */
const badgeVariants = cva(
  "inline-flex items-center rounded px-2 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-[0.12em] whitespace-nowrap",
  {
    variants: {
      variant: {
        default:       "bg-aureus-gold/10 text-aureus-gold border border-aureus-gold/30",
        green:         "bg-aureus-emerald/10 text-aureus-emerald border border-aureus-emerald/30",
        red:           "bg-aureus-crimson/10 text-aureus-crimson border border-aureus-crimson/30",
        amber:         "bg-aureus-amber/10 text-aureus-amber border border-aureus-amber/30",
        muted:         "bg-aureus-panellift text-aureus-muted border border-aureus-rule",
        institutional: "bg-aureus-text text-aureus-ink border border-aureus-text",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
