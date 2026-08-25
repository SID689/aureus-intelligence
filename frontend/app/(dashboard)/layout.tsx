// app/(dashboard)/layout.tsx
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "@/lib/auth";
import SessionProvider from "@/components/SessionProvider";
import PortfolioProvider from "@/components/dashboard/PortfolioProvider";
import DashboardShell from "@/components/dashboard/DashboardShell";

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
      {/* PortfolioProvider wraps the shell, not just the page: the ticker
          tape in the chrome and the page below it read the same holdings,
          and fetching in each would double the request and let the two
          drift apart. */}
      <PortfolioProvider>
        <DashboardShell>{children}</DashboardShell>
      </PortfolioProvider>
    </SessionProvider>
  );
}
