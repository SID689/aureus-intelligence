import TradeApproval from "@/components/TradeApproval";

export default function OrdersPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Order Approval</h1>
        <p className="text-aureus-muted text-sm mt-0.5">
          Review and approve agent-generated trade proposals before execution.
        </p>
      </div>
      <TradeApproval />
    </div>
  );
}
