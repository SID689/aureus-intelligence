import Link from "next/link";
import type { Metadata } from "next";
import LegalDocument, { type LegalSection } from "@/components/site/LegalDocument";
import { LEGAL } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms that govern your use of Aureus Intelligence.",
};

const E = LEGAL.entityName;

const sections: LegalSection[] = [
  {
    id: "agreement",
    title: "Agreement to these Terms",
    content: (
      <>
        <p>
          These Terms of Service (the “Terms”) are a binding agreement between you and {E} (“Aureus”, “we”,
          “us”) governing your access to and use of the {LEGAL.serviceName} website, applications, application
          programming interfaces, alerts and related services (together, the “Service”).
        </p>
        <p>
          By creating an account, subscribing to a plan or otherwise using the Service, you agree to these Terms and
          to our <Link href="/privacy">Privacy Policy</Link>. If you do not agree, do not use the Service.
        </p>
        <p>
          You must be at least 18 years old and able to form a binding contract to use the Service. If you use the
          Service on behalf of an organisation, you represent that you are authorised to accept these Terms for it.
        </p>
      </>
    ),
  },
  {
    id: "service",
    title: "The Service",
    content: (
      <>
        <p>
          The Service provides quantitative equity research tools, including multi-factor scoring of securities,
          written analysis, catalyst calendars, backtesting, portfolio monitoring, market alerts, and financial
          education content and games. Features, usage limits and data sources vary by subscription plan and are
          described on the pricing page at the time you subscribe.
        </p>
        <p>
          We may add, change or remove features. When a change materially reduces what a paid plan includes, we will
          give you notice and the option to cancel before the change takes effect.
        </p>
      </>
    ),
  },
  {
    id: "not-advice",
    title: "Not investment advice",
    content: (
      <>
        <p>
          <strong>
            The Service is published for informational and educational purposes only. It does not provide investment,
            financial, legal, tax or accounting advice, and nothing in it is an offer, solicitation or recommendation to
            buy, sell or hold any security or to adopt any investment strategy.
          </strong>
        </p>
        <ul>
          <li>
            {E} is not registered as an investment adviser with the U.S. Securities and Exchange Commission or any
            state securities regulator, and is not a broker-dealer. We do not execute trades, hold customer funds or
            securities, or have discretion over any account.
          </li>
          <li>
            Scores, ratings and labels such as “Strong Buy”, “Buy”, “Hold” and “Sell”, leaderboard rankings and alerts
            are the automated output of quantitative models applied to third-party data. They are impersonal, are not
            tailored to your financial situation, objectives or risk tolerance, and are not recommendations.
          </li>
          <li>
            No fiduciary, advisory or professional relationship is created by your use of the Service.
          </li>
          <li>
            You are solely responsible for your investment decisions and their results. Before acting, consider
            consulting a licensed professional who knows your circumstances.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "risk",
    title: "Risk disclosures",
    content: (
      <>
        <p>
          Investing in securities involves risk, including the possible loss of your entire investment. Market
          conditions change quickly, and a model that described the past well may describe the future badly.
        </p>
        <h3>Hypothetical and backtested results</h3>
        <p>
          Backtests, simulations, Monte Carlo projections and other hypothetical results are prepared with the benefit
          of hindsight, do not reflect actual trading, and cannot account for every factor that affects real results,
          including liquidity, market impact and the discipline of following a strategy through losses. Hypothetical
          performance has inherent limitations and is not a reliable indicator of future results.
        </p>
        <h3>Model and data risk</h3>
        <p>
          Our models rely on assumptions, calibration choices and third-party data that may be incomplete, delayed,
          revised or wrong. Scores can change materially when inputs are refreshed. Where the Service reports data
          completeness or conviction, those figures describe the model’s inputs, not the probability of any outcome.
        </p>
        <h3>AI-generated text</h3>
        <p>
          Some plans include written analysis produced or edited by large language models. Such text can contain
          factual errors, omissions or unsupported statements, even where it cites figures. Verify anything material
          against primary sources before relying on it.
        </p>
      </>
    ),
  },
  {
    id: "data",
    title: "Market data and third-party content",
    content: (
      <>
        <p>
          Prices, fundamentals, filings, news, social media content and economic calendars are obtained from third
          parties. They are provided as received, may be delayed by up to the period stated for your plan, and are not
          verified by us. Neither Aureus nor its data providers guarantee their accuracy, completeness or timeliness.
        </p>
        <p>
          Market data is licensed for your personal, non-commercial use within the Service. You may not redistribute,
          resell or publish it, or use it to build a competing product.
        </p>
      </>
    ),
  },
  {
    id: "accounts",
    title: "Accounts and security",
    content: (
      <>
        <p>
          You agree to provide accurate registration information and keep it current. You are responsible for keeping
          your credentials and any API keys confidential and for all activity under your account. Accounts are for one
          person and may not be shared. Tell us promptly at <a href={`mailto:${LEGAL.contact.support}`}>{LEGAL.contact.support}</a> if
          you believe your account has been accessed without authorisation.
        </p>
      </>
    ),
  },
  {
    id: "billing",
    title: "Subscriptions, billing and cancellation",
    content: (
      <>
        <ul>
          <li>
            <strong>Plans.</strong> The Service offers a free plan and paid plans billed in advance on a recurring
            monthly basis. Current prices are shown on the pricing page and at checkout.
          </li>
          <li>
            <strong>Automatic renewal.</strong> Paid subscriptions renew automatically at the end of each billing period
            until cancelled. By subscribing, you authorise us and our payment processor, Stripe, to charge your payment
            method each period, plus applicable taxes.
          </li>
          <li>
            <strong>Cancellation.</strong> You may cancel at any time from your account settings. Cancellation takes
            effect at the end of the current billing period, and you keep paid features until then.
          </li>
          <li>
            <strong>Refunds.</strong> Fees are non-refundable, including for partial billing periods and unused usage
            allowances, except where required by applicable law.
          </li>
          <li>
            <strong>Price changes.</strong> We will give you at least 30 days’ notice before a price change applies to
            your subscription. The new price applies from your next billing period after the notice period, and you may
            cancel before it does.
          </li>
          <li>
            <strong>Failed payments.</strong> If a payment fails and is not resolved, we may move your account to the
            free plan.
          </li>
          <li>
            <strong>Credits and allowances.</strong> Monthly analysis credits and usage allowances have no cash value,
            are not transferable, and do not roll over.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "acceptable-use",
    title: "Acceptable use",
    content: (
      <>
        <p>You agree not to:</p>
        <ul>
          <li>copy, scrape, harvest or systematically download scores, analysis, data or content, except through an API key your plan provides and within its limits;</li>
          <li>redistribute, resell, sublicense or publicly display the Service’s output, or present it as your own research;</li>
          <li>reverse engineer, decompile or attempt to extract the Service’s models, weights or source code;</li>
          <li>circumvent usage limits, rate limits, plan restrictions or security controls, or access the Service through automated means other than a provided API;</li>
          <li>use the Service to engage in or facilitate market manipulation, fraud or any unlawful activity;</li>
          <li>upload malicious code, interfere with the Service’s operation, or probe it for vulnerabilities without our written permission;</li>
          <li>impersonate another person or misrepresent your affiliation.</li>
        </ul>
      </>
    ),
  },
  {
    id: "ip",
    title: "Intellectual property",
    content: (
      <>
        <p>
          The Service, including its software, models, scoring methodology, written content, lessons, design and
          trademarks, is owned by {E} or its licensors and is protected by law. Subject to these Terms, we grant you a
          limited, revocable, non-exclusive, non-transferable licence to use the Service for your personal,
          non-commercial purposes during your subscription.
        </p>
        <p>
          You retain ownership of information you enter, such as portfolio holdings. You grant us a licence to host,
          process and display it solely to provide and improve the Service. If you send us feedback, we may use it
          without obligation to you.
        </p>
      </>
    ),
  },
  {
    id: "alerts",
    title: "Alerts and notifications",
    content: (
      <>
        <p>
          Alerts, including leaderboard alerts delivered in the application or as browser push notifications, depend on
          data providers, scheduled processing, your browser and third-party push services. They may be delayed,
          duplicated or not delivered. Do not rely on an alert arriving, or arriving on time, for any decision. You can
          turn push notifications off at any time.
        </p>
      </>
    ),
  },
  {
    id: "education",
    title: "Education and games",
    content: (
      <p>
        Lessons, quizzes, practice problems and games are general education. Experience points, badges and game
        results have no monetary value and are not an assessment of your competence to invest.
      </p>
    ),
  },
  {
    id: "third-parties",
    title: "Third-party services",
    content: (
      <p>
        The Service links to and integrates with services operated by others, including sign-in with Google and
        payment processing by Stripe. Your use of those services is governed by their own terms, and we are not
        responsible for them.
      </p>
    ),
  },
  {
    id: "warranties",
    title: "Disclaimer of warranties",
    content: (
      <p className="clause-caps">
        The Service and all data, scores, analysis and content are provided “as is” and “as available”. To the fullest
        extent permitted by law, {E} disclaims all warranties, express or implied, including warranties of
        merchantability, fitness for a particular purpose, accuracy, non-infringement, and uninterrupted or error-free
        operation.
      </p>
    ),
  },
  {
    id: "liability",
    title: "Limitation of liability",
    content: (
      <>
        <p className="clause-caps">
          To the fullest extent permitted by law, {E} and its officers, employees, licensors and data providers will not
          be liable for any indirect, incidental, special, consequential, exemplary or punitive damages, or for any loss
          of profits, trading losses, investment losses, lost data or loss of goodwill, arising from or relating to the
          Service, whether in contract, tort or otherwise, even if advised of the possibility of such damages.
        </p>
        <p className="clause-caps">
          Our total liability for all claims relating to the Service is limited to the greater of the amounts you paid
          us in the twelve months before the event giving rise to the claim, or one hundred U.S. dollars.
        </p>
        <p>
          Some jurisdictions do not allow certain limitations, so some of the above may not apply to you. Nothing in these
          Terms limits liability that cannot be limited by law.
        </p>
      </>
    ),
  },
  {
    id: "indemnity",
    title: "Indemnification",
    content: (
      <p>
        You agree to indemnify and hold harmless {E} and its officers and employees from claims, losses and expenses,
        including reasonable legal fees, arising from your misuse of the Service, your violation of these Terms, or your
        violation of any law or the rights of a third party.
      </p>
    ),
  },
  {
    id: "termination",
    title: "Suspension and termination",
    content: (
      <p>
        You may stop using the Service and close your account at any time. We may suspend or terminate your access if
        you breach these Terms, if required by law, or to protect the Service or other users. Sections that by their
        nature should survive termination, including those on advice, risk, intellectual property, disclaimers,
        liability, indemnification and disputes, will survive.
      </p>
    ),
  },
  {
    id: "disputes",
    title: "Disputes, arbitration and class action waiver",
    content: (
      <>
        <p>
          These Terms are governed by the laws of {LEGAL.governingLaw}, without regard to conflict of laws principles.
        </p>
        <p>
          <strong>
            Except for claims that qualify for small claims court, any dispute arising from these Terms or the Service
            will be resolved by final and binding individual arbitration administered by the American Arbitration
            Association under its Consumer Arbitration Rules, seated in {LEGAL.arbitrationSeat}. You and {E} each waive
            the right to a jury trial and to participate in a class action or class-wide arbitration.
          </strong>
        </p>
        <p>
          You may opt out of this arbitration agreement by emailing <a href={`mailto:${LEGAL.contact.legal}`}>{LEGAL.contact.legal}</a> within
          30 days of first accepting these Terms. Either party may seek injunctive relief in court to protect
          intellectual property rights.
        </p>
      </>
    ),
  },
  {
    id: "changes",
    title: "Changes to these Terms",
    content: (
      <p>
        We may update these Terms. We will post the revised Terms with a new “Last updated” date and, for material
        changes, notify you by email or in the Service at least 30 days before they take effect. Continuing to use the
        Service after the effective date means you accept the revised Terms.
      </p>
    ),
  },
  {
    id: "general",
    title: "General",
    content: (
      <p>
        These Terms and the Privacy Policy are the entire agreement between you and {E} about the Service. If any
        provision is unenforceable, the rest remains in effect. Our failure to enforce a provision is not a waiver. You
        may not assign these Terms without our consent; we may assign them in connection with a merger, acquisition or
        sale of assets. Neither party is liable for delays caused by events beyond its reasonable control.
      </p>
    ),
  },
  {
    id: "contact",
    title: "Contact",
    content: (
      <p>
        {E}, {LEGAL.entityAddress}. Questions about these Terms: <a href={`mailto:${LEGAL.contact.legal}`}>{LEGAL.contact.legal}</a>.
      </p>
    ),
  },
];

export default function TermsPage() {
  return (
    <LegalDocument
      title="Terms of Service"
      summary={
        <p>
          <strong>In short.</strong> Aureus publishes model-driven research and education. It is not investment advice,
          we are not your adviser or broker, and every score can be wrong. Paid plans renew monthly until you cancel,
          and cancellation takes effect at the end of the period. Disputes go to individual arbitration unless you opt
          out within 30 days. This summary is for convenience; the full Terms below govern.
        </p>
      }
      sections={sections}
    />
  );
}
