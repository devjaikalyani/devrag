import type { Metadata } from "next";
import { LegalShell } from "@/components/legal/LegalShell";

export const metadata: Metadata = { title: "Privacy Policy — DevRAG" };

export default function PrivacyPage() {
  return (
    <LegalShell title="Privacy Policy" updated="7 July 2026">
      <p>
        DevRAG is self-hosted software. This policy explains what data the software touches, what
        little we (Dev Jaikalyani, Nagpur, Maharashtra, India) receive, and your rights under the
        Digital Personal Data Protection Act, 2023 (India) and, where applicable, the GDPR.
      </p>

      <h2>1. Your code stays on your machine</h2>
      <ul>
        <li>Repositories you index, chat history, indexes, and agent run records are stored locally on your computer. We have no access to them.</li>
        <li>When you ask a question or run the agent, relevant code snippets are sent to the LLM provider whose API key you configured (such as Anthropic, Groq, or Mistral). That transfer happens directly from your machine under your own account with that provider, governed by their privacy terms.</li>
        <li>DevRAG contains no telemetry, analytics, or tracking. It phones home to no one.</li>
      </ul>

      <h2>2. What we receive when you buy Pro</h2>
      <ul>
        <li>Payments are processed by Razorpay Software Pvt. Ltd. Razorpay collects the payment details (card, UPI, or bank information) under its own privacy policy and PCI-DSS obligations; we never see or store them.</li>
        <li>We receive from Razorpay: your name and email or phone as provided at checkout, the amount, currency, and payment identifiers. We use these solely to activate your license, provide support, and meet tax and accounting obligations.</li>
        <li>Your Pro entitlement (package, expiry, payment identifiers) is stored locally on your machine.</li>
      </ul>

      <h2>3. Retention and sharing</h2>
      <p>
        Payment records are retained as long as Indian tax law requires, then deleted. We do not
        sell or share personal data with anyone except Razorpay (as payment processor) and
        authorities where legally required.
      </p>

      <h2>4. Your rights</h2>
      <p>
        You may request access to, correction of, or deletion of the personal data we hold about
        you, or raise a complaint, by writing to devjaikalyani@gmail.com. We respond within the
        timelines of the DPDP Act, 2023. EU/UK residents may additionally exercise their GDPR
        rights through the same contact.
      </p>

      <h2>5. Contact</h2>
      <p>
        Data requests and privacy questions: devjaikalyani@gmail.com. See the Contact and
        Grievance page for the grievance process.
      </p>
    </LegalShell>
  );
}
