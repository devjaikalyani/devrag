import { cn } from "@/lib/utils";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-white/[0.06]",
        className
      )}
      {...props}
    />
  );
}

export function MessageSkeleton() {
  return (
    <div className="space-y-2 py-4 px-4">
      <Skeleton className="h-3 w-3/4" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-5/6" />
      <Skeleton className="h-3 w-1/2 mt-1" />
    </div>
  );
}

export function SourceCardSkeleton() {
  return (
    <div className="p-3 space-y-2 border-b border-[var(--color-border)]">
      <Skeleton className="h-3 w-2/3" />
      <Skeleton className="h-2 w-1/3" />
      <Skeleton className="h-8 w-full mt-2" />
    </div>
  );
}

export function RepoItemSkeleton() {
  return (
    <div className="px-3 py-2.5 flex items-center gap-2">
      <Skeleton className="h-4 w-4 rounded-sm shrink-0" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-2 w-16" />
      </div>
    </div>
  );
}
