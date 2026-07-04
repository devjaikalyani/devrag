"use client";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: TooltipPrimitive.TooltipContentProps) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          "z-50 max-w-xs rounded-md border border-[var(--color-border-strong)] bg-[var(--color-bg-overlay)] px-2.5 py-1.5 text-[11px] text-white/80 shadow-xl",
          "data-[state=delayed-open]:data-[side=bottom]:animate-slideUpAndFade",
          "data-[state=delayed-open]:data-[side=top]:animate-slideDownAndFade",
          className
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  );
}
