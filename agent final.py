
# agent.py -- Glacial Pace Capital trading agent.
# InsightX Experimental Version 15.
# Hybrid specialist strategies based on V14 and teammate's agent.
# Self-contained: imports only math. No files, no keyboard, deterministic.

GROUP_CODE = "G13-QXQJ"

import math

FEE = 0.001

# Embedded sentiment lexicon: the 40 words from
# data/training/sentiment_words.csv.
LEXICON = {
    "surge": 1.0, "rally": 1.0, "soar": 1.0, "gain": 1.0,
    "bullish": 1.0, "breakout": 1.0, "upgrade": 1.0,
    "beat": 1.0, "record": 1.0, "boom": 1.0,
    "jump": 1.0, "optimism": 1.0, "inflow": 1.0,
    "adoption": 1.0,

    "crash": -1.0, "plunge": -1.0, "slump": -1.0,
    "loss": -1.0, "bearish": -1.0, "selloff": -1.0,
    "downgrade": -1.0, "miss": -1.0, "fear": -1.0,
    "dump": -1.0, "drop": -1.0, "panic": -1.0,
    "outflow": -1.0, "ban": -1.0,

    "market": 0.0, "today": 0.0, "trading": 0.0,
    "report": 0.0, "analysts": 0.0, "session": 0.0,
    "investors": 0.0, "volume": 0.0, "update": 0.0,
    "outlook": 0.0, "token": 0.0, "exchange": 0.0,
}


class TradingAgent:
    """InsightX V15: hybrid specialist trading strategies.

    PRICE-ONLY:
        Uses V14's 8/70-day trend strategy.
        Requires a 0.80% positive spread.
        Invests 90% using a 2% next-open price buffer.
        Uses a 1% peak-equity stop and 20-call cooldown.

    NEWS-ONLY:
        Uses the teammate's current-day sentiment strategy.
        Buys at +1 or above and sells at -1 or below.
        Uses fixed 60-share orders.

    PRICE + NEWS:
        Uses the teammate's current-day news-led strategy.
        Uses 12/30-day moving averages as an exit filter.
        Invests 40% of available cash.

    Cash-sized orders receive a one-time reduced retry size
    following a currency rejection.
    """

    # =====================================================
    # STRATEGY 1: PRICE-ONLY (V14 APPROACH)
    # =====================================================

    PRICE_SHORT = 8
    PRICE_LONG = 70

    PRICE_ONLY_ENTRY_GAP = 0.008
    PRICE_ONLY_EXIT_GAP = 0.005
    PRICE_ONLY_BREAKDOWN = 0.02

    PRICE_ONLY_INVEST = 0.90
    PRICE_ONLY_STOP = 0.99
    PRICE_ONLY_COOLDOWN = 20

    # Buffer the sizing price to allow for a higher next-day open.
    ORDER_PRICE_BUFFER = 1.02

    # =====================================================
    # STRATEGY 2: NEWS-ONLY (TEAMMATE APPROACH)
    # =====================================================

    NEWS_DAYS = 1
    NEWS_ONLY_THRESHOLD = 1.0
    NEWS_ONLY_LOT = 60

    # =====================================================
    # STRATEGY 3: PRICE + NEWS (TEAMMATE APPROACH)
    # =====================================================

    SHORT = 12
    LONG = 30

    COMBINED_ENTRY_GAP = 0.0025
    COMBINED_EXIT_GAP = 0.005
    COMBINED_BREAKDOWN = 0.01

    INVEST = 0.40

    # =====================================================
    # GENERAL RISK AND EXECUTION SETTINGS
    # =====================================================

    STOP = 0.90
    COOLDOWN = 10

    # Used for the next cash-sized order after a currency rejection.
    RETRY_SCALE = 0.50

    def __init__(self):
        self.closes = []
        self.moods = []

        self.peak = 0.0
        self.cooldown = 0

        self.lot = self.NEWS_ONLY_LOT
        self.retry_scale = 1.0

    # =====================================================
    # MOVING-AVERAGE CALCULATION
    # =====================================================

    def moving_averages(self, short_window, long_window):
        """Calculate short and long moving averages."""

        if len(self.closes) < long_window:
            return None, None, None

        recent = self.closes[-long_window:]

        short_avg = sum(recent[-short_window:]) / short_window
        long_avg = sum(recent) / long_window

        if long_avg <= 0:
            return None, None, None

        spread = (short_avg - long_avg) / long_avg

        return short_avg, long_avg, spread

    # =====================================================
    # NEWS SENTIMENT CALCULATION
    # =====================================================

    def news_score(self, headlines):
        """Calculate the current day's sentiment."""

        total = 0.0

        for line in headlines:
            for word in str(line).lower().split():
                word = word.strip(".,!?;:()[]{}\"'")

                if word in LEXICON:
                    total += LEXICON[word]

        return total

    def recent_news_total(self):
        """Return sentiment over the configured news window."""

        if not self.moods:
            return 0.0

        return sum(self.moods[-self.NEWS_DAYS:])

    # =====================================================
    # STRATEGY 1: PRICE-ONLY
    # =====================================================

    def price_only_signal(self):
        """Dedicated 8/70-day trend-following strategy.

        BUY:
            Short average is at least 0.80% above long average.
            Closing price is above the short average.

        SELL:
            Short average is at least 0.50% below long average,
            or closing price is at least 2% below long average.
        """

        short_avg, long_avg, spread = self.moving_averages(
            self.PRICE_SHORT,
            self.PRICE_LONG
        )

        if short_avg is None:
            return 0

        close = self.closes[-1]

        if (
            spread >= self.PRICE_ONLY_ENTRY_GAP
            and close > short_avg
        ):
            return 1

        if (
            spread <= -self.PRICE_ONLY_EXIT_GAP
            or close <= long_avg * (1.0 - self.PRICE_ONLY_BREAKDOWN)
        ):
            return -1

        return 0

    # =====================================================
    # STRATEGY 2: NEWS-ONLY
    # =====================================================

    def news_only_signal(self):
        """React to current-day sentiment.

        BUY at +1 or above.
        SELL at -1 or below.
        Otherwise HOLD.
        """

        mood = self.recent_news_total()

        if mood >= self.NEWS_ONLY_THRESHOLD:
            return 1

        if mood <= -self.NEWS_ONLY_THRESHOLD:
            return -1

        return 0

    # =====================================================
    # STRATEGY 3: PRICE + NEWS
    # =====================================================

    def combined_price_signal(self):
        """Use the 12/30-day price signal as an exit filter."""

        short_avg, long_avg, spread = self.moving_averages(
            self.SHORT,
            self.LONG
        )

        if short_avg is None:
            return 0

        close = self.closes[-1]

        if (
            spread >= self.COMBINED_ENTRY_GAP
            and close > short_avg
        ):
            return 1

        if (
            spread <= -self.COMBINED_EXIT_GAP
            or close <= long_avg * (1.0 - self.COMBINED_BREAKDOWN)
        ):
            return -1

        return 0

    def combined_news_signal(self):
        """Convert current-day sentiment to a directional signal."""

        mood = self.recent_news_total()

        if mood > 0:
            return 1

        if mood < 0:
            return -1

        return 0

    def combined_signal(self, holding):
        """News-led entry strategy with price-based exit filtering."""

        news = self.combined_news_signal()
        trend = self.combined_price_signal()

        # Negative news: exit.
        if news <= -1:
            return -1

        # Exit a holding if the trend falls and news is not positive.
        if holding and trend < 0 and news < 1:
            return -1

        # Positive current-day news: enter.
        if news >= 1:
            return 1

        return 0

    # =====================================================
    # REQUIRED COMPETITION METHOD
    # =====================================================

    def decide(self, bar, headlines, cash, shares, last_response):

        close = None

        # Store today's closing price when price data is visible.
        if bar is not None:
            close = bar["close"]
            self.closes.append(close)

        # Store today's sentiment when news is visible.
        if headlines is not None:
            self.moods.append(self.news_score(headlines))

        # -------------------------------------------------
        # HANDLE REJECTED ORDERS
        # -------------------------------------------------

        if last_response is not None:
            if str(last_response).startswith("REJECT currency"):

                if bar is None and headlines is not None:
                    # News-only regime uses fixed share quantities.
                    self.lot = max(1, self.lot // 2)
                else:
                    # Reduce only the next cash-sized order.
                    self.retry_scale = self.RETRY_SCALE

        # -------------------------------------------------
        # UPDATE COOLDOWN
        # -------------------------------------------------

        if self.cooldown > 0:
            self.cooldown -= 1

        # -------------------------------------------------
        # EQUITY-BASED RISK CONTROL
        # -------------------------------------------------

        if close is not None:

            equity = cash + shares * close

            if shares <= 0:
                self.peak = equity
            elif equity > self.peak:
                self.peak = equity

            if headlines is None:
                # Price-only uses its dedicated tighter stop.
                stop_level = self.PRICE_ONLY_STOP
                stop_cooldown = self.PRICE_ONLY_COOLDOWN
            else:
                # Combined strategy retains the original stop.
                stop_level = self.STOP
                stop_cooldown = self.COOLDOWN

            if shares > 0 and equity < stop_level * self.peak:
                self.cooldown = stop_cooldown
                return ("SELL", -1)

        # -------------------------------------------------
        # SELECT INFORMATION REGIME
        # -------------------------------------------------

        if headlines is None:
            # PRICE-ONLY
            score = self.price_only_signal()

        elif bar is None:
            # NEWS-ONLY
            score = self.news_only_signal()

        else:
            # PRICE + NEWS
            score = self.combined_signal(shares > 0)

        # -------------------------------------------------
        # ENTER POSITION
        # -------------------------------------------------

        if (
            shares <= 0
            and score >= 1
            and self.cooldown == 0
            and cash > 0
        ):

            if close is None:
                # News-only: price is unavailable.
                return ("BUY", self.lot)

            if close > 0:

                if headlines is None:
                    # V14-style price-only sizing.
                    allocation = self.PRICE_ONLY_INVEST
                    sizing_price = close * self.ORDER_PRICE_BUFFER
                else:
                    # Teammate's combined allocation.
                    allocation = self.INVEST
                    sizing_price = close

                allocation *= self.retry_scale

                count = int(
                    cash * allocation /
                    (sizing_price * (1.0 + FEE))
                )

                if count > 0 and math.isfinite(count):
                    # The reduced scale applies to one order only.
                    self.retry_scale = 1.0
                    return ("BUY", count)

            return ("HOLD", 0)

        # -------------------------------------------------
        # EXIT ENTIRE POSITION
        # -------------------------------------------------

        if shares > 0 and score <= -1:
            return ("SELL", -1)

        return ("HOLD", 0)
