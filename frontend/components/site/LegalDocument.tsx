import Link from "next/link";
import Logo from "@/components/brand/Logo";
import SiteFooter from "./SiteFooter";
import { LEGAL } from "@/lib/legal";

export interface LegalSection {
  id: string;
  title: string;
  content: React.ReactNode;
}

/**
 * The frame for long-form legal documents: a numbered contents rail beside
 * a text column held to a readable measure. Legal text is read by people
 * checking one clause, so every section is anchor-linked and numbered the
 * way it would be cited.
 */
export default function LegalDocument({
  title, summary, sections,
}: {
  title: string;
  summary: React.ReactNode;
  sections: LegalSection[];
}) {
  return (
    <div className="min-h-screen bg-aureus-ink flex flex-col">
      <header className="border-b border-aureus-rule">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-4 flex items-center justify-between gap-6">
          <Link href="/welcome" aria-label="Aureus Intelligence home">
            <Logo size={26} withWordmark wordmarkClassName="text-base" />
          </Link>
          <nav className="flex gap-5 text-[12.5px]" aria-label="Legal documents">
            <Link href="/terms" className="text-aureus-muted hover:text-aureus-text">Terms</Link>
            <Link href="/privacy" className="text-aureus-muted hover:text-aureus-text">Privacy</Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 w-full max-w-6xl mx-auto px-5 sm:px-8 py-12 lg:py-16 grid lg:grid-cols-[14rem_minmax(0,1fr)] gap-x-16 gap-y-10">
        <aside className="hidden lg:block">
          <nav className="sticky top-8" aria-label="Contents">
            <p className="label-caps">Contents</p>
            <ol className="mt-4 border-t border-aureus-rule">
              {sections.map((s, i) => (
                <li key={s.id} className="border-b border-aureus-rulesoft">
                  <a href={`#${s.id}`} className="grid grid-cols-[1.9rem_1fr] py-2 text-[12px] leading-snug text-aureus-muted hover:text-aureus-text">
                    <span className="font-mono-num text-aureus-golddim">{String(i + 1).padStart(2, "0")}</span>
                    {s.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>
        </aside>

        <article className="min-w-0 max-w-[68ch]">
          <p className="label-caps text-aureus-gold">Legal</p>
          <h1 className="font-display text-[40px] sm:text-[48px] leading-[1.04] text-aureus-text mt-3">{title}</h1>
          <p className="font-mono-num text-[12px] text-aureus-muted mt-4">Last updated {LEGAL.lastUpdated}</p>

          <div className="mt-8 border border-aureus-rule bg-aureus-panel px-5 py-4 legal-prose text-[14px]">{summary}</div>

          {sections.map((s, i) => (
            <section key={s.id} id={s.id} className="scroll-mt-8 mt-12 pt-8 border-t border-aureus-rule">
              <h2 className="flex items-baseline gap-4 font-display text-[23px] leading-tight text-aureus-text">
                <span className="font-mono-num text-[12px] text-aureus-gold">{String(i + 1).padStart(2, "0")}</span>
                {s.title}
              </h2>
              <div className="legal-prose mt-4">{s.content}</div>
            </section>
          ))}
        </article>
      </main>

      <SiteFooter variant="compact" />
    </div>
  );
}
