import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded px-2 py-0.5 text-[11px] font-mono font-medium uppercase tracking-wider",
  {
    variants: {
      variant: {
        default:       "bg-aureus-gold/10 text-aureus-gold border border-aureus-gold/30",
        green:         "bg-aureus-verdigris/10 text-aureus-verdigris border border-aureus-verdigris/30",
        red:           "bg-aureus-oxblood/10 text-aureus-oxblood border border-aureus-oxblood/30",
        muted:         "bg-aureus-rule/30 text-aureus-muted border border-aureus-rule",
        institutional: "bg-purple-950/40 text-purple-300 border border-purple-400/30",
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
