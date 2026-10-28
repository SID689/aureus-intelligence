import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Newsreader } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

/**
 * Type.
 *
 * Newsreader for display: an editorial serif drawn for long-form news
 * reading, with optical sizes, so headlines are sharp and small captions
 * stay open. IBM Plex Sans for interface text and IBM Plex Mono for every
 * figure: one family across words and numbers, with the engineered,
 * slightly mechanical character of institutional software rather than
 * the neutral grotesk every product template ships with.
 *
 * next/font self-hosts the files at build time. The reader's browser never
 * contacts a font CDN, which is both faster and one fewer third party in
 * the privacy policy.
 */
const display = Newsreader({
  subsets: ["latin"],
  style: ["normal", "italic"],
  axes: ["opsz"],
  variable: "--font-display",
  display: "swap",
});
const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: {
    default: "Aureus Intelligence",
    template: "%s · Aureus Intelligence",
  },
  description:
    "Institutional-grade equity research. Fundamental, technical and sentiment analysis with the reasoning, weighting and data completeness behind every score.",
  applicationName: "Aureus Intelligence",
  icons: {
    icon: [{ url: "/favicon.ico", sizes: "any" }],
    apple: [{ url: "/brand/mark-180.png", sizes: "180x180" }],
  },
  openGraph: {
    type: "website",
    siteName: "Aureus Intelligence",
    title: "Aureus Intelligence",
    description: "Equity research that shows the reasoning, weighting and data behind every score.",
    images: [{ url: "/brand/mark-1024.png", width: 1024, height: 1024, alt: "Aureus Intelligence" }],
  },
  twitter: {
    card: "summary",
    title: "Aureus Intelligence",
    description: "Equity research that shows the reasoning, weighting and data behind every score.",
    images: ["/brand/mark-1024.png"],
  },
};

export const viewport: Viewport = {
  themeColor: "#0b0b0a",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        {children}
        {/*
          Visit counting, from the host we are already on.

          Cookieless and without a device identifier, so it needs no
          consent banner and nothing to decline — which is the only
          reason it is here rather than a tag manager. The privacy policy
          describes it, and must keep describing it if this stays.

          It reports nothing in development and nothing on a deployment
          where Web Analytics has not been switched on in the Vercel
          project. Silence here means that switch, not a broken script.
        */}
        <Analytics />
      </body>
    </html>
  );
}
