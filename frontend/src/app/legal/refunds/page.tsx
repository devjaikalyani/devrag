import type { Metadata } from "next";
import { LegalShell } from "@/components/legal/LegalShell";

export const metadata: Metadata = { title: "Refunds and Cancellation — DevRAG" };

export default function RefundsPage() {
  return (
    <LegalShell title="Refunds and Cancellation" updated="7 July 2026">
      <h2>1. No auto-renewal, nothing to cancel</h2>
      <p>
        DevRAG Pro is a one-time purchase for a fixed period (monthly or yearly). It never
        auto-renews and we store no payment instrument, so there is no subscription to cancel.
        When your period ends, you simply drop back to the Free tier with your data intact.
      </p>

      <h2>2. Seven-day money-back guarantee</h2>
      <p>
        If you are not satisfied with your first DevRAG Pro purchase, write to
        devjaikalyani@gmail.com within 7 days of payment with your Razorpay payment ID and we
        will refund the full amount, no questions asked.
      </p>

      <h2>3. Defects</h2>
      <p>
        If a defect in DevRAG prevents you from using a Pro feature and we cannot fix it within a
        reasonable time, you are entitled to a pro-rata refund of the unused period at any time,
        not just the first 7 days.
      </p>

      <h2>4. How refunds are processed</h2>
      <ul>
        <li>Refunds are issued through Razorpay to the original payment method.</li>
        <li>We initiate the refund within 2 business days of approval; banks typically credit it within 5 to 7 business days.</li>
        <li>The associated Pro entitlement is revoked when the refund is issued.</li>
      </ul>

      <h2>5. Contact</h2>
      <p>
        Refund requests: devjaikalyani@gmail.com with the subject &quot;Refund&quot; and your
        payment ID. See the Contact and Grievance page for escalation.
      </p>
    </LegalShell>
  );
}
