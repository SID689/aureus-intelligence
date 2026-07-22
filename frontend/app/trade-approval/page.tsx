import TradeApproval from "@/components/TradeApproval";

export default function TradeApprovalPage() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Order Approval</h1>
        <p className="text-aureus-muted text-sm mt-1">
          Review and approve agent-generated trade proposals before execution.
        </p>
      </div>
      <TradeApproval />
    </div>
  );
}
