import type { Metadata } from "next";
import { LegalShell } from "@/components/legal/LegalShell";

export const metadata: Metadata = { title: "Terms of Service — DevRAG" };

export default function TermsPage() {
  return (
    <LegalShell title="Terms of Service" updated="7 July 2026">
      <p>
        DevRAG is operated by Dev Jaikalyani, sole proprietor, Nagpur, Maharashtra, India
        (&quot;we&quot;, &quot;us&quot;). By downloading, installing, or purchasing DevRAG you agree to
        these terms.
      </p>

      <h2>1. The service</h2>
      <p>
        DevRAG is self-hosted developer software: it indexes source code repositories you choose,
        answers questions about them, and can run an autonomous agent that proposes code changes
        and pull requests. The software runs on your own machine. You supply and pay for your own
        LLM provider API keys (such as Anthropic, Groq, or Mistral); your use of those providers
        is governed by their terms, not ours, and we never resell or mark up model usage.
      </p>

      <h2>2. License</h2>
      <p>
        The DevRAG source code is licensed under the Elastic License 2.0, included in the
        repository as the LICENSE file. In short: you may use, modify, and self-host DevRAG
        freely, but you may not offer it to third parties as a hosted or managed service, and you
        may not circumvent the license or entitlement functionality.
      </p>

      <h2>3. Free and Pro tiers</h2>
      <ul>
        <li>The Free tier is available at no charge with the usage limits published on the Pricing page.</li>
        <li>Pro is a one-time purchase per period (monthly or yearly). There is no auto-renewal; buying again extends your current expiry.</li>
        <li>Prices shown on the Pricing page are inclusive of all applicable taxes.</li>
        <li>Payments are processed by Razorpay. We do not store your card, UPI, or banking details.</li>
      </ul>

      <h2>4. Acceptable use</h2>
      <ul>
        <li>Run the agent&apos;s pull-request mode only against repositories you own or have permission to contribute to. Unsolicited automated pull requests to third-party repositories violate GitHub&apos;s Acceptable Use Policies and these terms.</li>
        <li>Review agent-generated changes before merging. DevRAG proposes changes; you are responsible for what you merge and ship.</li>
        <li>Do not use DevRAG to develop or deploy malicious software.</li>
      </ul>

      <h2>5. Warranties and liability</h2>
      <p>
        DevRAG is provided as is, without warranties of any kind. AI-generated answers and code
        changes may be incorrect; verify them before relying on them. To the maximum extent
        permitted by law, our total liability arising out of these terms or the software is
        limited to the amount you paid us in the twelve months preceding the claim.
      </p>

      <h2>6. Governing law</h2>
      <p>
        These terms are governed by the laws of India. Courts at Nagpur, Maharashtra have
        exclusive jurisdiction, subject to any non-waivable consumer-protection rights.
      </p>

      <h2>7. Changes</h2>
      <p>
        We may update these terms; material changes will be noted by the date above. Continued
        use after a change constitutes acceptance.
      </p>
    </LegalShell>
  );
}
