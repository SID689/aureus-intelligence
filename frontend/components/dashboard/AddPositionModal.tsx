"use client";
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { addHolding, updateHolding, deleteHolding } from "@/lib/api";
import type { Holding } from "@/lib/api";

interface Props {
  portfolioId: string;
  userId: string;
  onClose: () => void;
  onAdded: () => void;
  // When provided, the modal operates in edit mode for this existing
  // holding — ticker is locked, quantity/cost are prefilled, and a
  // Delete option appears. Omit for "add new position" mode.
  editingHolding?: Holding;
}

export default function AddPositionModal({ portfolioId, userId, onClose, onAdded, editingHolding }: Props) {
  const isEditing = !!editingHolding;
  const [ticker, setTicker] = useState(editingHolding?.ticker ?? "");
  const [quantity, setQuantity] = useState(editingHolding ? String(editingHolding.quantity) : "");
  const [costBasis, setCostBasis] = useState(editingHolding ? String(editingHolding.average_cost_basis) : "");
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const qty = parseFloat(quantity);
    const cost = parseFloat(costBasis);
    if ((!isEditing && !ticker.trim()) || !qty || qty <= 0 || !cost || cost <= 0) {
      setError("Enter a valid ticker, quantity, and cost basis.");
      return;
    }

    setLoading(true);
    try {
      if (isEditing && editingHolding) {
        await updateHolding(editingHolding.id, userId, { quantity: qty, average_cost_basis: cost });
      } else {
        await addHolding({
          portfolio_id: portfolioId, user_id: userId,
          ticker: ticker.toUpperCase().trim(), quantity: qty, average_cost_basis: cost,
        });
      }
      onAdded();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not save position");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!editingHolding) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteHolding(editingHolding.id, userId);
      onAdded();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not remove position");
      setDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <form onSubmit={handleSubmit}
            className="w-full max-w-sm rounded-xl border border-aureus-rule p-5 space-y-4"
            style={{ background: "var(--panel)" }}
            onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="font-display text-aureus-text text-lg" style={{ fontWeight: 600 }}>
            {isEditing ? `Edit ${editingHolding?.ticker}` : "Add Position"}
          </h3>
          {isEditing && (
            <button type="button" onClick={() => setConfirmDelete(true)}
                    className="text-aureus-oxblood hover:text-aureus-oxblood transition-colors" aria-label="Delete position">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>

        {error && (
          <div className="rounded p-2 bg-aureus-oxblood/10 border border-aureus-oxblooddim text-aureus-oxblood text-xs">{error}</div>
        )}

        {confirmDelete ? (
          <div className="space-y-3 py-2">
            <p className="text-sm text-aureus-soft">
              Remove your entire {editingHolding?.ticker} position ({editingHolding?.quantity} shares)?
              This can&apos;t be undone.
            </p>
            <div className="flex gap-2">
              <button type="button" onClick={handleDelete} disabled={deleting}
                      className="flex-1 py-2 rounded-lg border border-aureus-oxblooddim text-aureus-oxblood text-sm font-semibold hover:bg-aureus-oxblood/10 disabled:opacity-50">
                {deleting ? "Removing..." : "Yes, remove it"}
              </button>
              <button type="button" onClick={() => setConfirmDelete(false)}
                      className="px-4 py-2 rounded-lg border border-aureus-rule text-aureus-muted text-sm hover:text-aureus-text">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            {!isEditing && (
              <div className="space-y-1">
                <label className="text-xs text-aureus-muted">Ticker</label>
                <input
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="AAPL"
                  maxLength={10}
                  className="w-full bg-transparent border border-aureus-rule rounded px-3 py-2 text-aureus-text text-sm focus:outline-none focus:border-aureus-gold"
                />
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-aureus-muted">Shares</label>
                <input
                  type="number" step="any" value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  placeholder="10"
                  className="w-full bg-transparent border border-aureus-rule rounded px-3 py-2 text-aureus-text text-sm font-mono-num focus:outline-none focus:border-aureus-gold"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-aureus-muted">Cost / Share</label>
                <input
                  type="number" step="any" value={costBasis}
                  onChange={(e) => setCostBasis(e.target.value)}
                  placeholder="175.00"
                  className="w-full bg-transparent border border-aureus-rule rounded px-3 py-2 text-aureus-text text-sm font-mono-num focus:outline-none focus:border-aureus-gold"
                />
              </div>
            </div>

            <p className="text-xs text-aureus-muted">
              {isEditing
                ? "Updates your share count and average cost basis directly."
                : "If you already hold this ticker, the new shares are merged with your existing position using a weighted-average cost basis."}
            </p>

            <div className="flex gap-2 pt-1">
              <button type="submit" disabled={loading}
                      className="flex-1 py-2 rounded-lg bg-aureus-gold text-aureus-ink font-semibold text-sm hover:opacity-90 disabled:opacity-50">
                {loading ? "Saving..." : isEditing ? "Save Changes" : "Add Position"}
              </button>
              <button type="button" onClick={onClose}
                      className="px-4 py-2 rounded-lg border border-aureus-rule text-aureus-muted text-sm hover:text-aureus-text">
                Cancel
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  );
}
