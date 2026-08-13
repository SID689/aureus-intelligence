"""
app/api/v1/games.py
---------------------
Financial Games Engine — FinWordle and the Chart Pattern Guesser.

  POST /api/v1/games/finwordle/session         start or resume a round
  POST /api/v1/games/finwordle/guess           submit a guess, get tiles back
  POST /api/v1/games/pattern/scenario          new chart scenario
  POST /api/v1/games/pattern/guess             answer it, get the reveal
  GET  /api/v1/games/leaderboard               top players by streak / score
  GET  /api/v1/games/stats?user_id=            one user's stats

=====================================================================
THE ANSWER NEVER LEAVES THE SERVER UNTIL THE ROUND IS OVER
=====================================================================
Every response builder in this module goes through a helper that decides
whether the round has ended before including the answer. A client that
inspects the network tab mid-game sees tile colours and nothing else.
Same for pattern scenarios: outcome bars and the correct direction are
withheld until the player has committed to a choice.

This is why guesses are graded here rather than in the browser. It's the
same reasoning as the education quiz endpoints — make cheating impossible
rather than merely inconvenient.

=====================================================================
STREAKS ARE A DAILY CONCEPT
=====================================================================
Only the DAILY FinWordle mode moves the streak, and only once per day.
Practice rounds add score but can't inflate a streak, otherwise the
leaderboard would rank whoever replayed most, not whoever showed up most
consistently. The advance/reset rule lives in `_apply_daily_streak`.
"""

import json
import logging
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.games import pattern_engine
from app.games.finwordle_dictionary import MAX_GUESSES, WORD_LENGTH
from app.games.wordle_engine import (
    daily_puzzle_index,
    daily_word,
    emoji_grid,
    get_entry,
    is_solved,
    keyboard_state,
    practice_word,
    score_for_round,
    score_guess,
    validate_guess,
)

logger = logging.getLogger("aureus.api.games")
router = APIRouter(prefix="/api/v1/games", tags=["games"])

Mode = Literal["daily", "practice"]


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


# ── Stats / streak maintenance ────────────────────────────────────────────

def _ensure_stats(conn, user_id: str, game_type: str) -> None:
    conn.execute(
        text("""
            INSERT INTO game_stats (user_id, game_type)
            VALUES (:uid, CAST(:gt AS game_type))
            ON CONFLICT (user_id, game_type) DO NOTHING
        """),
        {"uid": user_id, "gt": game_type},
    )


def _apply_daily_streak(conn, user_id: str, won: bool, today: date) -> None:
    """
    Advance or reset the daily streak.

    Rules:
      - A win on a day immediately following the last counted day extends
        the streak.
      - A win after a gap starts a new streak at 1.
      - A loss resets to 0.
      - A second daily result on the same date is ignored (the unique index
        on (user_id, puzzle_date) should prevent it reaching here anyway).
    """
    row = conn.execute(
        text("SELECT current_streak, max_streak, last_daily_played FROM game_stats "
             "WHERE user_id = :uid AND game_type = 'finwordle'"),
        {"uid": user_id},
    ).fetchone()
    if row is None:
        return
    if row.last_daily_played == today:
        return  # already counted today

    if not won:
        new_streak = 0
    elif row.last_daily_played == today - timedelta(days=1):
        new_streak = row.current_streak + 1
    else:
        new_streak = 1

    conn.execute(
        text("""
            UPDATE game_stats
            SET current_streak    = :cs,
                max_streak        = GREATEST(max_streak, :cs),
                last_daily_played = :today,
                updated_at        = NOW()
            WHERE user_id = :uid AND game_type = 'finwordle'
        """),
        {"cs": new_streak, "today": today, "uid": user_id},
    )


def _record_round(conn, user_id: str, game_type: str, won: bool, score: int,
                  counts_for_streak: bool, today: date) -> None:
    _ensure_stats(conn, user_id, game_type)
    conn.execute(
        text("""
            UPDATE game_stats
            SET games_played   = games_played + 1,
                games_won      = games_won + CASE WHEN :won THEN 1 ELSE 0 END,
                total_score    = total_score + :score,
                last_played_at = NOW(),
                updated_at     = NOW()
            WHERE user_id = :uid AND game_type = CAST(:gt AS game_type)
        """),
        {"won": won, "score": score, "uid": user_id, "gt": game_type},
    )
    if counts_for_streak:
        _apply_daily_streak(conn, user_id, won, today)


# ── FinWordle ─────────────────────────────────────────────────────────────

def _session_payload(row, *, reveal: bool) -> dict:
    """
    Build the client view of a session.

    `reveal` gates every field that would give the answer away. It is only
    ever True once status != 'in_progress'.
    """
    guesses: list[str] = json.loads(row.guesses) if isinstance(row.guesses, str) else (row.guesses or [])
    answer = row.answer
    tiles = [score_guess(g, answer) for g in guesses]

    payload = {
        "session_id": str(row.id),
        "mode": row.mode,
        "puzzle_date": str(row.puzzle_date) if row.puzzle_date else None,
        "puzzle_number": daily_puzzle_index(row.puzzle_date) if row.puzzle_date else None,
        "word_length": WORD_LENGTH,
        "max_guesses": MAX_GUESSES,
        "guesses": guesses,
        "tiles": tiles,
        "keyboard": keyboard_state(guesses, answer),
        "status": row.status,
        "guesses_used": len(guesses),
        "score_awarded": row.score_awarded,
    }

    if reveal:
        entry = get_entry(answer)
        payload["answer"] = answer
        payload["emoji_grid"] = emoji_grid(tiles)
        payload["education"] = entry.to_dict() if entry else None
    return payload


class SessionRequest(BaseModel):
    user_id: str
    mode: Mode = "daily"


@router.post("/finwordle/session")
def finwordle_session(req: SessionRequest) -> dict:
    """
    Start a new round or resume an in-progress one.

    Daily mode is idempotent per calendar day — calling this repeatedly
    returns the same session, including a finished one (so the results
    screen survives a refresh) rather than handing out a second attempt.
    """
    today = date.today()
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            if req.mode == "daily":
                row = conn.execute(
                    text("SELECT * FROM finwordle_sessions WHERE user_id = :uid "
                         "AND mode = 'daily' AND puzzle_date = :d"),
                    {"uid": req.user_id, "d": today},
                ).fetchone()
                if row is None:
                    answer = daily_word(today).word
                    row = conn.execute(
                        text("""
                            INSERT INTO finwordle_sessions (user_id, mode, puzzle_date, answer)
                            VALUES (:uid, 'daily', :d, :a)
                            RETURNING *
                        """),
                        {"uid": req.user_id, "d": today, "a": answer},
                    ).fetchone()
            else:
                # Practice: always a fresh round. Seeding the word on the new
                # row's own id keeps it stable across refreshes of THAT round.
                sid = str(uuid.uuid4())
                answer = practice_word(sid).word
                row = conn.execute(
                    text("""
                        INSERT INTO finwordle_sessions (id, user_id, mode, puzzle_date, answer)
                        VALUES (:sid, :uid, 'practice', NULL, :a)
                        RETURNING *
                    """),
                    {"sid": sid, "uid": req.user_id, "a": answer},
                ).fetchone()
            _ensure_stats(conn, req.user_id, "finwordle")
    except Exception as exc:
        logger.error("FinWordle session failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not start the game")
    finally:
        engine.dispose()

    return _session_payload(row, reveal=row.status != "in_progress")


class GuessRequest(BaseModel):
    user_id: str
    session_id: str
    guess: str = Field(min_length=1, max_length=16)


@router.post("/finwordle/guess")
def finwordle_guess(req: GuessRequest) -> dict:
    ok, err = validate_guess(req.guess)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    guess = req.guess.strip().upper()

    engine = _get_engine()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM finwordle_sessions WHERE id = :sid AND user_id = :uid FOR UPDATE"),
                {"sid": req.session_id, "uid": req.user_id},
            ).fetchone()
            if row is None:
                # Scoped to user_id, so another user's session id reads as
                # not-found rather than confirming it exists.
                raise HTTPException(status_code=404, detail="Game session not found")
            if row.status != "in_progress":
                raise HTTPException(status_code=400, detail="This round is already finished")

            guesses: list[str] = json.loads(row.guesses) if isinstance(row.guesses, str) else (row.guesses or [])
            if len(guesses) >= MAX_GUESSES:
                raise HTTPException(status_code=400, detail="No guesses remaining")

            guesses = guesses + [guess]
            tiles = score_guess(guess, row.answer)
            won = is_solved(tiles)
            out_of_guesses = len(guesses) >= MAX_GUESSES
            status = "won" if won else ("lost" if out_of_guesses else "in_progress")

            score = score_for_round(won, len(guesses)) if status != "in_progress" else 0

            row = conn.execute(
                text("""
                    UPDATE finwordle_sessions
                    SET guesses = CAST(:g AS jsonb),
                        status = CAST(:st AS game_session_status),
                        score_awarded = :score,
                        completed_at = CASE WHEN :done THEN NOW() ELSE completed_at END,
                        updated_at = NOW()
                    WHERE id = :sid
                    RETURNING *
                """),
                {
                    "g": json.dumps(guesses), "st": status, "score": score,
                    "done": status != "in_progress", "sid": req.session_id,
                },
            ).fetchone()

            if status != "in_progress":
                _record_round(
                    conn, req.user_id, "finwordle", won=won, score=score,
                    counts_for_streak=(row.mode == "daily"),
                    today=row.puzzle_date or date.today(),
                )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("FinWordle guess failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not record guess")
    finally:
        engine.dispose()

    return _session_payload(row, reveal=row.status != "in_progress")


# ── Chart Pattern Guesser ─────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    user_id: str


@router.post("/pattern/scenario")
def pattern_scenario(req: ScenarioRequest) -> dict:
    """New scenario. Ticker, outcome bars and answer are all withheld."""
    try:
        scenario = pattern_engine.generate_scenario(random.Random())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("Scenario generation failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not build a scenario")

    engine = _get_engine()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO pattern_scenarios
                      (user_id, ticker, setup_bars, outcome_bars, correct_direction,
                       forward_return_pct, threshold_pct, rationale, setup_notes)
                    VALUES
                      (:uid, :ticker, CAST(:setup AS jsonb), CAST(:outcome AS jsonb), :dir,
                       :fwd, :thr, :rat, CAST(:notes AS jsonb))
                    RETURNING id, created_at
                """),
                {
                    "uid": req.user_id, "ticker": scenario.ticker,
                    "setup": json.dumps(scenario.setup_bars),
                    "outcome": json.dumps(scenario.outcome_bars),
                    "dir": scenario.correct_direction,
                    "fwd": scenario.forward_return_pct,
                    "thr": scenario.threshold_pct,
                    "rat": scenario.rationale,
                    "notes": json.dumps(scenario.setup_notes),
                },
            ).fetchone()
            _ensure_stats(conn, req.user_id, "pattern_guesser")
    except Exception as exc:
        logger.error("Scenario persist failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save the scenario")
    finally:
        engine.dispose()

    return {
        "scenario_id": str(row.id),
        "setup_bars": scenario.setup_bars,
        "setup_notes": scenario.setup_notes,
        "outcome_horizon_sessions": pattern_engine.OUTCOME_BARS,
        "choices": [
            {"value": k, "label": v} for k, v in pattern_engine.DIRECTION_LABELS.items()
        ],
    }


class PatternGuessRequest(BaseModel):
    user_id: str
    scenario_id: str
    direction: Literal["bullish_breakout", "bearish_breakdown", "range_consolidation"]


@router.post("/pattern/guess")
def pattern_guess(req: PatternGuessRequest) -> dict:
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT * FROM pattern_scenarios WHERE id = :sid AND user_id = :uid FOR UPDATE"),
                {"sid": req.scenario_id, "uid": req.user_id},
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Scenario not found")
            if row.answered_at is not None:
                raise HTTPException(status_code=400, detail="This scenario was already answered")

            correct = req.direction == row.correct_direction
            score = pattern_engine.score_pattern_guess(correct)

            conn.execute(
                text("""
                    UPDATE pattern_scenarios
                    SET guessed_direction = :g, was_correct = :c,
                        score_awarded = :s, answered_at = NOW()
                    WHERE id = :sid
                """),
                {"g": req.direction, "c": correct, "s": score, "sid": req.scenario_id},
            )
            # Pattern rounds add score but never touch the daily streak.
            _record_round(conn, req.user_id, "pattern_guesser", won=correct,
                          score=score, counts_for_streak=False, today=date.today())
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Pattern guess failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not record your answer")
    finally:
        engine.dispose()

    outcome = json.loads(row.outcome_bars) if isinstance(row.outcome_bars, str) else row.outcome_bars
    return {
        "correct": correct,
        "your_direction": req.direction,
        "correct_direction": row.correct_direction,
        "correct_label": pattern_engine.DIRECTION_LABELS[row.correct_direction],
        "ticker": row.ticker,                       # revealed only now
        "outcome_bars": outcome,
        "forward_return_pct": float(row.forward_return_pct),
        "threshold_pct": float(row.threshold_pct),
        "rationale": row.rationale,
        "score_awarded": score,
    }


# ── Leaderboard & stats ───────────────────────────────────────────────────

@router.get("/leaderboard")
def leaderboard(
    game_type: str = Query(default="finwordle", pattern="^(finwordle|pattern_guesser)$"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """
    Top players, ranked by max streak then total score.

    Only display_name is exposed — never email. A user without a profile
    name falls back to an anonymous label rather than leaking the address
    they signed up with.
    """
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT gs.user_id, gs.games_played, gs.games_won, gs.current_streak,
                           gs.max_streak, gs.total_score, p.display_name
                    FROM game_stats gs
                    JOIN users u ON u.id = gs.user_id AND u.is_active AND u.deleted_at IS NULL
                    LEFT JOIN profiles p ON p.user_id = gs.user_id
                    WHERE gs.game_type = CAST(:gt AS game_type) AND gs.games_played > 0
                    ORDER BY gs.max_streak DESC, gs.total_score DESC, gs.games_won DESC
                    LIMIT :lim
                """),
                {"gt": game_type, "lim": limit},
            ).fetchall()
    except Exception as exc:
        logger.error("Leaderboard query failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Could not load the leaderboard")
    finally:
        engine.dispose()

    return {
        "game_type": game_type,
        "entries": [
            {
                "rank": i + 1,
                "user_id": str(r.user_id),
                "display_name": (r.display_name or "").strip() or "Anonymous Trader",
                "games_played": r.games_played,
                "games_won": r.games_won,
                "win_rate_pct": round(r.games_won / r.games_played * 100, 1) if r.games_played else 0.0,
                "current_streak": r.current_streak,
                "max_streak": r.max_streak,
                "total_score": r.total_score,
            }
            for i, r in enumerate(rows)
        ],
    }


@router.get("/stats")
def user_stats(user_id: str) -> dict:
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT game_type, games_played, games_won, current_streak, max_streak, "
                     "total_score, last_daily_played FROM game_stats WHERE user_id = :uid"),
                {"uid": user_id},
            ).fetchall()
            played_today = conn.execute(
                text("SELECT status FROM finwordle_sessions WHERE user_id = :uid "
                     "AND mode = 'daily' AND puzzle_date = :d"),
                {"uid": user_id, "d": date.today()},
            ).fetchone()
    except Exception as exc:
        logger.error("Stats query failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Could not load stats")
    finally:
        engine.dispose()

    by_game = {
        r.game_type: {
            "games_played": r.games_played,
            "games_won": r.games_won,
            "win_rate_pct": round(r.games_won / r.games_played * 100, 1) if r.games_played else None,
            "current_streak": r.current_streak,
            "max_streak": r.max_streak,
            "total_score": r.total_score,
            "last_daily_played": str(r.last_daily_played) if r.last_daily_played else None,
        }
        for r in rows
    }
    return {
        "by_game": by_game,
        "total_score": sum(v["total_score"] for v in by_game.values()),
        "daily_puzzle_number": daily_puzzle_index(date.today()),
        "daily_status_today": played_today.status if played_today else "not_started",
    }
