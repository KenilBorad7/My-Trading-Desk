# agent.py -- Glacial Pace Capital trading agent.
# One rule for each regime the competition runs: prices only, news only, prices + news.

GROUP_CODE = "G13-QXQJ"
# Group: Kenil Yogeshbhai Borad, Kulkarni Atharva, Sharma Nandini, Srivastava Devanshi, Kulkarni Aditya

# Reference: Kenil Yogeshbhai Borad

import math

FEE = 0.001

# Embedded sentiment lexicon: the 40 words from data/training/sentiment_words.csv.
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
    """One trading rule for each of the three regimes.

    PRICES ONLY:
        8/70-day moving averages, 0.80% entry spread, 0.50% downside
        spread, and 2.00% close breakdown. Invest 90% after a 2% next-open
        price buffer. Retain the 1% peak-equity stop and 20-call cooldown.

    NEWS ONLY:
        Use current-day sentiment. Buy at +1 or above; sell at -1 or below.
        Use 60 shares for +1 sentiment and 80 shares for +2 or stronger.
        After a currency rejection, halve the next news-only lot.

    PRICES + NEWS:
        Use current-day sentiment for entries and exits. Positive news can
        enter; negative news exits. The 12/30-day price signal is an exit
        filter while holding. Invest 40%, with the 10% equity stop and
        10-call cooldown.

    The three regimes are independent competition runs. Each decision uses
    only information supplied on the current or previous calls. The desk
    executes orders at the next day's open and applies the 0.1% fee.
    """

    # Strategy 1: prices only

    PRICE_SHORT = 8
    PRICE_LONG = 70

    PRICE_ONLY_ENTRY_GAP = 0.008
    PRICE_ONLY_EXIT_GAP = 0.005
    PRICE_ONLY_BREAKDOWN = 0.02

    PRICE_ONLY_INVEST = 0.90
    PRICE_ONLY_STOP = 0.99
    PRICE_ONLY_COOLDOWN = 20
    ORDER_PRICE_BUFFER = 1.02

    # Strategy 2: news only

    NEWS_DAYS = 1
    NEWS_ONLY_THRESHOLD = 1.0
    NEWS_ONLY_NORMAL_LOT = 60
    NEWS_ONLY_STRONG_LOT = 80
    NEWS_ONLY_STRONG_THRESHOLD = 2.0

    # Strategy 3: prices + news

    SHORT = 12
    LONG = 30

    COMBINED_ENTRY_GAP = 0.0025
    COMBINED_EXIT_GAP = 0.005
    COMBINED_BREAKDOWN = 0.01

    INVEST = 0.40

    # Risk and execution settings

    STOP = 0.90
    COOLDOWN = 10
    RETRY_SCALE = 0.50

    def __init__(self):
        self.closes = []
        self.moods = []
        self.peak = 0.0
        self.cooldown = 0

        self.lot = self.NEWS_ONLY_NORMAL_LOT
        self.retry_scale = 1.0
        self.news_currency_rejected = False

    # Indicators shared by the strategies

    # COMPLEXITY: the one optimization in the back-test (all comments, nothing runs here)
    #
    # The back-test loop in engine.py calls decide() once per day, and decide() calls
    # moving_averages(). So what this function costs per day decides the Big-O of the
    # whole back-test over n days.
    #
    # STEP 1 -- the slow version, O(n^2) over a whole run.
    # It walks the WHOLE price history on every call, so on day t it does t steps:
    # 1 + 2 + ... + n = about n * n / 2 steps for the run.
    #
    #   def moving_averages(self, short_window, long_window):
    #       count = len(self.closes)
    #       if count < long_window:
    #           return None, None, None
    #       short_total = 0.0
    #       long_total = 0.0
    #       for i in range(count):                  # every close seen so far, every day
    #           if i >= count - short_window:
    #               short_total = short_total + self.closes[i]
    #           if i >= count - long_window:
    #               long_total = long_total + self.closes[i]
    #       short_avg = short_total / short_window
    #       long_avg = long_total / long_window
    #       if long_avg <= 0:
    #           return None, None, None
    #       spread = (short_avg - long_avg) / long_avg
    #       return short_avg, long_avg, spread
    #
    # STEP 2 -- our version (below), O(n) over a whole run.
    # It slices only the last long_window closes, self.closes[-long_window:], so every
    # call adds up at most 30 numbers (70 in the prices-only run), however long the
    # run has been. Each day costs the same, so n days cost n times that: O(n).
    #
    # Same answers: both versions give the same final equity on VOLT, 19720.91.
    # Measured on VOLT repeated to longer markets (best of 3 runs each):
    #     days     slow (step 1)   ours (step 2)
    #      750       0.012 s         0.002 s
    #     1500       0.045 s         0.005 s
    #     3000       0.171 s         0.010 s
    #     6000       0.668 s         0.020 s
    # Doubling the days makes step 1 about 4 times slower (n^2) and ours about 2 times
    # slower (n), so the gap keeps growing as the market gets longer.
    def moving_averages(self, short_window, long_window):
        """Calculate simple moving averages and their relative spread."""

        if len(self.closes) < long_window:
            return None, None, None

        recent = self.closes[-long_window:]
        short_avg = sum(recent[-short_window:]) / short_window
        long_avg = sum(recent) / long_window

        if long_avg <= 0:
            return None, None, None

        spread = (short_avg - long_avg) / long_avg
        return short_avg, long_avg, spread

    def news_score(self, headlines):
        """Sum known lexicon scores from all headlines received today."""

        total = 0.0
        for line in headlines:
            for word in str(line).lower().split():
                word = word.strip(".,!?;:()[]{}\"'")
                if word in LEXICON:
                    total += LEXICON[word]
        return total

    def recent_news_total(self):
        """Return the configured recent sentiment total."""

        if not self.moods:
            return 0.0
        return sum(self.moods[-self.NEWS_DAYS:])

    # Strategy 1: prices only

    def price_only_signal(self):
        """Return +1 for entry, -1 for exit, or 0 to hold."""

        short_avg, long_avg, spread = self.moving_averages(
            self.PRICE_SHORT, self.PRICE_LONG
        )

        if short_avg is None:
            return 0

        close = self.closes[-1]

        if spread >= self.PRICE_ONLY_ENTRY_GAP and close > short_avg:
            return 1

        if (
            spread <= -self.PRICE_ONLY_EXIT_GAP
            or close <= long_avg * (1.0 - self.PRICE_ONLY_BREAKDOWN)
        ):
            return -1

        return 0

    # Strategy 2: news only

    def news_only_signal(self):
        """Use current-day sentiment and adjust the share lot by strength."""

        mood = self.recent_news_total()

        # Preserve a reduced lot on the decision immediately after rejection.
        if not self.news_currency_rejected:
            if mood >= self.NEWS_ONLY_STRONG_THRESHOLD:
                self.lot = self.NEWS_ONLY_STRONG_LOT
            else:
                self.lot = self.NEWS_ONLY_NORMAL_LOT
        else:
            self.lot = max(1, self.lot)

        if mood >= self.NEWS_ONLY_THRESHOLD:
            return 1

        if mood <= -self.NEWS_ONLY_THRESHOLD:
            return -1

        return 0

    # Strategy 3: prices + news

    def combined_price_signal(self):
        """Use the 12/30-day trend signal as an exit filter."""

        short_avg, long_avg, spread = self.moving_averages(
            self.SHORT, self.LONG
        )

        if short_avg is None:
            return 0

        close = self.closes[-1]

        if spread >= self.COMBINED_ENTRY_GAP and close > short_avg:
            return 1

        if (
            spread <= -self.COMBINED_EXIT_GAP
            or close <= long_avg * (1.0 - self.COMBINED_BREAKDOWN)
        ):
            return -1

        return 0

    def combined_news_signal(self):
        """Convert current-day sentiment into a directional signal."""

        mood = self.recent_news_total()

        if mood > 0:
            return 1
        if mood < 0:
            return -1
        return 0

    def combined_signal(self, holding):
        """News-led entry rule with a price-based exit filter."""

        news = self.combined_news_signal()
        trend = self.combined_price_signal()

        if news <= -1:
            return -1

        if holding and trend < 0 and news < 1:
            return -1

        if news >= 1:
            return 1

        return 0

    # The method the competition calls

    def decide(self, bar, headlines, cash, shares, last_response):
        """Return a legal BUY, SELL or HOLD order for the current regime."""

        close = None

        # Record today's observed closing price and/or news sentiment.
        if bar is not None:
            close = bar["close"]
            self.closes.append(close)

        if headlines is not None:
            self.moods.append(self.news_score(headlines))

        # Handle the desk's previous execution response.
        self.news_currency_rejected = False
        if last_response is not None:
            if str(last_response).startswith("REJECT currency"):
                if bar is None and headlines is not None:
                    self.lot = max(1, self.lot // 2)
                    self.news_currency_rejected = True
                else:
                    self.retry_scale = self.RETRY_SCALE

        # Advance cooldown once per decision call.
        if self.cooldown > 0:
            self.cooldown -= 1

        # Peak-equity protection is available in price-bearing regimes only.
        if close is not None:
            equity = cash + shares * close

            if shares <= 0:
                self.peak = equity
            elif equity > self.peak:
                self.peak = equity

            if headlines is None:
                stop_level = self.PRICE_ONLY_STOP
                stop_cooldown = self.PRICE_ONLY_COOLDOWN
            else:
                stop_level = self.STOP
                stop_cooldown = self.COOLDOWN

            if shares > 0 and equity < stop_level * self.peak:
                self.cooldown = stop_cooldown
                return ("SELL", -1)

        # Select the appropriate independent strategy.
        if headlines is None:
            score = self.price_only_signal()
        elif bar is None:
            score = self.news_only_signal()
        else:
            score = self.combined_signal(shares > 0)

        # Enter a new position.
        if (
            shares <= 0
            and score >= 1
            and self.cooldown == 0
            and cash > 0
        ):
            if close is None:
                # News-only: no price is available, so order a fixed share lot.
                return ("BUY", self.lot)

            if close > 0:
                if headlines is None:
                    allocation = self.PRICE_ONLY_INVEST
                    sizing_price = close * self.ORDER_PRICE_BUFFER
                else:
                    allocation = self.INVEST
                    sizing_price = close

                allocation *= self.retry_scale
                count = int(
                    cash * allocation / (sizing_price * (1.0 + FEE))
                )

                if count > 0 and math.isfinite(count):
                    self.retry_scale = 1.0
                    return ("BUY", count)

            return ("HOLD", 0)

        # Exit the entire position on a negative signal.
        if shares > 0 and score <= -1:
            return ("SELL", -1)

        return ("HOLD", 0)
