import * as React from "react";
import { cn } from "@/lib/utils";

// A card carries a hairline bronze-grey border rather than a heavy stroke,
// and a barely-lifted panel tone rather than a flat surface color — the
// idea is a page of a ledger sitting slightly above the desk, not a
// generic "dashboard tile."
const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { accent?: boolean }>(
  ({ className, accent, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border border-aureus-rule",
        accent && "guilloche-corner",
        className
      )}
      style={{ background: "var(--panel)" }}
      {...props}
    />
  )
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col space-y-1 p-4 border-b border-aureus-rule/60", className)} {...props} />
  )
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-xs font-medium text-aureus-muted uppercase tracking-wider", className)} {...props} />
  )
);
CardTitle.displayName = "CardTitle";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-4", className)} {...props} />
  )
);
CardContent.displayName = "CardContent";

export { Card, CardHeader, CardTitle, CardContent };
