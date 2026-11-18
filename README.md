[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/fauzinfau4/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/fauzinfau4/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

# BTC race bot — crash bounce + recovery + trailing deep-dip

Entry for **btc-race-24h-20261118-1444** ("Race a BTC trading bot live for
24 hours", make.fun). Long-only cbBTC bot, Python 3.13, standard library
only plus the vendored `makefun_bars.py` SDK shim (byte-identical copy of
the kit's `sdk/makefun_bars.py`).

## How it trades

- **Fast mean-reversion:** buy when the close falls ≥1.30% over 30
  minutes; exit at +1.00% / −0.40% / 20 bars.
- **Recovery:** buy when the close rises ≥0.40% off the lowest close of
  the last 10 bars while still down ≥0.40% over 60 minutes; exit at
  +0.80% / −0.40% / 20 bars.
- **Deep dip:** buy when the close is ≥1.50% below the highest close of
  the last 480 bars (8h); exit on a trailing stop (sell 0.40% below the
  best close since entry, once up ≥0.50%), hard stop −0.80%, or 90 bars.
- **Breakout:** buy when the close rises ≥2.30% over 30 minutes; exit at
  +3.00% / −1.00% / 120 bars. Silent on flat days by design.
- **Fallback:** if it has never held a position by bar 1000, buy and hold
  to the end — so it can never repeat the round-1 live-race failure of
  zero fills.
- **Entry cutoff:** no new entries after bar 1300, so no trade is opened
  too late to play out before the window-end flatten.
- Full size (100% of cash), one position, max slippage 150 bps, integer
  arithmetic only — two runs on the same data produce byte-identical
  orders.

See [STRATEGY.md](STRATEGY.md) for the full reasoning, the round-1/2
lessons, and the per-trade results.

## Dev-window results (local replay, exact fill model)

The kit's `grade-local` cannot run a Python bot on this VM (its process
driver runs Node only and there is no Docker here), so the bot was graded
with a local replay driver that implements the harness's fill model
exactly as `sim/bars/engine.ts` documents it. The driver was validated by
reproducing the round-2 bot's official dev grade byte for byte: **+$15.03,
8 fills, maxDD 0.97%** on its own window, matching its STRATEGY.md.

| Window | Net PnL | Trades (fills) | Max drawdown |
|---|---|---|---|
| Dev 2026-11-17/18 (this competition) | **+$11.27** | 6 | 0.62% |
| Round-2 dev window 2026-11-16/17 | **+$20.89** | 8 | 1.31% |

For comparison, the round-2 bot scores **−$12.68** on this competition's
dev window and would fail the dev gate there. This bot clears the gate
(net PnL > $0) on both windows, with every round trip profitable on this
window. Determinism was verified by running the bot twice on the dev
data and diffing the replies: byte-identical on both windows.

## Files

- `main.py` — the bot (entrypoint)
- `vendor/makefun_bars.py` — kit SDK shim, byte-identical copy
- `STRATEGY.md` — strategy write-up, round-1/2 lessons, per-trade results
- `LICENSE` — MIT
