import type { Metadata } from "next";
import { LegalShell } from "@/components/legal/LegalShell";

export const metadata: Metadata = { title: "Contact and Grievance — DevRAG" };

export default function ContactPage() {
  return (
    <LegalShell title="Contact and Grievance Redressal" updated="7 July 2026">
      <h2>Business identity</h2>
      <ul>
        <li>Product: DevRAG</li>
        <li>Operator: Dev Jaikalyani (sole proprietor)</li>
        <li>Location: Nagpur, Maharashtra, India</li>
        <li>Email: devjaikalyani@gmail.com</li>
      </ul>

      <h2>Support</h2>
      <p>
        For product questions, bug reports, and billing support, email devjaikalyani@gmail.com or
        open an issue on the GitHub repository. We aim to respond within 2 business days.
      </p>

      <h2>Grievance redressal</h2>
      <p>
        In accordance with the Consumer Protection (E-Commerce) Rules, 2020 and the Information
        Technology Act, 2000:
      </p>
      <ul>
        <li>Grievance Officer: Dev Jaikalyani</li>
        <li>Email: devjaikalyani@gmail.com (subject line &quot;Grievance&quot;)</li>
        <li>Acknowledgement: within 48 hours of receipt</li>
        <li>Resolution: within 30 days of receipt</li>
      </ul>

      <h2>Data protection requests</h2>
      <p>
        Requests under the Digital Personal Data Protection Act, 2023 or the GDPR are handled
        through the same contact; see the Privacy Policy for details.
      </p>
    </LegalShell>
  );
}
