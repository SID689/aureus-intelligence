import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Badges carry a tinted fill and a border of the same hue. The
 * `institutional` variant is the one place purple appears anywhere on the
 * platform — it marks the top tier, and its scarcity is the point.
 */
const badgeVariants = cva(
  "inline-flex items-center rounded px-2 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-[0.12em] whitespace-nowrap",
  {
    variants: {
      variant: {
        default:       "bg-aureus-gold/10 text-aureus-gold border border-aureus-gold/30",
        green:         "bg-aureus-verdigris/10 text-aureus-verdigris border border-aureus-verdigris/30",
        red:           "bg-aureus-oxblood/10 text-aureus-oxblood border border-aureus-oxblood/30",
        amber:         "bg-aureus-amber/10 text-aureus-amber border border-aureus-amber/30",
        muted:         "bg-aureus-panellift text-aureus-muted border border-aureus-rule",
        institutional: "bg-[#3a2f52]/50 text-[#c3a9e8] border border-[#c3a9e8]/30",
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
