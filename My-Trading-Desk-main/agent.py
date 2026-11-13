# agent.py -- Glacial Pace Capital trading agent (competition entry).
# Self-contained: imports only math. No files, no keyboard, deterministic.

GROUP_CODE = "G13-QXQJ"
# Group: <every member's full name, separated by commas>
# Reference: <the full name of this file's reference member>

import math

FEE = 0.001

# Embedded sentiment lexicon: the 40 words of data/training/sentiment_words.csv, copied
# in by hand because agent.py may not read files (agent contract, section 2).
# Week-4 pattern: split a headline, look each word up, sum the scores.
LEXICON = {
    "surge": 1.0, "rally": 1.0, "soar": 1.0, "gain": 1.0, "bullish": 1.0,
    "breakout": 1.0, "upgrade": 1.0, "beat": 1.0, "record": 1.0, "boom": 1.0,
    "jump": 1.0, "optimism": 1.0, "inflow": 1.0, "adoption": 1.0,
    "crash": -1.0, "plunge": -1.0, "slump": -1.0, "loss": -1.0, "bearish": -1.0,
    "selloff": -1.0, "downgrade": -1.0, "miss": -1.0, "fear": -1.0, "dump": -1.0,
    "drop": -1.0, "panic": -1.0, "outflow": -1.0, "ban": -1.0,
   # neutral words (score 0.0), kept so the table matches the file
    "market": 0.0, "today": 0.0, "trading": 0.0, "report": 0.0, "analysts": 0.0,
    "session": 0.0, "investors": 0.0, "volume": 0.0, "update": 0.0, "outlook": 0.0,
    "token": 0.0, "exchange": 0.0,
}


class TradingAgent:
    """Three rules, one per information regime:
    OHLCV-only -> 10/30-day trend;  news-only -> 3-day news mood;
    both visible -> combined_signal() (news enters, news or trend can exit).

    The signal votes +1 / -1 / 0. Enter when it is +1, leave when it is -1, otherwise keep
    the current position (hysteresis = few trades = few fees). Risk control: invest only
    part of the equity, and a stop-loss that sells everything and sits out for a
    cool-down, so equity stays well clear of the "falls to half its best" gate. On the
    training markets the trend rule alone lost money, so news always leads entries.
    """

    SHORT = 10          # short moving-average window (days)
    LONG = 30           # long moving-average window (days)
    NEWS_DAYS = 3       # days of headlines summed into the mood
    INVEST = 0.4        # fraction of equity put into shares when a bar is visible
    STOP = 0.90         # sell all if equity falls below this share of its peak
    NEWS_ONLY_LOT = 40  # shares per buy when no price is visible (about 40% at ~100)
    COOLDOWN = 10       # days to stay out after a stop-loss

    def __init__(self):
        self.closes = []        # only today's close is added each day
        self.moods = []         # one news score per day
        self.peak = 0.0         # highest equity since entry
        self.cooldown = 0
        self.lot = self.NEWS_ONLY_LOT

    # ---- helpers ---------------------------------------------------------
    def news_score(self, headlines):
        total = 0.0
        for line in headlines:
            for word in str(line).lower().split():
                if word in LEXICON:
                    total = total + LEXICON[word]
        return total

    def price_signal(self):
        if len(self.closes) < self.LONG:
            return 0
        recent = self.closes[-self.LONG:]               # fixed-size slice: O(1) per day
        short_avg = sum(recent[-self.SHORT:]) / self.SHORT
        long_avg = sum(recent) / self.LONG
        if short_avg > long_avg:
            return 1
        if short_avg < long_avg:
            return -1
        return 0

    def news_signal(self):
        if len(self.moods) == 0:
            return 0
        mood = sum(self.moods[-self.NEWS_DAYS:])
        if mood > 0:
            return 1
        if mood < 0:
            return -1
        return 0

    def combined_signal(self, holding):
        """News + price together (used when both are visible).

        News decides when to ENTER (bullish mood = buy). Either signal can make us LEAVE:
        bearish news, or a downtrend (10-day average under the 30-day) while the news is
        not bullish. Returns +1 buy / -1 sell / 0 no change.
        """
        news = self.news_signal()
        trend = self.price_signal()
        if news <= -1:
            return -1                       # bad news: out
        if holding and trend < 0 and news < 1:
            return -1                       # price trend has turned down: out
        if news >= 1:
            return 1                        # good news: in
        return 0

    # ---- the one method the contract requires ----------------------------
    def decide(self, bar, headlines, cash, shares, last_response):
        close = None
        if bar is not None:
            close = bar["close"]
            self.closes.append(close)
        if headlines is not None:
            self.moods.append(self.news_score(headlines))

        if last_response is not None and str(last_response).startswith("REJECT currency"):
            self.lot = max(1, self.lot // 2)            # lot too big for the cash: halve it

        if self.cooldown > 0:
            self.cooldown = self.cooldown - 1

        # Stop-loss (needs prices to value the shares).
        if close is not None:
            equity = cash + shares * close
            if shares <= 0:
                self.peak = equity
            elif equity > self.peak:
                self.peak = equity
            if shares > 0 and equity < self.STOP * self.peak:
                self.cooldown = self.COOLDOWN
                return ("SELL", -1)

        if headlines is None:
            score = self.price_signal()                 # OHLCV-only run: trend rule
        elif bar is None:
            score = self.news_signal()                  # news-only run: news rule
        else:
            score = self.combined_signal(shares > 0)    # both visible: news + price

        if shares <= 0 and score >= 1 and self.cooldown == 0 and cash > 0:
            if close is None:
                return ("BUY", self.lot)                # news-only: price unseen, fixed lot
            count = int(cash * self.INVEST / (close * (1.0 + FEE)))
            if count > 0 and math.isfinite(count):
                return ("BUY", count)
            return ("HOLD", 0)

        if shares > 0 and score <= -1:
            return ("SELL", -1)

        return ("HOLD", 0)
