"use client";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { connectAlertStream } from "@/lib/websocket";
import { approveOrder, rejectOrder } from "@/lib/api";

interface Proposal {
  proposal_id: string;
  ticker: string;
  side: string;
  quantity: number;
  stop_loss_price: number;
  take_profit_price: number;
  confidence: number;
  expires_at: string;
  approval_token: string;
  state?: string;
}

export default function TradeApproval() {
  const { data: session } = useSession();
  const USER_ID = session?.user?.id ?? "";
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading,   setLoading]   = useState<string | null>(null);
  const [result,    setResult]    = useState<{ id: string; msg: string; ok: boolean } | null>(null);

  // Listen for HITL approval requests via WebSocket
  useEffect(() => {
    if (!USER_ID) return;
    const ws = connectAlertStream(USER_ID, (msg) => {
      if (msg.type === "hitl_approval_required") {
        const p = msg as unknown as Proposal;
        setProposals((prev) => {
          if (prev.some((x) => x.proposal_id === p.proposal_id)) return prev;
          return [...prev, p];
        });
      }
    });
    return () => ws.close();
  }, [USER_ID]);

  const handleApprove = async (p: Proposal) => {
    setLoading(p.proposal_id);
    try {
      await approveOrder(p.proposal_id, USER_ID, p.approval_token);
      setResult({ id: p.proposal_id, msg: "Order submitted to broker.", ok: true });
      setProposals((prev) => prev.filter((x) => x.proposal_id !== p.proposal_id));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setResult({ id: p.proposal_id, msg: `Approval failed: ${msg}`, ok: false });
    } finally {
      setLoading(null);
    }
  };

  const handleReject = async (p: Proposal) => {
    setLoading(p.proposal_id);
    try {
      await rejectOrder(p.proposal_id, USER_ID);
      setResult({ id: p.proposal_id, msg: "Order rejected.", ok: true });
      setProposals((prev) => prev.filter((x) => x.proposal_id !== p.proposal_id));
    } catch {
      setResult({ id: p.proposal_id, msg: "Rejection failed.", ok: false });
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Result toast */}
      {result && (
        <div className={`rounded-lg p-3 text-sm border ${
          result.ok
            ? "border-aureus-green text-aureus-green bg-green-950/20"
            : "border-aureus-red text-aureus-red bg-red-950/20"
        }`}>
          {result.msg}
          <button onClick={() => setResult(null)} className="ml-3 underline text-xs">dismiss</button>
        </div>
      )}

      {proposals.length === 0 ? (
        <div className="rounded-lg border border-aureus-border p-12 text-center"
             style={{ background: "var(--surface)" }}>
          <div className="text-4xl mb-3">⏳</div>
          <p className="text-aureus-muted text-sm">
            No pending order approvals. Proposals from your active strategies will appear here.
          </p>
        </div>
      ) : (
        proposals.map((p) => (
          <div key={p.proposal_id} className="rounded-lg border border-aureus-gold/30 p-5 space-y-4"
               style={{ background: "var(--surface)" }}>
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${
                  p.side === "buy" ? "bg-green-950 text-aureus-green" : "bg-red-950 text-aureus-red"
                }`}>{p.side}</span>
                <span className="text-white font-bold text-lg">{p.ticker}</span>
              </div>
              <span className="text-xs text-aureus-muted">
                Expires {new Date(p.expires_at).toLocaleTimeString()}
              </span>
            </div>

            {/* Order details */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Detail label="Quantity"    value={`${p.quantity} shares`} />
              <Detail label="Confidence"  value={`${(p.confidence * 100).toFixed(0)}%`}
                      color={p.confidence >= 0.65 ? "text-aureus-green" : "text-aureus-gold"} />
              <Detail label="Stop-Loss"   value={`$${p.stop_loss_price?.toFixed(2)}`}  color="text-aureus-red" />
              <Detail label="Take-Profit" value={`$${p.take_profit_price?.toFixed(2)}`} color="text-aureus-green" />
            </div>

            {/* Disclaimer */}
            <p className="text-xs text-aureus-muted border-t border-aureus-border pt-3">
              ⚠ Approving submits a real order to your connected broker account.
              Stop-loss and take-profit levels are automatically attached.
              This is not financial advice.
            </p>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={() => handleApprove(p)}
                disabled={loading === p.proposal_id}
                className="flex-1 py-2 rounded-lg bg-aureus-green text-black font-semibold
                           text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                {loading === p.proposal_id ? "Processing..." : "✓ Approve & Execute"}
              </button>
              <button
                onClick={() => handleReject(p)}
                disabled={loading === p.proposal_id}
                className="flex-1 py-2 rounded-lg border border-aureus-red text-aureus-red
                           font-semibold text-sm hover:bg-red-950/30 disabled:opacity-50 transition-colors"
              >
                ✕ Reject
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function Detail({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded p-2 border border-aureus-border" style={{ background: "var(--bg)" }}>
      <div className="text-aureus-muted text-xs mb-1">{label}</div>
      <div className={`font-semibold ${color}`}>{value}</div>
    </div>
  );
}
