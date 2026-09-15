import Link from "next/link";
import Logo from "@/components/brand/Logo";
import SiteFooter from "@/components/site/SiteFooter";

/**
 * Sign-in and sign-up share one frame: a statement column on the left that
 * says what the product is in its own terms (method, coverage, disclosure)
 * and the form on the right. A lone centred card on a black page says only
 * "a login form"; this says whose.
 */
export default function AuthFrame({
  title, lead, children, below,
}: {
  title: string;
  lead?: React.ReactNode;
  children: React.ReactNode;
  below?: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-aureus-ink flex flex-col">
      <div className="flex-1 grid lg:grid-cols-[minmax(0,1fr)_minmax(0,36rem)]">
        <aside className="hidden lg:flex flex-col justify-between border-r border-aureus-rule bg-aureus-panel px-14 py-12">
          <Link href="/welcome" aria-label="Aureus Intelligence home" className="w-fit">
            <Logo size={30} withWordmark wordmarkClassName="text-xl" />
          </Link>

          <div className="max-w-lg">
            <p className="font-display text-[38px] leading-[1.12] text-aureus-text">
              Every score arrives with the working behind it.
            </p>
            <dl className="mt-10 border-t border-aureus-rule">
              {[
                ["Method", "Fundamental, technical and sentiment evidence, pooled by published horizon weights"],
                ["Coverage", "The S&P 500, rescored every 15 minutes while the market is open"],
                ["Disclosure", "Data completeness and pillar agreement printed beside every composite"],
              ].map(([k, v]) => (
                <div key={k} className="grid grid-cols-[7rem_1fr] gap-6 py-3.5 border-b border-aureus-rule">
                  <dt className="label-caps pt-0.5">{k}</dt>
                  <dd className="text-[13.5px] text-aureus-soft leading-relaxed">{v}</dd>
                </div>
              ))}
            </dl>
          </div>

          <p className="text-[11.5px] text-aureus-muted leading-relaxed max-w-md">
            Informational research only. Not investment advice, and not a recommendation to buy or sell any security.
          </p>
        </aside>

        <main className="flex items-center justify-center px-5 sm:px-10 py-14">
          <div className="w-full max-w-sm">
            <Link href="/welcome" className="lg:hidden inline-block mb-12" aria-label="Aureus Intelligence home">
              <Logo size={28} withWordmark wordmarkClassName="text-lg" />
            </Link>
            <h1 className="font-display text-[32px] leading-tight text-aureus-text">{title}</h1>
            {lead && <p className="text-[13.5px] text-aureus-muted mt-2 leading-relaxed">{lead}</p>}
            <div className="mt-9">{children}</div>
            {below && <div className="mt-9 pt-6 border-t border-aureus-rule text-[12.5px] text-aureus-muted">{below}</div>}
          </div>
        </main>
      </div>
      <SiteFooter variant="compact" />
    </div>
  );
}

/** Google’s mark stays in Google’s colours: its brand guidelines require it. */
export function GoogleMark() {
  return (
    <svg width="15" height="15" viewBox="0 0 48 48" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.6-6 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6 29.5 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z"/>
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 15.9 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6 29.5 4 24 4 16.3 4 9.6 8.3 6.3 14.7z"/>
      <path fill="#4CAF50" d="M24 44c5.4 0 10.3-1.8 14.1-5l-6.5-5.5C29.5 35.4 26.9 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.6 5.1C9.5 39.6 16.2 44 24 44z"/>
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.2 4.2-4.1 5.6l6.5 5.5C41.6 35.9 44 30.4 44 24c0-1.3-.1-2.7-.4-3.5z"/>
    </svg>
  );
}

export const authInput =
  "w-full h-10 bg-aureus-ink border border-aureus-rule rounded-sm px-3 text-[14px] text-aureus-text " +
  "placeholder:text-aureus-muted/60 focus:outline-none focus:border-aureus-gold transition-colors";
