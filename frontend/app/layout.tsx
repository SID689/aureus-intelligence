import type { Metadata, Viewport } from "next";
import "./globals.css";

/**
 * Next's App Router picks up app/icon.png and app/apple-icon.png by
 * convention and emits the <link> tags itself, so those are not listed
 * here. `icons.icon` below points additionally at public/favicon.ico,
 * which carries 16/32/48 in one file for browsers and OS surfaces that
 * still ask for .ico specifically.
 *
 * metadataBase silences Next's relative-URL warning and makes the
 * OpenGraph image resolve to an absolute URL — link previews on Slack,
 * iMessage and Twitter all refuse relative paths. Set
 * NEXT_PUBLIC_SITE_URL in production; localhost is only the fallback.
 */
export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: {
    default: "Aureus Intelligence",
    template: "%s · Aureus Intelligence",
  },
  description:
    "Institutional-grade investment analysis and research platform. Fundamental, technical and sentiment analysis with transparent, metric-backed reasoning.",
  applicationName: "Aureus Intelligence",
  icons: {
    icon: [{ url: "/favicon.ico", sizes: "any" }],
    apple: [{ url: "/brand/mark-180.png", sizes: "180x180" }],
  },
  openGraph: {
    type: "website",
    siteName: "Aureus Intelligence",
    title: "Aureus Intelligence",
    description:
      "Fundamental, technical and sentiment analysis with transparent, metric-backed reasoning.",
    images: [{ url: "/brand/mark-1024.png", width: 1024, height: 1024, alt: "Aureus Intelligence" }],
  },
  twitter: {
    card: "summary",
    title: "Aureus Intelligence",
    description:
      "Fundamental, technical and sentiment analysis with transparent, metric-backed reasoning.",
    images: ["/brand/mark-1024.png"],
  },
};

/**
 * themeColor lives here, not in `metadata`.
 *
 * Next 15 moved it to the viewport export and warns on every render if
 * it is declared in metadata — which it was, producing an "Unsupported
 * metadata themeColor" warning on each page. Colours the mobile browser
 * chrome to match the dark UI instead of leaving a white bar above it.
 */
export const viewport: Viewport = {
  themeColor: "#101309",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
