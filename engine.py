# engine.py -- the back-test loop. Decide on day t, fill at day t+1's OPEN (no look-ahead).
# Reference: Atharva Kulkarni

from account import Account

class Simulator:
    def __init__(self, bars, news, start_cash=10000.0, start_shares=0.0):
        self.bars = bars
        self.news = news
        self.start_cash = start_cash
        self.start_shares = start_shares

    def todays_inputs(self, t, use_prices, use_news):
        """What the agent is allowed to see on day t: today's bar and today's headlines."""
        bar = self.bars[t] if use_prices else None
        if use_news:
            headlines = self.news.get(t, [])
        else:
            headlines = None
        return bar, headlines

    def run(self, agent, name="Agent", use_prices=True, use_news=True, start_day=0):
        """One pass over the data: O(n). The agent is handed only today's bar.

        start_day = 0 : trade from the first day (as before).
        start_day > 0 : the days before it are first shown to the agent as a warm-up
                        (its orders are thrown away) so its moving averages and news
                        history are filled in; trading starts on start_day.
        """
        if start_day < 0 or start_day >= len(self.bars) - 1:
            raise ValueError("start day must be from 0 to " + str(len(self.bars) - 2))
        account = Account(self.start_cash, self.start_shares)
        for t in range(start_day):                       # warm-up: look, never trade
            bar, headlines = self.todays_inputs(t, use_prices, use_news)
            try:
                agent.decide(bar, headlines, account.cash, account.shares, None)
            except Exception:
                pass                                     # the real loop reports agent errors
        equity = [account.equity(self.bars[start_day]["close"])]
        trades = []
        last_response = None
        for t in range(start_day, len(self.bars) - 1):
            bar, headlines = self.todays_inputs(t, use_prices, use_news)
            try:
                order = agent.decide(bar, headlines, account.cash, account.shares,
                                     last_response)
            except Exception as error:            # a crashing agent must not kill the desk
                print("Agent error on day " + str(t) + ": " + str(error))
                order = ("HOLD", 0)
            fill = self.bars[t + 1]["open"]
            before = account.shares
            last_response = account.execute(order, fill)
            if account.shares > before:
                trades.append((t + 1, "BUY", fill))
            elif account.shares < before:
                trades.append((t + 1, "SELL", fill))
            equity.append(account.equity(self.bars[t + 1]["close"]))
        return {"name": name, "equity": equity, "trades": trades}
