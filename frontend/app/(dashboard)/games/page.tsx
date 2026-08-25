"use client";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Flame, Trophy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import FinWordle from "@/components/games/FinWordle";
import PatternGame from "@/components/games/PatternGame";
import { getGameStats, getLeaderboard } from "@/lib/api";
import type { GameStats, LeaderboardEntry } from "@/lib/api";

type Tab = "finwordle" | "pattern";

export default function GamesPage() {
  const { data: session } = useSession();
  const userId = session?.user?.id ?? "";

  const [tab, setTab] = useState<Tab>("finwordle");
  const [stats, setStats] = useState<GameStats | null>(null);
  const [board, setBoard] = useState<LeaderboardEntry[]>([]);

  const refresh = useCallback(async () => {
    if (!userId) return;
    try {
      const [s, lb] = await Promise.all([
        getGameStats(userId),
        getLeaderboard(tab === "finwordle" ? "finwordle" : "pattern_guesser", 10),
      ]);
      setStats(s);
      setBoard(lb.entries);
    } catch {
      // Stats and the leaderboard are ancillary — a failure here must never
      // block play, so this degrades to empty panels rather than an error page.
    }
  }, [userId, tab]);

  useEffect(() => { refresh(); }, [refresh]);

  if (!userId) return <div className="py-20 text-center text-aureus-muted text-sm">Loading…</div>;

  const wordleStats = stats?.by_game?.finwordle;
  const patternStats = stats?.by_game?.pattern_guesser;
  const active = tab === "finwordle" ? wordleStats : patternStats;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-aureus-text">Games</h1>
        <p className="text-aureus-muted text-sm mt-0.5">
          Test what you actually know. Every round ends with the concept explained —
          the puzzle is the hook, the definition is the point.
        </p>
      </div>

      {/* Stat strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Current Streak", value: String(wordleStats?.current_streak ?? 0), icon: <Flame className="w-3.5 h-3.5 text-aureus-gold" /> },
          { label: "Max Streak", value: String(wordleStats?.max_streak ?? 0) },
          { label: "Knowledge XP", value: (stats?.total_score ?? 0).toLocaleString() },
          { label: "Win Rate", value: active?.win_rate_pct != null ? `${active.win_rate_pct}%` : "—" },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-3">
              <div className="text-[10px] uppercase tracking-wider text-aureus-muted flex items-center gap-1">
                {s.icon}{s.label}
              </div>
              <div className="text-xl font-semibold text-aureus-text mt-1">{s.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6 items-start">
        <Card>
          <CardHeader>
            <div className="flex gap-1.5">
              {([
                ["finwordle", "FinWordle"],
                ["pattern", "Chart Patterns"],
              ] as const).map(([k, label]) => (
                <button
                  key={k}
                  onClick={() => setTab(k)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    tab === k
                      ? "bg-aureus-gold text-aureus-ink font-semibold"
                      : "text-aureus-muted hover:text-aureus-text"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardContent className="pt-5">
            {tab === "finwordle" ? (
              <FinWordle
                userId={userId}
                currentStreak={wordleStats?.current_streak ?? 0}
                onRoundComplete={refresh}
              />
            ) : (
              <PatternGame userId={userId} onRoundComplete={refresh} />
            )}
          </CardContent>
        </Card>

        {/* Leaderboard */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Trophy className="w-3.5 h-3.5" />
              Leaderboard
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {board.length === 0 ? (
              <p className="text-xs text-aureus-muted py-4 text-center">
                No ranked players yet. Finish a round to claim the top spot.
              </p>
            ) : (
              board.map((e) => {
                const isMe = e.user_id === userId;
                return (
                  <div
                    key={e.user_id}
                    className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-xs ${
                      isMe ? "bg-aureus-gold/10 border border-aureus-gold/30" : ""
                    }`}
                  >
                    <span className={`w-5 font-mono ${e.rank <= 3 ? "text-aureus-gold" : "text-aureus-muted"}`}>
                      {e.rank}
                    </span>
                    <span className={`flex-1 truncate ${isMe ? "text-aureus-gold" : "text-aureus-text"}`}>
                      {e.display_name}{isMe && " (you)"}
                    </span>
                    <span className="text-aureus-muted font-mono" title="Max streak">🔥{e.max_streak}</span>
                    <span className="text-aureus-text font-mono w-12 text-right" title="Knowledge XP">
                      {e.total_score}
                    </span>
                  </div>
                );
              })
            )}
            <p className="text-[10px] text-aureus-muted pt-2 border-t border-aureus-rule mt-2">
              Ranked by longest streak, then knowledge XP. Streaks come from the
              daily word only — practice rounds add XP but can&apos;t inflate a streak.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
