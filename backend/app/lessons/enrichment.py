"""
app/lessons/enrichment.py
---------------------------
Attaches interactive elements to lessons that were authored before those
elements existed.

WHY NOT JUST EDIT THE LESSONS
The tier 1, 3 and 4 banks are thirty-two lessons of finished prose. Adding
a drill to a dozen of them by hand means touching a dozen large literals
for a two-line change each, and every one of those edits is a chance to
break a string that reads perfectly well today. Keeping the additions in
one table makes the whole enrichment pass reviewable in a single diff, and
makes it obvious which lessons have interactive content and which do not.

WHAT GOES HERE AND WHAT DOES NOT
Only additions that fit the lesson already written. A drill is worth
adding when the lesson teaches a calculation the reader should be able to
perform; an exercise is worth adding when the lesson is about a
RELATIONSHIP that is easier to feel by moving a slider than to read about.
Where neither is true the lesson is left alone — a drill bolted onto a
conceptual lesson is padding, and padding is worse than nothing because
it trains people to skip the interactive parts.

New lessons should carry their own interactive content inline (see
tier0_beginner_b.py). This file exists for the back-catalogue.
"""

from app.lessons.models import Exercise, NumericQuestion

# lesson_id -> exercises to append
EXERCISES: dict[str, list[Exercise]] = {

    "l004": [  # Why Diversification Stops Helping After ~20-30 Stocks
        Exercise(
            kind="drawdown_recovery",
            title="Why a concentrated loss is hard to undo",
            prompt=(
                "A position at 30% of the portfolio going to zero is a 30% drawdown. Read off the "
                "gain required to recover, then halve the position size and read it again. This "
                "asymmetry is the reason position limits exist."
            ),
            params={"loss_pct": 30},
        ),
    ],

    "l013": [  # Sequence-of-Returns Risk, Explained Simply
        Exercise(
            kind="compounding",
            title="The same average return, different order",
            prompt=(
                "Compounding is order-independent while you are only contributing. Add withdrawals "
                "and it stops being, which is the whole of sequence risk. Set a long horizon, then "
                "compare what a poor first decade does against a poor last one."
            ),
            params={"principal": 100000, "rate": 7, "years": 30},
        ),
    ],

    "i001": [  # Position Sizing: The Math That Matters More Than Stock Picking
        Exercise(
            kind="position_size",
            title="Size a position from the risk, not the conviction",
            prompt=(
                "Enter your account value, the fraction of it you are willing to lose on this idea, "
                "your entry and your stop. The share count falls out of those four numbers. Note "
                "that a tighter stop permits a LARGER position at identical risk: sizing is a "
                "function of distance to the stop, not of how much you like the trade."
            ),
            params={"account": 100000, "risk_pct": 1.0, "entry": 50, "stop": 45},
        ),
        Exercise(
            kind="risk_of_ruin",
            title="How often a positive edge still ends badly",
            prompt=(
                "Set a genuine edge, say 55% win rate, and raise the bet size. Watch the "
                "probability of ruin climb even though every individual bet is favourable. Betting "
                "too large turns a winning system into a losing one."
            ),
            params={"win_rate": 55, "bet_pct": 5, "trades": 200},
        ),
    ],

    "i004": [  # Expected Value: Why Win Rate Is a Misleading Statistic
        Exercise(
            kind="expected_value",
            title="Win rate against payoff",
            prompt=(
                "Start at a 70% win rate with a small average win and a large average loss, and "
                "read the expected value. Then invert it: a 35% win rate with a large payoff. Win "
                "rate on its own tells you nothing about whether a strategy makes money."
            ),
            params={"win_rate": 70, "avg_win": 1.0, "avg_loss": 3.0},
        ),
    ],

    "i006": [  # Interest Rates: The Gravity Behind Every Asset Price
        Exercise(
            kind="compounding",
            title="What a discount rate does to distant cash",
            prompt=(
                "Compounding forward and discounting back are the same operation reversed. Raise "
                "the rate and see how much more it changes a 30-year figure than a 3-year one: "
                "that difference is precisely why rate rises hit long-duration growth companies "
                "hardest."
            ),
            params={"principal": 1000, "rate": 5, "years": 30},
        ),
    ],
}


# lesson_id -> numeric drills to append
PRACTICE: dict[str, list[NumericQuestion]] = {

    "l001": [  # Why P/E Ratios Lie to You Across Sectors
        NumericQuestion(
            question="A company earns $3.20 per share and trades at $76.80. What is its P/E ratio?",
            answer=24.0, tolerance=0.3,
            unit="x",
            hint="Price divided by earnings per share.",
            explanation=(
                "$76.80 / $3.20 = 24x. On its own that number means nothing: 24x is expensive for a "
                "utility and cheap for a software company with the same growth. A P/E is only "
                "interpretable against a peer set and a growth rate."
            ),
        ),
    ],

    "l002": [  # What Beta Actually Measures (and Doesn't)
        NumericQuestion(
            question="A stock has a beta of 1.4. The market falls 10%. What is the expected move in the stock, as a percentage?",
            answer=-14.0, tolerance=0.3,
            unit="%",
            hint="Beta scales the market move. Give the answer as a negative number.",
            explanation=(
                "1.4 x -10% = -14%. This is an EXPECTATION from a historical relationship, not a "
                "prediction: the stock's own news can swamp it entirely, and beta itself is unstable "
                "across regimes."
            ),
        ),
    ],

    "l011": [  # Free Cash Flow Yield vs. Dividend Yield
        NumericQuestion(
            question="A company generates $480 million of free cash flow and has a market cap of $8 billion. What is its free cash flow yield, as a percentage?",
            answer=6.0, tolerance=0.1,
            unit="%",
            hint="Free cash flow divided by market capitalisation.",
            explanation=(
                "$480m / $8,000m = 6%. This is what the business generates for owners relative to what "
                "the market charges for it: a more complete picture than dividend yield, which shows "
                "only the portion management chose to pay out."
            ),
        ),
    ],

    "i002": [  # Discounted Cash Flow Without the False Precision
        NumericQuestion(
            question="A cash flow of $1,000 arrives in 5 years. At a 9% discount rate, what is its present value in dollars?",
            answer=649.93, tolerance=8,
            unit="$",
            hint="Divide by (1 + rate) raised to the number of years.",
            explanation=(
                "$1,000 / 1.09^5 = $649.93. Now note the sensitivity: at 11% it is $593. A two-point "
                "change in an assumption nobody can pin down moves the answer 9%, which is why a DCF "
                "output quoted to the cent is false precision."
            ),
        ),
    ],

    "i005": [  # What an Index Fund Actually Owns
        NumericQuestion(
            question="In a cap-weighted index, the top 7 holdings total $12 trillion of a $40 trillion index. What percentage is that?",
            answer=30.0, tolerance=0.5,
            unit="%",
            hint="Top holdings divided by total index value.",
            explanation=(
                "$12tn / $40tn = 30%. An investor holding 'five hundred companies' has roughly a third "
                "of their money in seven of them. That is not an argument against indexing, but it is "
                "not the diversification most people believe they bought."
            ),
        ),
    ],

    "a004": [  # Duration and Convexity
        NumericQuestion(
            question="A bond has modified duration of 7.2. Rates rise by 0.50%. What is the approximate price change, as a percentage?",
            answer=-3.6, tolerance=0.15,
            unit="%",
            hint="Duration times the rate change, with the opposite sign. Express the rate move in percentage points.",
            explanation=(
                "-7.2 x 0.50 = -3.6%. Duration is the linear approximation; convexity means the true "
                "fall is slightly smaller than this, and correspondingly a rate CUT gains slightly more "
                "than 3.6%. That asymmetry is convexity working in the holder's favour."
            ),
        ),
    ],

    "a006": [  # Why Backtested Sharpe Ratios Are Almost Always Overstated
        NumericQuestion(
            question="You test 40 independent strategies with no real edge, at a 5% significance level. How many do you expect to appear 'significant' by chance?",
            answer=2, tolerance=0.5,
            hint="A 5% false-positive rate applied across every independent test.",
            explanation=(
                "40 x 0.05 = 2. Testing many strategies and reporting the winner guarantees discoveries "
                "that are pure chance. This is why the number of strategies TRIED, which is almost never "
                "disclosed, matters as much as the result presented."
            ),
        ),
    ],

    "e001": [  # Value-at-Risk vs. Conditional VaR
        NumericQuestion(
            question="A portfolio has a 1-day 95% VaR of $40,000. On how many trading days in a 250-day year would you expect losses to EXCEED it?",
            answer=12.5, tolerance=1.0,
            unit="days",
            hint="95% confidence means the threshold is breached 5% of the time.",
            explanation=(
                "250 x 0.05 = 12.5 days. VaR is a threshold, not a worst case, and it is silent on how "
                "bad those 12.5 days get. That silence is exactly what conditional VaR exists to fill."
            ),
        ),
    ],
}


def enrich(lesson):
    """
    Return `lesson` with any registered interactive content appended.

    Appends rather than replaces, so a lesson that already carries its own
    exercises keeps them — the table is additive by design and a lesson
    authored with inline content is never silently overwritten by it.
    """
    ex = EXERCISES.get(lesson.id)
    pr = PRACTICE.get(lesson.id)
    if not ex and not pr:
        return lesson

    from dataclasses import replace
    return replace(
        lesson,
        exercises=list(lesson.exercises) + list(ex or []),
        practice=list(lesson.practice) + list(pr or []),
    )
