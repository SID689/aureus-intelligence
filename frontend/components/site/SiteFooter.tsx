import Link from "next/link";
import Logo from "@/components/brand/Logo";
import { LEGAL } from "@/lib/legal";

/**
 * The footer for every public page. The legal links live here and in the
 * dashboard sidebar, so the Terms and the Privacy Policy are one click from
 * anywhere a person can arrive.
 */
export default function SiteFooter({ variant = "full" }: { variant?: "full" | "compact" }) {
  const year = new Date().getFullYear();

  if (variant === "compact") {
    return (
      <footer className="border-t border-aureus-rule">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 text-[11.5px] text-aureus-muted">
          <span>© {year} {LEGAL.serviceName}. Informational research only; not investment advice.</span>
          <nav className="flex gap-5" aria-label="Legal">
            <Link href="/terms" className="hover:text-aureus-text">Terms of Service</Link>
            <Link href="/privacy" className="hover:text-aureus-text">Privacy Policy</Link>
          </nav>
        </div>
      </footer>
    );
  }

  return (
    <footer className="border-t border-aureus-rule bg-aureus-panel">
      <div className="max-w-6xl mx-auto px-5 sm:px-8 pt-12 pb-8">
        <div className="grid gap-y-10 gap-x-12 md:grid-cols-[minmax(0,1.6fr)_minmax(0,0.7fr)_minmax(0,0.7fr)]">
          <div className="max-w-md">
            <Logo size={26} withWordmark wordmarkClassName="text-base" />
            <p className="text-[12.5px] text-aureus-muted leading-relaxed mt-5">
              {LEGAL.serviceName} publishes quantitative research and education. It is not a registered
              investment adviser or broker-dealer, and nothing on this site is a recommendation to buy or
              sell a security. Scores are model outputs and can be wrong. Past and backtested performance
              does not predict future results.
            </p>
          </div>
          <FooterColumn
            title="Platform"
            links={[["Create an account", "/sign-up"], ["Sign in", "/sign-in"], ["Plans", "/welcome#plans"]]}
          />
          <FooterColumn
            title="Legal"
            links={[["Terms of Service", "/terms"], ["Privacy Policy", "/privacy"], [LEGAL.contact.legal, `mailto:${LEGAL.contact.legal}`]]}
          />
        </div>
        <div className="mt-12 pt-5 border-t border-aureus-rule flex flex-wrap justify-between gap-x-6 gap-y-2 text-[11px] text-aureus-muted">
          <span>© {year} {LEGAL.entityName}. All rights reserved.</span>
          <span className="font-mono-num">Market data may be delayed. Verify before acting.</span>
        </div>
      </div>
    </footer>
  );
}

function FooterColumn({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <p className="label-caps">{title}</p>
      <ul className="mt-4 space-y-2.5">
        {links.map(([label, href]) => (
          <li key={href}>
            <Link href={href} className="text-[13px] text-aureus-soft hover:text-aureus-gold transition-colors break-all">
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
