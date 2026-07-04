import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium leading-none",
  {
    variants: {
      variant: {
        default: "bg-[var(--color-accent-dim)] text-[var(--color-accent)]",
        success: "bg-green-500/10 text-green-400",
        warning: "bg-amber-500/10 text-amber-400",
        danger: "bg-red-500/10 text-red-400",
        muted: "bg-white/[0.06] text-white/50",
        outline: "border border-[var(--color-border-strong)] text-white/60",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />;
}
