"""
app/games/wordle_engine.py
----------------------------
Pure game logic for FinWordle. No I/O, no database — everything here is a
deterministic function of its inputs, which is what makes the tile
algorithm straightforwardly testable.

=====================================================================
THE TILE ALGORITHM — WHY IT IS TWO PASSES
=====================================================================
Colouring tiles is the part of Wordle that clones most often get wrong,
and the bug only shows up on repeated letters.

The naive approach — "green if it matches, else yellow if the letter
appears anywhere in the answer" — over-reports yellows. Guessing SPEND
against ASSET would mark BOTH S's as present even though the answer
contains exactly one S, telling the player something false.

The correct rule is that each letter of the answer can be consumed by
exactly one tile. So:

  Pass 1 — mark every exact positional match green and DECREMENT that
           letter's remaining count.
  Pass 2 — walk the non-green tiles left to right; a letter is yellow
           only if that letter still has remaining count left after the
           greens took theirs, and consuming it decrements again.

Left-to-right ordering in pass 2 matters: when a guess has more copies of
a letter than the answer does, the earlier occurrence gets the yellow and
the later one goes grey. That's the behaviour players expect.

Worked example — answer ASSET, guess SASSY:
    A S S E T   (answer)
    S A S S Y   (guess)
  Pass 1: index 2 is S vs S -> GREEN. Remaining letters: A,S,E,T minus
          nothing for the green's S -> {A:1, S:1, E:1, T:1}.
  Pass 2: index 0 'S' -> S remaining (1) -> YELLOW, now {S:0}.
          index 1 'A' -> A remaining (1) -> YELLOW, now {A:0}.
          index 3 'S' -> S remaining is 0 -> ABSENT.
          index 4 'Y' -> not in answer -> ABSENT.
  Result: yellow, yellow, green, absent, absent.
"""

import hashlib
from collections import Counter
from datetime import date
from typing import Literal

from app.games.finwordle_dictionary import (
    ANSWERS,
    MAX_GUESSES,
    WORD_LENGTH,
    WordEntry,
    get_entry,
    is_valid_guess,
)

TileState = Literal["correct", "present", "absent"]

# FinWordle launched on this date. The daily puzzle index counts forward
# from here, so the sequence is stable and reproducible for every user.
EPOCH = date(2026, 1, 1)


def score_guess(guess: str, answer: str) -> list[TileState]:
    """
    Return one TileState per letter of `guess`. See the module docstring
    for why this is two passes rather than one.
    """
    guess = guess.upper()
    answer = answer.upper()
    if len(guess) != len(answer):
        raise ValueError(f"Guess {guess!r} and answer must be the same length")

    tiles: list[TileState] = ["absent"] * len(guess)

    # Pass 1 — exact positional matches claim their letter first.
    remaining = Counter(answer)
    for i, ch in enumerate(guess):
        if ch == answer[i]:
            tiles[i] = "correct"
            remaining[ch] -= 1

    # Pass 2 — wrong-position matches draw from whatever is left over.
    for i, ch in enumerate(guess):
        if tiles[i] == "correct":
            continue
        if remaining.get(ch, 0) > 0:
            tiles[i] = "present"
            remaining[ch] -= 1

    return tiles


def keyboard_state(guesses: list[str], answer: str) -> dict[str, TileState]:
    """
    Best-known state for each letter typed so far, for colouring the
    on-screen keyboard. 'correct' outranks 'present' outranks 'absent' —
    a letter confirmed green somewhere must never be downgraded to yellow
    by a later guess that placed it wrong.
    """
    rank = {"absent": 0, "present": 1, "correct": 2}
    best: dict[str, TileState] = {}
    for g in guesses:
        for ch, state in zip(g.upper(), score_guess(g, answer)):
            if ch not in best or rank[state] > rank[best[ch]]:
                best[ch] = state
    return best


def daily_puzzle_index(day: date) -> int:
    return (day - EPOCH).days


def _shuffled_answers() -> list[WordEntry]:
    """
    The answer bank in a fixed, non-alphabetical order.

    Ordered by a hash of each word, so the sequence is stable across
    processes and deploys but is not the order the list is written in. A
    player reading the source still learns the order; the point is that
    someone who merely notices today's answer cannot infer tomorrow's
    from the shape of the list.
    """
    return sorted(ANSWERS, key=lambda e: hashlib.sha256(f"finwordle:order:{e.word}".encode()).hexdigest())


_CYCLE: list[WordEntry] = _shuffled_answers()


def daily_word(day: date) -> WordEntry:
    """
    The answer for a given calendar day, identical for every user.

    WHY A CYCLE RATHER THAN A HASH OF THE DATE
    This used to hash the date and take the result modulo the bank size,
    which samples WITH REPLACEMENT: over a year of 365 days and 96
    answers, one word came up nine times while two never appeared at all.
    Players notice a repeat inside a fortnight, and an expanded
    dictionary that still repeats defeats the point of expanding it.

    Walking a fixed permutation guarantees every answer appears once
    before any appears twice, so the bank size IS the repeat interval:
    96 answers means 96 days.
    """
    return _CYCLE[(day - EPOCH).days % len(_CYCLE)]


def practice_word(seed: str) -> WordEntry:
    """
    Answer for an unlimited-practice round. Seeded by the caller (session
    id) so a page refresh resumes the SAME puzzle rather than silently
    swapping the answer underneath a game already in progress.
    """
    digest = hashlib.sha256(f"finwordle:practice:{seed}".encode()).hexdigest()
    return ANSWERS[int(digest, 16) % len(ANSWERS)]


def is_solved(tiles: list[TileState]) -> bool:
    return all(t == "correct" for t in tiles)


def validate_guess(guess: str) -> tuple[bool, str | None]:
    """Return (ok, error_message). Kept separate so the API can 400 cleanly."""
    g = (guess or "").strip().upper()
    if len(g) != WORD_LENGTH:
        return False, f"Guess must be exactly {WORD_LENGTH} letters"
    if not g.isalpha():
        return False, "Guess must contain only letters"
    if not is_valid_guess(g):
        return False, f"{g} isn't in the FinWordle dictionary"
    return True, None


def emoji_grid(all_tiles: list[list[TileState]]) -> str:
    """The shareable result block. Reveals the pattern, never the word."""
    symbol = {"correct": "■", "present": "▣", "absent": "□"}
    return "\n".join("".join(symbol[t] for t in row) for row in all_tiles)


def score_for_round(won: bool, guesses_used: int) -> int:
    """
    Knowledge XP for a completed round. Solving in fewer guesses is worth
    more; a loss still returns a small amount because the post-game
    definition is the actual educational payload and we want it read.
    """
    if not won:
        return 10
    return {1: 100, 2: 80, 3: 65, 4: 50, 5: 40, 6: 30}.get(guesses_used, 30)


__all__ = [
    "EPOCH", "MAX_GUESSES", "WORD_LENGTH", "TileState",
    "score_guess", "keyboard_state", "daily_puzzle_index", "daily_word",
    "practice_word", "is_solved", "validate_guess", "emoji_grid",
    "score_for_round", "get_entry",
]
