# Strategy: crash bounce + recovery + trailing deep-dip

## Why the previous bots failed, and what changed

- **Round 1 (btc-race-24h-20261115-0828):** passed dev grade (+$36.61)
  then made **zero fills in the live 24h race** (equity flat $1,000, rank
  1749/2828, $0). Cause: signal rarity — its entries needed a ±2.00%
  move over 30–45 minutes, and a flat day never produces one.
- **Round 2 (btc-race-24h-20261117-0603):** fixed the rarity part-way with
  a deep-dip leg (1.50% below the 8-hour high) and a fallback. It passed
  dev grade (+$15.03, 8 fills) and finished the live race rank 51/4387,
  equity +$16.48, but only **6 fills** in 24 hours — the deep dip still
  fires rarely, and the breakout leg (2.30% over 30 minutes) never fired
  on either flat dev window. Re-run on *this* competition's dev window
  it scores **−$12.68 and fails the dev gate**: its two dip trades were
  +$1.88 and −$14.56, the second bought at bar 1388 and sold into the
  window-end slide.

This bot keeps the deep-dip and breakout legs, but adds two legs that
fire on ordinary multi-hour slides, and fixes the two leaks round 2
showed: a trailing exit for the dip leg, and an entry cutoff so no trade
opens too late to play out.

## The market as the dev window shows it

The dev window (1,440 one-minute cbBTC bars, 2026-11-17 14:44Z to
2026-11-18 14:44Z) is a grinding downtrend: −281 bps drift, range
63,076–65,189 (+335 bps), median |1-minute move| ~2 bps. A full-size
round trip costs ~26 bps (4 bps fee + 2 bps slippage + ~7 bps pool
impact per leg), so scalping the noise is a guaranteed loss. There are
only five troughs in the whole day whose next-hour bounce reaches
+80 bps or more (+162, +91, +119, +90, +111 bps). The biggest (+162)
follows a −238 bps / 30 min crash. Forward-return analysis: after a
−100 bps / 30 min slide the next 30 minutes average +40 bps (median
+46); after a −150 bps / 120 min slide the next 60 minutes average
+23 bps; but 30-minute *rises* reverse hard (after +100 bps / 30 min
the next 30 minutes average −77 bps) — so breakouts must stay
untradably high on a day like this, and dip-buying must exit fast
before the downtrend reasserts itself.

## What the bot does

Long only, one position, full size (100% of cash), edge-triggered entries
(a signal fires only on the bar it turns on):

- **Fast mean-reversion:** the close has fallen at least **1.30% over
  30 minutes**. Only a crash this sharp is bought blind: looser
  thresholds (−0.70% to −0.90%) buy into slides that keep falling and
  lose on both dev windows. Exit at +1.00% target, −0.40% stop, or
  20 bars.
- **Recovery:** the close has risen at least **0.40% off the lowest
  close of the last 10 bars** while still down at least **0.40% over
  60 minutes**. This buys the bounce after the slide has bottomed,
  instead of while it is still falling. Exit at +0.80% target, −0.40%
  stop, or 20 bars.
- **Deep dip:** the close is at least **1.50% below the highest close of
  the last 480 bars (8 hours)**. Exit on a **trailing stop**: once the
  position is up at least 0.50%, sell when the close falls 0.40% below
  the highest close since entry; a hard −0.80% stop or 90 bars also
  exits. The trailing exit is worth +$5.86 on round 2's window versus
  the fixed +1.00% target (the first dip trade there rode a +231 bps
  bounce and the fixed target left most of it behind).
- **Breakout:** the close has risen at least **2.30% over 30 minutes**.
  Deliberately above both dev windows' biggest 30-minute rise, so it
  stays silent on range days and only fires on a genuine trend day.
  Exit at +3.00% target, −1.00% stop, or 120 bars.
- **Fallback:** if the bot has never held a position by bar 1000, it buys
  and holds to the end (target +3.00%, stop −1.50%). It never fires on a
  day where the main legs traded.
- **Entry cutoff:** no new entries after bar 1300. A trade opened in the
  last ~2 hours has too little room before the window-end flatten, and
  on this window the dip trade opened at bar 1388 lost −$14.73. The
  cutoff costs nothing on either dev window (their last good entries
  are at bar 1225 or earlier), and the 1250–1350 range gives identical
  results on both windows, so it is a plateau, not a tuned edge.

Priority when two legs fire on the same bar: deep dip, then
mean-reversion, then recovery, then breakout.

Exits are re-sent every bar while their reason holds, and the bot only
clears its in-position state when the account actually shows no position,
so a sell the market refuses is retried instead of stranding the
position, and a buy that never fills is dropped instead of leaving the
bot believing it holds something it does not. It sends no order while
warming up.

## Dev-window results (local replay, exact fill model)

The kit's `grade-local --driver process` runs Node bots only and this VM
has no Docker, so the bot was graded with a local replay driver that
implements the harness fill model exactly as `sim/bars/engine.ts`
documents it (fee 4 bps, slippage 2 bps, constant-product impact
1 + a/D, max-slippage checks, end-of-window flatten at the last close).
The driver was validated by reproducing round 2's official dev grade
exactly: +$15.03, 8 fills, maxDD 0.97% on its own window, with the same
per-trade PnLs its STRATEGY.md reports. Determinism was checked by
running the bot twice on each window and diffing the full reply streams:
byte-identical in both cases.

### This competition's dev window (2026-11-17/18)

Net PnL **+$11.27** on $1,000 start (+1.13%), **6 fills (3 round trips)**,
max drawdown **0.62%**. Every round trip profitable:

| Entry bar | Leg | Exit | PnL |
|---|---|---|---|
| 65 | mean-reversion (crash −238 bps/30m) | target +1.00% | +$7.90 |
| 135 | recovery | target +0.80% | +$1.49 |
| 678 | deep dip | trailing exit | +$1.87 |

Round 2's bot on the same window: −$12.68, 4 fills — it fails the dev
gate here. This bot beats it by $23.95 on this window.

### Round-2 dev window (2026-11-16/17, robustness check)

Net PnL **+$20.89** (+2.09%), **8 fills (4 round trips)**, max drawdown
**1.31%**, versus round 2's bot's +$15.03 on its own window:

| Entry bar | Leg | Exit | PnL |
|---|---|---|---|
| 486 | deep dip | trailing exit | +$15.57 |
| 549 | deep dip | stop −0.80% | −$0.83 |
| 1099 | deep dip | trailing exit | +$1.80 |
| 1224 | deep dip | trailing exit | +$4.35 |

## Robustness notes

- The parameter region is a plateau, not a spike: neighbouring settings
  give the same or near-identical results on both windows (dip trailing
  25–40 bps with min-gain 50–80 bps; recovery target 60–80 bps, stop
  40–60 bps; entry cutoff anywhere 1250–1350).
- Settings that were tried and rejected, because they lose on one or both
  windows: mean-reversion thresholds −0.70% to −1.10% (buy into falling
  slides); a 120-minute-slide leg (−150 bps/120m, −$14 on this window);
  a range-low leg (buy near the 120/240-bar low, negative on both
  windows); dip thresholds −1.00%/−1.25% (too many losing dips); no
  entry cutoff (the bar-1388 dip trade, −$14.73).
- Honest limits: on this window the bot makes +$11.27, below round 2's
  +$15.03 *on round 2's own window* — this dev window is a −281 bps
  downtrend with only five ≥+80 bps bounces in 24 hours, and no
  long-only strategy can manufacture trades that are not there. What it
  does do is clear the dev gate with margin on both regimes studied
  (+$11.27 here, +$20.89 there), while the round-2 bot fails the gate
  on this window outright. The race window is a new, unseen day: the
  breakout leg is the insurance for a trend day, the dip and recovery
  legs for a range day.

## What it does not do

No shorting, no leverage, no averaging down, no Martingale, no re-entry
into a signal that is already on, no trading on 1-minute noise. If the
race window trends, the breakout leg catches it; if it ranges, the dip
and recovery legs trade the slides; if it does neither, the fallback
still trades.
