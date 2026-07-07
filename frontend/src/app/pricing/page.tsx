"use client";
import { useCallback, useEffect, useState } from "react";
import { Check, Sparkles, Zap } from "lucide-react";
import { toast } from "sonner";
import { Topbar } from "@/components/layout/Topbar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  createOrder,
  getBillingPlans,
  getBillingStatus,
  verifyPayment,
  type BillingPlans,
  type BillingStatus,
} from "@/lib/api";

type Currency = "INR" | "USD";
type Package = "pro_monthly" | "pro_yearly";

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

function formatAmount(amount: number, currency: Currency): string {
  const value = amount / 100;
  return currency === "INR" ? `Rs ${value.toLocaleString("en-IN")}` : `$${value.toFixed(2)}`;
}

export default function PricingPage() {
  const [plans, setPlans] = useState<BillingPlans | null>(null);
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [currency, setCurrency] = useState<Currency>("INR");
  const [pkg, setPkg] = useState<Package>("pro_monthly");
  const [paying, setPaying] = useState(false);

  const refresh = useCallback(() => {
    getBillingPlans().then(setPlans).catch(() => {});
    getBillingStatus().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const isPro = status?.tier === "pro";
  const selected = plans?.packages[pkg];
  const amount = selected?.prices[currency] ?? 0;
  const perMonth = pkg === "pro_yearly" ? amount / 12 : amount;

  const handleUpgrade = async () => {
    if (paying) return;
    setPaying(true);
    try {
      const ok = await loadRazorpayScript();
      if (!ok) {
        toast.error("Could not load Razorpay checkout. Check your connection.");
        return;
      }
      const order = await createOrder(pkg, currency);
      const rzp = new window.Razorpay!({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: order.name,
        description: order.description,
        order_id: order.order_id,
        theme: { color: "#7C5CFF" },
        handler: async (response: {
          razorpay_order_id: string;
          razorpay_payment_id: string;
          razorpay_signature: string;
        }) => {
          try {
            const result = await verifyPayment({ ...response, package: pkg, currency });
            toast.success(`DevRAG Pro active until ${result.expires_at.slice(0, 10)}`);
            refresh();
          } catch {
            toast.error("Payment verification failed. Contact support with your payment ID.");
          }
        },
      });
      rzp.open();
    } catch {
      // createOrder already surfaced the toast (e.g. Razorpay keys not configured)
    } finally {
      setPaying(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--color-bg)] overflow-y-auto">
      <Topbar />

      <div className="flex-1 px-6 py-10 max-w-4xl mx-auto w-full">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-white tracking-tight">
            One automated fix pays for the month
          </h1>
          <p className="mt-2 text-sm text-white/40 max-w-lg mx-auto">
            Chat with any codebase free, forever. Go Pro when you want the agent
            shipping tested pull requests without limits.
          </p>

          {/* Currency + period toggles */}
          <div className="mt-6 flex items-center justify-center gap-3">
            <div className="flex rounded border border-border overflow-hidden text-xs font-mono">
              {(["INR", "USD"] as Currency[]).map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCurrency(c)}
                  className={cn(
                    "px-3 py-1.5 transition-colors",
                    currency === c ? "bg-accent-dim text-accent" : "text-white/40 hover:text-white/70"
                  )}
                >
                  {c === "INR" ? "INR (India)" : "USD (International)"}
                </button>
              ))}
            </div>
            <div className="flex rounded border border-border overflow-hidden text-xs font-mono">
              {([["pro_monthly", "Monthly"], ["pro_yearly", "Yearly"]] as [Package, string][]).map(([p, label]) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPkg(p)}
                  className={cn(
                    "px-3 py-1.5 transition-colors",
                    pkg === p ? "bg-accent-dim text-accent" : "text-white/40 hover:text-white/70"
                  )}
                >
                  {label}
                  {p === "pro_yearly" && <span className="ml-1 text-emerald-400">-16%</span>}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-5">
          {/* Free */}
          <div className="rounded-lg border border-border p-6 flex flex-col">
            <div className="flex items-center gap-2">
              <Zap size={15} className="text-white/40" />
              <span className="text-sm font-semibold text-white">Free</span>
              {!isPro && status && (
                <Badge variant="outline" className="ml-auto text-[10px] font-mono">current plan</Badge>
              )}
            </div>
            <div className="mt-3 text-2xl font-semibold text-white">
              {currency === "INR" ? "Rs 0" : "$0"}
              <span className="text-xs text-white/30 font-normal ml-1">forever</span>
            </div>
            <ul className="mt-5 space-y-2.5 text-xs text-white/55 flex-1">
              {(plans?.tiers.free.features ?? []).map((f) => (
                <li key={f} className="flex gap-2">
                  <Check size={13} className="text-white/25 shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            {!isPro && status?.remaining && (
              <div className="mt-4 pt-4 border-t border-white/[0.06] text-[11px] text-white/35 font-mono space-y-1">
                <div>{status.remaining.queries_today} queries left today</div>
                <div>{status.remaining.runs_this_month} agent runs left this month</div>
              </div>
            )}
          </div>

          {/* Pro */}
          <div className="rounded-lg border border-accent/40 bg-accent-dim/30 p-6 flex flex-col relative">
            <div className="flex items-center gap-2">
              <Sparkles size={15} className="text-accent" />
              <span className="text-sm font-semibold text-white">Pro</span>
              {isPro ? (
                <Badge variant="outline" className="ml-auto text-[10px] font-mono border-accent/40 text-accent">
                  active{status?.expires_at ? ` until ${status.expires_at.slice(0, 10)}` : ""}
                </Badge>
              ) : (
                <Badge variant="outline" className="ml-auto text-[10px] font-mono border-accent/40 text-accent">
                  recommended
                </Badge>
              )}
            </div>
            <div className="mt-3 text-2xl font-semibold text-white">
              {selected ? formatAmount(perMonth, currency) : "—"}
              <span className="text-xs text-white/30 font-normal ml-1">/month</span>
              {pkg === "pro_yearly" && selected && (
                <span className="block text-[11px] text-white/35 font-normal mt-0.5">
                  billed {formatAmount(amount, currency)} yearly
                </span>
              )}
            </div>
            <ul className="mt-5 space-y-2.5 text-xs text-white/70 flex-1">
              {(plans?.tiers.pro.features ?? []).map((f) => (
                <li key={f} className="flex gap-2">
                  <Check size={13} className="text-accent shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            <Button
              onClick={handleUpgrade}
              disabled={paying || isPro}
              className="mt-5 w-full"
              size="md"
            >
              {isPro ? "Pro is active" : paying ? "Opening checkout..." : `Upgrade — ${selected ? formatAmount(amount, currency) : ""}`}
            </Button>
            <p className="mt-3 text-center text-[10px] text-white/25">
              Secured by Razorpay. UPI, cards and netbanking in India; international cards in USD.
              Prices are inclusive of all applicable taxes.
            </p>
          </div>
        </div>

        <p className="mt-8 text-center text-[11px] text-white/25 max-w-md mx-auto">
          You bring your own LLM API keys on both tiers; DevRAG never marks up model usage.
          One-time purchase per period, no auto-renewal. Seven-day money-back guarantee on your
          first purchase.
        </p>

        <nav className="mt-6 flex flex-wrap justify-center gap-4 text-[11px] font-mono text-white/30">
          <a href="/legal/terms" className="hover:text-white/70">Terms of Service</a>
          <a href="/legal/privacy" className="hover:text-white/70">Privacy Policy</a>
          <a href="/legal/refunds" className="hover:text-white/70">Refunds</a>
          <a href="/legal/contact" className="hover:text-white/70">Contact and Grievance</a>
        </nav>
      </div>
    </div>
  );
}
