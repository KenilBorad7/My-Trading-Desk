# agent.py -- the starting point. Rename this file to agent.py and build from here.
#
# This is a legal, complete agent. It does nothing (it holds every day), which is exactly
# what you want on day one: run it and the checks name what is missing, your group code
# (a FAIL) and your names (a warning). Fill both in and everything goes green, with one
# warning left: an agent that never has 10% of its money in shares is not placed.
# Everything else is built around this method.
#
#   python3 agent_unittest.py    protocol check, no data needed (on Windows: python)
#   python3 selfcheck.py         the same plus a real run on your group's market
#
# First, put your group code in the line below. It arrived by email at the group lock (a tutor can re-send it),
# and it looks like G07-4KQT. It is the line the checks read to know whose file this is,
# so they refuse to do much until it is there. It also decides which of the four training
# markets your report's self-check figures come from, which is why you never type a ticker
# anywhere; you build and test your agent on all four. Then replace the two lines under
# it: every member of your group, and the member who is this file's reference, the one who
# makes any live change to it at the interview.
#
# Keep agent.py, agent_unittest.py and selfcheck.py in the same folder.

GROUP_CODE = "G13-QXQJ"       # <- replace this with your group's code
# Group: <every member's full name, separated by commas>
# Reference: <the full name of this file's reference member>
#-------------------------------------------------------------------------------------------------------------------

# TradingAgent is the class that contains the agent's memory and trading decisions.

class TradingAgent:

    def __init__(self):                            # Store previous closing prices so the agent can calculate its own moving avg
        self.price_history = []

    def decide(self, bar, headlines, cash, shares, last_response):

        if bar is not None:                       
            close_price = bar["close"]                        # Get today's closing price from the market bar.
            self.price_history.append(close_price)            # Add today's closing price to the agent's memory.

        if len(self.price_history) < 5:                   # Wait until we have 5 closing prices before calculating the 5-day avg
            return ("HOLD", 0)

        recent_prices = self.price_history[-5:]              # Take the most recent 5 closing prices for the moving avg
        moving_average = sum(recent_prices) / 5

        current_price = self.price_history[-1]               # Get today's latest closing price.

        if current_price > moving_average:                   # If today's price is above the 5-day average, send a BUY order.
            return ("BUY", -1)

        elif current_price < moving_average:                 # If today's price is below the 5-day average, send a SELL order.
            return ("SELL", -1)

        else:                                                # If the price equals the moving average, do nothing.
            return ("HOLD", 0)

# temporarily
agent = TradingAgent()

prices = [100, 102, 104, 106, 108, 110]

for price in prices:
    bar = {"close": price}
    decision = agent.decide(bar, [], 10000, 0, None)
    print(price, decision)
    






















































