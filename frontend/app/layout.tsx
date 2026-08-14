import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title:       "Aureus Intelligence",
  description: "Institutional-grade investment analysis and research platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
