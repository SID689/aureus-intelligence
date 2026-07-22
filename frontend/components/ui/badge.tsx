import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide",
  {
    variants: {
      variant: {
        default:       "bg-aureus-gold/20 text-aureus-gold border border-aureus-gold/40",
        green:         "bg-green-950/40 text-aureus-green border border-aureus-green/40",
        red:           "bg-red-950/40 text-aureus-red border border-aureus-red/40",
        muted:         "bg-gray-800 text-aureus-muted border border-aureus-border",
        institutional: "bg-purple-950/40 text-purple-400 border border-purple-400/40",
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
