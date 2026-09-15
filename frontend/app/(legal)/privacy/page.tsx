import Link from "next/link";
import type { Metadata } from "next";
import LegalDocument, { type LegalSection } from "@/components/site/LegalDocument";
import { LEGAL } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What Aureus Intelligence collects, why, who it is shared with, and your choices.",
};

const E = LEGAL.entityName;
const mail = (addr: string) => <a href={`mailto:${addr}`}>{addr}</a>;

const sections: LegalSection[] = [
  {
    id: "scope",
    title: "Scope",
    content: (
      <p>
        This Privacy Policy explains how {E} (“Aureus”, “we”, “us”) collects, uses and shares personal information when
        you use the {LEGAL.serviceName} website, applications and related services (the “Service”). It should be read
        with our <Link href="/terms">Terms of Service</Link>.
      </p>
    ),
  },
  {
    id: "collect",
    title: "Information we collect",
    content: (
      <>
        <h3>Information you give us</h3>
        <ul>
          <li><strong>Account details:</strong> your name, email address and password. Passwords are stored only as a salted one-way hash.</li>
          <li><strong>Google sign-in:</strong> if you choose it, the name, email address and account identifier Google shares with us.</li>
          <li><strong>Onboarding responses:</strong> your answers to the introductory questions and a record of your acknowledgement of our risk disclosures, with its date.</li>
          <li><strong>Portfolio information:</strong> holdings, quantities and cost basis you enter. We do not connect to your brokerage accounts.</li>
          <li><strong>Voice sessions:</strong> the text of questions you ask the voice assistant and its responses.</li>
          <li><strong>Communications:</strong> messages you send to support or legal.</li>
        </ul>
        <h3>Information created as you use the Service</h3>
        <ul>
          <li><strong>Usage records:</strong> analyses you run, the tickers and horizons you request, backtests, credit consumption and plan usage counters.</li>
          <li><strong>Learning and games:</strong> lesson progress, quiz and practice results, experience points, badges and game statistics.</li>
          <li><strong>Alerts:</strong> the alerts sent to you and whether you have read them. If you enable browser push notifications, the push subscription endpoint and encryption keys your browser generates.</li>
          <li><strong>Technical data:</strong> IP address, browser type and request logs, used for security, rate limiting and diagnosing faults.</li>
        </ul>
        <h3>Payment information</h3>
        <p>
          Payments are processed by Stripe. Your card number is entered directly with Stripe and never reaches our
          servers. We receive and store a Stripe customer identifier, your plan, subscription status and billing dates.
        </p>
        <h3>Cookies</h3>
        <p>
          We use only strictly necessary cookies, which keep you signed in and protect sign-in forms against forgery. We do
          not use advertising cookies, cross-site tracking or third-party analytics.
        </p>
      </>
    ),
  },
  {
    id: "use",
    title: "How we use information",
    content: (
      <ul>
        <li>to provide the Service: run analyses, maintain your portfolio and learning progress, and deliver alerts you enable;</li>
        <li>to operate subscriptions: process payments, apply plan limits and credits, and send service and billing notices;</li>
        <li>to secure the Service: authenticate you, prevent abuse and fraud, and enforce rate limits and our Terms;</li>
        <li>to improve the Service, using aggregated or de-identified usage information;</li>
        <li>to comply with legal obligations and respond to lawful requests.</li>
      </ul>
    ),
  },
  {
    id: "ai",
    title: "AI processing",
    content: (
      <>
        <p>
          Plans that include written synthesis send the analysis context for a security (its metrics, scores and
          catalyst data) to Anthropic to generate or edit text. This context does not include your name or email.
        </p>
        <p>
          The voice assistant sends the text of your questions, and portfolio context you choose to discuss, to a language
          model provider to generate a response. If voice transcription runs on our servers rather than in your browser,
          the audio of your question is sent to OpenAI for transcription. In browser transcription mode, your browser’s
          speech service processes the audio under your browser vendor’s terms.
        </p>
        <p>These providers process the content to return a result to us, under their API terms.</p>
      </>
    ),
  },
  {
    id: "share",
    title: "How we share information",
    content: (
      <>
        <p><strong>We do not sell your personal information, and we do not share it for cross-context behavioural advertising.</strong></p>
        <p>We share personal information only with:</p>
        <ul>
          <li><strong>Service providers</strong> acting on our instructions: Stripe (payments), Anthropic and OpenAI (AI features described above), Google (if you use Google sign-in), and our hosting and infrastructure providers.</li>
          <li><strong>Browser push services</strong> operated by Google, Mozilla, Apple or Microsoft, depending on your browser, which relay push notifications. Notification content is encrypted end to end between our servers and your browser.</li>
          <li><strong>Authorities</strong> when required by law, or to protect the rights, property or safety of Aureus, our users or others.</li>
          <li><strong>A successor</strong> in a merger, acquisition or sale of assets, subject to this Policy.</li>
        </ul>
        <p>
          Market data providers receive the ticker symbols our systems request. They do not receive information that
          identifies you.
        </p>
      </>
    ),
  },
  {
    id: "retention",
    title: "Retention",
    content: (
      <p>
        We keep personal information while your account is open. When you ask us to delete your account, we delete or
        de-identify your personal information within 30 days, except records we must keep to meet legal, tax, accounting
        or fraud-prevention obligations, such as billing records, which we keep only for the period the law requires.
        Security logs are kept for a limited period and then deleted.
      </p>
    ),
  },
  {
    id: "security",
    title: "Security",
    content: (
      <p>
        We use administrative, technical and physical safeguards appropriate to the information we hold, including
        encryption in transit, hashed passwords, short-lived signed tokens for real-time features, and access controls.
        No system is perfectly secure, and we cannot guarantee the security of information transmitted over the internet.
      </p>
    ),
  },
  {
    id: "rights",
    title: "Your rights and choices",
    content: (
      <>
        <ul>
          <li><strong>Access, correction and deletion.</strong> You may ask for a copy of your personal information, ask us to correct it, or ask us to delete it.</li>
          <li><strong>Portability.</strong> You may ask for your information in a structured, machine-readable format.</li>
          <li><strong>Notifications.</strong> You can turn browser push notifications off at any time in the Service or in your browser settings.</li>
          <li><strong>Withdrawing consent.</strong> Where we rely on your consent, you may withdraw it at any time without affecting earlier processing.</li>
        </ul>
        <h3>California residents</h3>
        <p>
          Under the California Consumer Privacy Act, as amended, you have the rights to know, delete, correct and limit
          the use of sensitive personal information, and the right not to be discriminated against for exercising them.
          We do not sell or share personal information as those terms are defined. We honour Global Privacy Control
          signals as a request to opt out of sale or sharing.
        </p>
        <h3>European Economic Area and United Kingdom</h3>
        <p>
          We process personal information to perform our contract with you, to pursue legitimate interests such as
          securing the Service, to comply with legal obligations, and, where required, with your consent. You may object
          to processing or ask us to restrict it, and you may complain to your local data protection authority.
        </p>
        <p>
          To exercise any right, email {mail(LEGAL.contact.privacy)} from the address on your account. We will verify your
          request and respond within the time the law requires.
        </p>
      </>
    ),
  },
  {
    id: "transfers",
    title: "International transfers",
    content: (
      <p>
        We and our service providers may process information in the United States and other countries whose data
        protection laws differ from yours. Where required, we rely on appropriate safeguards such as standard contractual
        clauses.
      </p>
    ),
  },
  {
    id: "children",
    title: "Children",
    content: (
      <p>
        The Service is not directed to anyone under 18, and we do not knowingly collect personal information from
        children. If you believe a child has given us personal information, contact {mail(LEGAL.contact.privacy)} and we
        will delete it.
      </p>
    ),
  },
  {
    id: "changes",
    title: "Changes to this Policy",
    content: (
      <p>
        We will post any update here with a new “Last updated” date and, for material changes, notify you by email or in
        the Service before they take effect.
      </p>
    ),
  },
  {
    id: "contact",
    title: "Contact",
    content: (
      <p>
        {E}, {LEGAL.entityAddress}. Privacy questions and requests: {mail(LEGAL.contact.privacy)}.
      </p>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <LegalDocument
      title="Privacy Policy"
      summary={
        <p>
          <strong>In short.</strong> We collect what the Service needs to run your account, analyses, portfolio,
          learning and alerts. Stripe handles your card. We use only strictly necessary cookies, run no third-party
          analytics, and never sell your information. AI features send security data, and voice questions you ask, to
          model providers. Email {LEGAL.contact.privacy} to access or delete your data.
        </p>
      }
      sections={sections}
    />
  );
}
