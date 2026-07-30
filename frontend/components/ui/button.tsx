import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium tracking-wide transition-colors duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-aureus-gold disabled:opacity-40 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        default: "bg-aureus-gold text-aureus-ink hover:bg-aureus-goldbright",
        outline: "border border-aureus-rule text-aureus-text hover:border-aureus-gold hover:text-aureus-gold",
        ghost:   "text-aureus-muted hover:text-aureus-text",
        danger:  "border border-aureus-oxblood text-aureus-oxblood hover:bg-aureus-oxblood/10",
        success: "bg-aureus-verdigris text-aureus-ink hover:opacity-90",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm:      "h-7 px-3 text-xs",
        lg:      "h-11 px-6",
        icon:    "h-9 w-9",
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
