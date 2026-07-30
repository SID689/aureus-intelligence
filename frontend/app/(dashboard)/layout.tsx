// app/(dashboard)/layout.tsx
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "@/lib/auth";
import Sidebar from "@/components/dashboard/Sidebar";
import SessionProvider from "@/components/SessionProvider";

const API = process.env.NEXTAUTH_API_URL || "http://backend:8000";

async function hasCompletedOnboarding(userId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API}/api/v1/onboarding/status?user_id=${userId}`, {
      cache: "no-store",
    });
    if (!res.ok) return true; // fail open — don't lock users out over a transient error
    const data = await res.json();
    return !!data.completed;
  } catch {
    return true;
  }
}

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);
  if (!session) redirect("/welcome");

  // New users must complete the educational onboarding wizard (and sign
  // the risk acknowledgment) before reaching the dashboard.
  const completed = await hasCompletedOnboarding(session.user.id);
  if (!completed) redirect("/onboarding");

  return (
    <SessionProvider session={session}>
      <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg)" }}>
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          {/* Top disclaimer bar */}
          <div className="border-b border-aureus-border px-6 py-1.5 text-xs text-aureus-muted text-center"
               style={{ background: "var(--surface)" }}>
            All analysis is informational only · Not financial advice · Past performance is not indicative of future results
          </div>
          <div className="p-6 max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </SessionProvider>
  );
}
