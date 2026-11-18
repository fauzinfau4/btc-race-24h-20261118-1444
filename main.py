"""Mean-reversion + deep-dip + breakout bot for the make.fun BTC race
(btc-race-24h-20261118-1444).

Long-only, one position, full size. It buys on one of four edge-triggered
signals, all measured on closes:

  * FAST MEAN-REVERSION (new main leg): the close has fallen at least
    1.30% over the last 30 minutes. This is the lesson of rounds 1 and 2:
    deep-dip-only bots trade too rarely (round 1: 0 fills live; round 2:
    6 fills live). A sharp half-hour crash bounces fast: after the
    -238 bps / 30 min crash at bar 66 of this dev window the price
    recovered +162 bps within the hour. Exit at +1.00% target, -0.40%
    stop, or 20 bars.
  * RECOVERY (new second leg): the close has risen at least 0.40% off
    the lowest close of the last 10 bars while still down at least
    0.40% over the last 60 minutes. This catches the bounce after a
    slide has already bottomed, instead of buying while it is still
    falling. Exit at +0.80% target, -0.40% stop, or 20 bars.
  * DEEP DIP: the close is at least 1.50% below the highest close of the
    last 480 bars (8 hours). A multi-hour slide that deep is where the
    bigger bounces live. Exit on a TRAILING stop: once the position is
    up at least 0.50%, sell when the close falls 0.40% below the
    highest close since entry; a hard -0.80% stop or 90 bars also exits.
    The trailing exit matters: on round 2's window the first dip trade
    rode a +231 bps bounce, and a fixed +1.00% target left most of it
    behind.
  * BREAKOUT: the close has risen at least 2.30% over 30 minutes.
    Deliberately high: on both flat dev windows the biggest 30-minute
    rise is ~2.2% or less, so this leg stays silent on range days and
    only fires on a genuine trend day, where it rides the continuation.
    Exit at +3.00% target, -1.00% stop, or 120 bars.

A signal fires only on the bar it turns on (edge-triggered). While a
signal stays on, the bot does not re-enter after an exit. If two legs
fire on the same bar, the deep dip wins (the deeper signal), then the
fast mean-reversion, then the recovery, then the breakout.

No new entries after bar 1300: a trade opened in the last ~2 hours has
too little room to play out before the window-end flatten sells it at
whatever the close is, and on this dev window the dip trade opened at
bar 1388 lost -$14.73 that way. The cutoff costs nothing on either dev
window studied (their last good entries are at bar 1225 or earlier).

Exits are re-sent every bar while their reason holds, and the bot only
clears its in-position state when the account actually shows no position,
so a sell the market refuses is retried instead of stranding the
position, and a buy that never fills is dropped instead of leaving the
bot believing it holds something it does not. It sends no order while
warming up.

Fallback (the anti-zero-trades rule): if the bot has never held a
position by bar 1000, it buys and holds to the end of the window
(target +3.00%, stop -1.50%). A day with no signal at all is a steady
grind or a dead range; buying late still captures the drift, and it
guarantees the entry meets the race's minimum bar of at least 1 trade.
It never fires on a day where the main legs traded.

Everything is integer arithmetic on the closes the harness sent, no
floats, no randomness, no wall clock, no network, no files: two runs on
the same data produce byte-identical replies. Sizing is 100% of cash on
entry; the exit sells the whole position. max_slippage_bps is 150 on
every order, wide enough for the modelled slippage plus pool impact at
full size plus a normal open-vs-close gap, and tight enough to refuse a
fill that gapped far away from the close the decision was made on.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

# --- fast mean-reversion leg: close down this much over 30 minutes ---
MR_WINDOW = 30         # bars of lookback for the slide
MR_BPS = 130           # entry when the close fell this much over MR_WINDOW
MR_TARGET_BPS = 100    # sell when the close is this far above the entry close
MR_STOP_BPS = 40       # sell when the close is this far below the entry close
MR_MAX_HOLD = 20       # sell this many bars after entry at the latest

# --- recovery leg: close up this much off the 10-bar low, still down over 60m ---
REC_WINDOW = 10        # bars of lookback for the low
REC_BPS = 40           # entry when the close is this far above that low
REC_DOWN60_BPS = 40    # ... while still this far down over the last 60 bars
REC_TARGET_BPS = 80    # sell when the close is this far above the entry close
REC_STOP_BPS = 40      # sell when the close is this far below the entry close
REC_MAX_HOLD = 20      # sell this many bars after entry at the latest

# --- dip leg: close this far below the 480-bar rolling high ---
DIP_WINDOW = 480       # bars of lookback for the rolling high
DIP_BPS = 150          # entry when the close is this far under that high
DIP_TRAIL_BPS = 40     # trailing exit: sell this far below the best close since entry
DIP_MIN_GAIN_BPS = 50  # ... once the position is this far up
DIP_STOP_BPS = 80      # sell when the close is this far below the entry close
DIP_MAX_HOLD = 90      # sell this many bars after entry at the latest

# --- breakout leg: close up this much over 30 minutes ---
MOM_WINDOW = 30        # bars of lookback for the breakout signal
MOM_BPS = 230          # entry when the close rose this much over MOM_WINDOW
MOM_TARGET_BPS = 300   # sell when the close is this far above the entry close
MOM_STOP_BPS = 100     # sell when the close is this far below the entry close
MOM_MAX_HOLD = 120     # sell this many bars after entry at the latest

# --- fallback: buy-and-hold if nothing has traded by this bar ---
FALLBACK_BAR = 1000
FALLBACK_TARGET_BPS = 300
FALLBACK_STOP_BPS = 150

# --- no new entries after this bar: too little window left to play out ---
ENTRY_CUTOFF_BAR = 1300

MAX_SLIPPAGE_BPS = 150


class Bot:
    def __init__(self):
        self.closes = []          # closes seen so far, ints at price_scale 5
        self.in_position = False
        self.entry_close = 0      # close at the bar the position was decided on
        self.entry_bar = 0        # seq of the bar the position was decided on
        self.target_bps = 0       # exit target for the open position
        self.stop_bps = 0         # exit stop for the open position
        self.max_hold = 0         # exit hold for the open position
        self.prev_mr_on = False   # mean-reversion signal's state on the prev bar
        self.prev_rec_on = False  # recovery signal's state on the previous bar
        self.prev_dip_on = False  # dip signal's state on the previous bar
        self.prev_mom_on = False  # breakout signal's state on the previous bar
        self.ever_held = False    # a position has been held at least once
        self.exit_mode = "fixed"  # "fixed" target exit or "trail" trailing exit
        self.trail_bps = 0        # trailing exit distance (trail mode only)
        self.min_gain_bps = 0     # gain needed before the trail arms (trail mode)
        self.max_since_entry = 0  # highest close since entry (trail mode)

    def _bps_change(self, now, then):
        """(now - then) / then in basis points (integer division)."""
        return (now - then) * 10000 // then

    def on_batch(self, state, batch):
        bar = state.latest.get(SYMBOL)
        if bar is not None:
            self.closes.append(int(bar["c"]))
        closes = self.closes
        seq = state.seq

        holding = state.positions.get(SYMBOL)
        if holding is not None and holding.qty > 0:
            self.ever_held = True

        # Update the four signals' state on every bar, in or out of a
        # position, so an entry after an exit needs a fresh turn-on, never a
        # signal that was already on while the last trade was held.
        mr_on = rec_on = dip_on = mom_on = False
        fired_mr = fired_rec = fired_dip = fired_mom = False
        if len(closes) > MR_WINDOW:
            mr_on = (
                self._bps_change(closes[-1], closes[-1 - MR_WINDOW]) < -MR_BPS
            )
            fired_mr = mr_on and not self.prev_mr_on
            self.prev_mr_on = mr_on
        if len(closes) > max(REC_WINDOW, 60):
            low = closes[-REC_WINDOW]
            for c in closes[-REC_WINDOW + 1:]:
                if c < low:
                    low = c
            rec_on = (
                self._bps_change(closes[-1], low) >= REC_BPS
                and self._bps_change(closes[-1], closes[-61]) <= -REC_DOWN60_BPS
            )
            fired_rec = rec_on and not self.prev_rec_on
            self.prev_rec_on = rec_on
        if len(closes) > DIP_WINDOW:
            high = closes[-DIP_WINDOW]
            for c in closes[-DIP_WINDOW + 1:]:
                if c > high:
                    high = c
            dip_on = self._bps_change(closes[-1], high) < -DIP_BPS
            fired_dip = dip_on and not self.prev_dip_on
            self.prev_dip_on = dip_on
        if len(closes) > MOM_WINDOW:
            mom_on = (
                self._bps_change(closes[-1], closes[-1 - MOM_WINDOW]) > MOM_BPS
            )
            fired_mom = mom_on and not self.prev_mom_on
            self.prev_mom_on = mom_on

        if self.in_position:
            # The buy decided on entry_bar fills at the next bar's open. If
            # the position still is not there a bar later, the buy was
            # rejected (e.g. max_slippage on a gap): drop the stale state
            # instead of sitting on a position that does not exist.
            if seq > self.entry_bar and (holding is None or holding.qty <= 0):
                self.in_position = False
            else:
                close = closes[-1] if closes else None
                if close is not None and holding is not None and holding.qty > 0:
                    if close > self.max_since_entry:
                        self.max_since_entry = close
                    gain_bps = self._bps_change(close, self.entry_close)
                    exit_now = False
                    if self.exit_mode == "trail":
                        if (
                            gain_bps >= self.min_gain_bps
                            and self._bps_change(self.max_since_entry, close)
                            >= self.trail_bps
                        ):
                            exit_now = True
                    elif gain_bps >= self.target_bps:
                        exit_now = True
                    if (
                        gain_bps <= -self.stop_bps
                        or seq - self.entry_bar >= self.max_hold
                    ):
                        exit_now = True
                    if exit_now:
                        # Do not clear in_position here: if this sell is
                        # refused, the next batch still shows the position
                        # and the sell is sent again while its reason holds.
                        # in_position clears when the position is gone.
                        return [
                            {
                                "side": "sell",
                                "symbol": SYMBOL,
                                "qty": holding.qty,
                                "max_slippage_bps": MAX_SLIPPAGE_BPS,
                            }
                        ]
                return []

        # The position is gone (or was never there): a sell that filled, or
        # a buy that never filled, ends the open trade.
        self.in_position = False

        if state.warming_up:
            return []

        fallback = not self.ever_held and seq >= FALLBACK_BAR
        if (
            (fired_mr or fired_rec or fired_dip or fired_mom or fallback)
            and closes
            and seq <= ENTRY_CUTOFF_BAR
        ):
            amount = state.cash
            if amount >= 1_000_000:
                self.in_position = True
                self.entry_close = closes[-1]
                self.entry_bar = seq
                self.max_since_entry = closes[-1]
                if fallback:
                    self.exit_mode = "fixed"
                    self.target_bps = FALLBACK_TARGET_BPS
                    self.stop_bps = FALLBACK_STOP_BPS
                    self.max_hold = 10 ** 9
                elif fired_dip:
                    self.exit_mode = "trail"
                    self.trail_bps = DIP_TRAIL_BPS
                    self.min_gain_bps = DIP_MIN_GAIN_BPS
                    self.stop_bps = DIP_STOP_BPS
                    self.max_hold = DIP_MAX_HOLD
                elif fired_mr:
                    self.exit_mode = "fixed"
                    self.target_bps = MR_TARGET_BPS
                    self.stop_bps = MR_STOP_BPS
                    self.max_hold = MR_MAX_HOLD
                elif fired_rec:
                    self.exit_mode = "fixed"
                    self.target_bps = REC_TARGET_BPS
                    self.stop_bps = REC_STOP_BPS
                    self.max_hold = REC_MAX_HOLD
                else:
                    self.exit_mode = "fixed"
                    self.target_bps = MOM_TARGET_BPS
                    self.stop_bps = MOM_STOP_BPS
                    self.max_hold = MOM_MAX_HOLD
                return [
                    {
                        "side": "buy",
                        "symbol": SYMBOL,
                        "notional_quote_units": amount,
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    }
                ]
        return []


def main():
    bot = Bot()
    makefun_bars.run(bot.on_batch)


if __name__ == "__main__":
    main()
