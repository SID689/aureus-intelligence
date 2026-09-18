import type { Metadata } from "next";
import DemoQRBoard from "@/components/demo/DemoQRBoard";

export const metadata: Metadata = {
  title: "Scan for Mobile Demo · Aureus Intelligence",
  robots: { index: false, follow: false },
};

/**
 * The slide. Open this on the machine driving the projector and the room
 * scans it.
 *
 * It reads its own origin in the browser rather than taking a configured
 * hostname, so the code always points at the address this page was
 * actually reached on. A tunnel URL that changes between rehearsal and
 * the event cannot leave a stale QR code on screen.
 */
export default function DemoQRPage() {
  return <DemoQRBoard />;
}
