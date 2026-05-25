import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { clsx } from "clsx";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  asChild?: boolean;
  variant?: "default" | "outline";
  size?: "default" | "lg";
};

export function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={clsx(
        "inline-flex items-center justify-center font-semibold transition disabled:pointer-events-none disabled:opacity-50",
        size === "lg" ? "h-12 px-6 text-base" : "h-10 px-4 text-sm",
        variant === "outline"
          ? "border bg-transparent"
          : "bg-white text-black hover:bg-white/90",
        className
      )}
      {...props}
    />
  );
}
