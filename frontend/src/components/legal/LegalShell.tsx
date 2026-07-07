import { Topbar } from "@/components/layout/Topbar";

export function LegalShell({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col h-full bg-[var(--color-bg)] overflow-y-auto">
      <Topbar />
      <div className="flex-1 px-6 py-10 max-w-2xl mx-auto w-full">
        <h1 className="text-xl font-semibold text-white tracking-tight">{title}</h1>
        <p className="mt-1 text-[11px] text-white/30 font-mono">Last updated: {updated}</p>
        <div className="mt-6 space-y-5 text-[13px] leading-relaxed text-white/60 [&_h2]:text-white/85 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-7 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1.5 [&_a]:text-accent [&_a]:underline-offset-2 hover:[&_a]:underline">
          {children}
        </div>
        <nav className="mt-10 pt-5 border-t border-white/[0.06] flex flex-wrap gap-4 text-[11px] font-mono text-white/35">
          <a href="/legal/terms" className="hover:text-white/70">Terms of Service</a>
          <a href="/legal/privacy" className="hover:text-white/70">Privacy Policy</a>
          <a href="/legal/refunds" className="hover:text-white/70">Refunds and Cancellation</a>
          <a href="/legal/contact" className="hover:text-white/70">Contact and Grievance</a>
          <a href="/pricing" className="hover:text-white/70">Pricing</a>
        </nav>
      </div>
    </div>
  );
}
