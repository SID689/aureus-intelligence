// app/(onboarding)/layout.tsx
// This was the missing piece causing the crash at /onboarding: the
// (onboarding) route group had no SessionProvider, so useSession() inside
// OnboardingWizard.tsx threw immediately ("useSession must be wrapped in
// a <SessionProvider>"). Mirrors the (dashboard) layout's pattern.
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "@/lib/auth";
import SessionProvider from "@/components/SessionProvider";

export default async function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);
  if (!session) redirect("/sign-in");

  return <SessionProvider session={session}>{children}</SessionProvider>;
}
