"use client";
/**
 * The projector slide: one large code, the address in plain text under it,
 * and a step count. Nothing animated, nothing that needs explaining from
 * the front of the room.
 *
 * The address comes from `window.location.origin` so it can never drift
 * from the deployment this page is being served by, and it is editable for
 * the case where the projected machine reaches the app on an address the
 * audience cannot (localhost during a rehearsal, an internal hostname
 * behind a proxy).
 */
import { useEffect, useState } from "react";
import Logo from "@/components/brand/Logo";
import PresentationQR from "@/components/demo/PresentationQR";
import { Input } from "@/components/ui/primitives";
import { IconCopy } from "@/components/ui/icons";

export default function DemoQRBoard() {
  const [origin, setOrigin] = useState("");
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);

  // Rendered after mount: the origin does not exist during SSR, and
  // guessing it would put a wrong address on a projector.
  useEffect(() => { setOrigin(window.location.origin); }, []);

  const target = origin ? `${origin.replace(/\/$/, "")}/demo` : "";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(target);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setEditing(true);   // no clipboard permission: show it selectable instead
    }
  };

  return (
    <main className="min-h-screen bg-aureus-ink flex flex-col">
      <header className="border-b border-aureus-rule px-6 sm:px-10 py-4 flex items-center justify-between gap-4">
        <Logo size={26} withWordmark wordmarkClassName="text-lg" tagline="Intelligence" />
        <span className="label-caps text-aureus-gold">Scan for mobile demo</span>
      </header>

      <div className="flex-1 grid lg:grid-cols-[minmax(0,1fr)_auto] items-center gap-12 px-6 sm:px-10 py-10 max-w-6xl mx-auto w-full">
        <div className="max-w-xl">
          <h1 className="font-display text-[clamp(30px,5vw,52px)] leading-[1.08] text-aureus-text">
            Open the terminal on your phone.
          </h1>
          <ol className="mt-8 border-t border-aureus-rule">
            {[
              ["01", "Point your camera at the code"],
              ["02", "Open the link it offers"],
              ["03", "You arrive on the Institutional plan, fully unlocked"],
            ].map(([n, text]) => (
              <li key={n} className="grid grid-cols-[2.25rem_1fr] gap-4 py-3.5 border-b border-aureus-rule">
                <span className="font-mono-num text-[12px] text-aureus-gold pt-0.5">{n}</span>
                <span className="text-[14px] text-aureus-soft leading-relaxed">{text}</span>
              </li>
            ))}
          </ol>

          <div className="mt-8">
            <div className="label-caps">Address</div>
            {editing ? (
              <Input
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                className="mt-2 font-mono-num h-11"
                aria-label="Public address of this deployment"
                spellCheck={false}
              />
            ) : (
              <div className="mt-2 flex items-center gap-3 flex-wrap">
                <code className="font-mono-num text-[15px] sm:text-[17px] text-aureus-text break-all">
                  {target || "reading this deployment's address"}
                </code>
                <button
                  onClick={copy}
                  className="inline-flex items-center gap-1.5 border border-aureus-rulestrong px-2.5 min-h-[36px] text-[11.5px] text-aureus-soft hover:border-aureus-gold hover:text-aureus-gold transition-colors"
                >
                  <IconCopy className="w-3.5 h-3.5" />
                  {copied ? "Copied" : "Copy"}
                </button>
                <button
                  onClick={() => setEditing(true)}
                  className="label-caps text-aureus-muted hover:text-aureus-gold min-h-[36px] px-1"
                >
                  Not reachable from phones? Set it
                </button>
              </div>
            )}
          </div>

          <p className="mt-6 text-[12px] text-aureus-muted leading-relaxed max-w-md">
            Showcase environment. Every figure is real engine output on a paper portfolio.
            Informational research only, and not investment advice.
          </p>
        </div>

        <div className="justify-self-center lg:justify-self-end">
          <PresentationQR
            url={target}
            size={400}
            label="Aureus Intelligence institutional demo"
            className="max-w-full"
          />
        </div>
      </div>
    </main>
  );
}
