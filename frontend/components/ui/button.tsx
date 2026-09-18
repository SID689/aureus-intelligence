import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Gold is the only fill that means "act". Everything else is an outline
 * or a ghost, so a page never has two things competing to be the primary
 * action — if two buttons are both gold, neither is the answer.
 *
 * `subtle` is the workhorse for secondary actions inside a sheet, where
 * an outline against the sheet's own border reads as a double rule.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 rounded-md font-medium tracking-wide " +
    "transition-colors duration-150 disabled:opacity-40 disabled:pointer-events-none whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "bg-aureus-gold text-aureus-ink hover:bg-aureus-goldbright",
        outline: "border border-aureus-rulestrong text-aureus-text hover:border-aureus-gold hover:text-aureus-gold",
        subtle:  "bg-aureus-panellift text-aureus-soft hover:bg-aureus-panelhigh hover:text-aureus-text",
        ghost:   "text-aureus-muted hover:text-aureus-text hover:bg-aureus-panellift",
        danger:  "border border-aureus-crimsondim text-aureus-crimson hover:bg-aureus-crimson/10 hover:border-aureus-crimson",
        success: "bg-aureus-emerald text-aureus-ink hover:bg-aureus-emeraldbright",
      },
      // Heights below 44px are fine under a mouse and hard to hit with a
      // thumb, so the two small sizes grow on coarse pointers only. The
      // `touch:` variant is defined in tailwind.config.ts as
      // (pointer: coarse); desktop layout is untouched.
      size: {
        default: "h-9 touch:h-11 px-4 text-sm",
        sm:      "h-7 touch:h-10 px-3 text-xs",
        lg:      "h-11 px-6 text-[15px]",
        icon:    "h-9 w-9 touch:h-11 touch:w-11",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
