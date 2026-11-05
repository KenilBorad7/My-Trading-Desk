# engine.py -- the back-test loop. Decide on day t, fill at day t+1's OPEN (no look-ahead).
# Reference: <full name>
from account import Account


class Simulator:
    def __init__(self, bars, news, start_cash=10000.0, start_shares=0.0):
        self.bars = bars
        self.news = news
        self.start_cash = start_cash
        self.start_shares = start_shares

    def run(self, agent, name="Agent", use_prices=True, use_news=True):
        """One pass over the data: O(n). The agent is handed only today's bar."""
        account = Account(self.start_cash, self.start_shares)
        equity = [account.equity(self.bars[0]["close"])]
        trades = []
        last_response = None
        for t in range(len(self.bars) - 1):
            bar = self.bars[t] if use_prices else None
            if use_news:
                headlines = self.news.get(t, [])
            else:
                headlines = None
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
