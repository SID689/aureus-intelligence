import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * A card is a raised sheet: warm panel surface, hairline border, a gold
 * top edge and a soft cast shadow, so the page reads as physical layers
 * rather than outlined rectangles on a flat plane.
 *
 * Prefer `RuledLabel` from ui/primitives when the content isn't really a
 * discrete object — a heading with a hairline to the edge divides space
 * without adding another border to the page. Reserve Card for things that
 * genuinely are objects: a table, a chart, a panel of controls.
 */
const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { accent?: boolean; flat?: boolean }
>(({ className, accent, flat, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-[10px] border border-aureus-rule bg-aureus-panel",
      !flat && "border-t-aureus-golddim shadow-lift",
      accent && "guilloche-corner",
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
