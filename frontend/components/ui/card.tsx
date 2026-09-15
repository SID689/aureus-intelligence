import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * A card is a sheet: panel surface and a hairline, with a gold top rule
 * when it is the primary object on the page. It separates from the ground
 * by luminance, never by a cast shadow.
 *
 * Prefer `RuledLabel` from ui/primitives when the content is not really a
 * discrete object. Reserve Card for tables, charts and control panels.
 */
const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { accent?: boolean; flat?: boolean }
>(({ className, accent, flat, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-sm border border-aureus-rule bg-aureus-panel",
      !flat && "border-t-aureus-golddim",
      accent && "border-t-aureus-gold",
      className
    )}
    {...props}
  />
));
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex flex-col space-y-1 px-5 py-3.5 border-b border-aureus-rule", className)}
      {...props}
    />
  )
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("label-caps", className)} {...props} />
  )
);
CardTitle.displayName = "CardTitle";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-5", className)} {...props} />
  )
);
CardContent.displayName = "CardContent";

export { Card, CardHeader, CardTitle, CardContent };
