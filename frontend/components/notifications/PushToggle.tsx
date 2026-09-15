"use client";
/**
 * Browser push on/off for Strong Buy alerts, per device.
 *
 * Push is per browser, not per account, so this says "this browser" every
 * time. A user who turns it on at work and wonders why their laptop at home
 * is silent has been told why before it happens.
 */
import { useEffect, useState } from "react";
import { IconBell, IconBellOff } from "@/components/ui/icons";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { disablePush, enablePush, getPushState, sendTestPush } from "@/lib/realtime";
import type { PushState } from "@/lib/realtime";

export default function PushToggle({ compact = false }: { compact?: boolean }) {
  const [state, setState] = useState<PushState | "loading">("loading");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getPushState().then(setState).catch(() => setState("unsupported"));
  }, []);

  const toggle = async () => {
    setBusy(true);
    setMessage(null);
    try {
      if (state === "on") {
        await disablePush();
        setState("off");
        setMessage("Push is off for this browser. Alerts still arrive here while the app is open.");
      } else {
        await enablePush();
        setState("on");
        setMessage("This browser will be notified when a stock enters the board, even with the app closed.");
      }
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : "Could not change notification settings");
      setState(await getPushState().catch(() => "unsupported" as PushState));
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const r = await sendTestPush();
      setMessage(r.delivered > 0
        ? `Test sent to ${r.delivered} device${r.delivered === 1 ? "" : "s"}.`
        : "No registered device accepted the test. Try turning push off and on again.");
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : "Test failed");
    } finally {
      setBusy(false);
    }
  };

  const description =
    state === "unsupported" ? "This browser cannot receive push notifications."
    : state === "blocked" ? "Notifications are blocked for this site in your browser settings."
    : state === "on" ? "On for this browser."
    : state === "off" ? "Off for this browser. Alerts only arrive while the app is open."
    : "Checking";

  return (
    <div className={cn(compact ? "space-y-2" : "space-y-3")}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {state === "on"
          ? <IconBell className="w-4 h-4 text-aureus-emerald shrink-0" />
          : <IconBellOff className="w-4 h-4 text-aureus-muted shrink-0" />}
        <div className="min-w-0 flex-1">
          {!compact && <div className="text-[13px] text-aureus-text">Push notifications</div>}
          <div className={cn("text-aureus-muted", compact ? "text-[11.5px]" : "text-[12px]")}>{description}</div>
        </div>
        {(state === "on" || state === "off") && (
          <div className="flex items-center gap-2">
            {state === "on" && !compact && (
              <Button variant="outline" size="sm" onClick={test} disabled={busy}>Send test</Button>
            )}
            <Button variant={state === "on" ? "outline" : "default"} size="sm" onClick={toggle} disabled={busy}>
              {busy ? "Working" : state === "on" ? "Turn off" : "Turn on"}
            </Button>
          </div>
        )}
      </div>
      {message && <p className="text-[11.5px] text-aureus-soft leading-relaxed">{message}</p>}
    </div>
  );
}
