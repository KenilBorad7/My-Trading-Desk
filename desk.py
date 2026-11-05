# desk.py -- the trading desk: a text menu that owns the money and runs the agent.
# Start with:  python3 desk.py [start_cash] [start_shares]     (both optional)
# Reference: <full name>
import math
import sys

import analytics
import storage
from account import Account
from agent import TradingAgent
from engine import Simulator
from market_data import load_bars, load_news

DEFAULT_TICKER = "VOLT"
SESSION_FILE = "session.txt"
RESULTS_FILE = "results.txt"
LEADERBOARD_FILE = "leaderboard.txt"
MENU = """========== Glacial Pace Capital trading desk ==========
[1] Load dataset            [2] Set starting cash/shares
[3] Step one day            [4] Manual buy
[5] Manual sell             [6] Run agent to end
[7] Show price chart        [8] Show equity + drawdown
[9] Save / load             [0] Quit
================================================="""


def ask_number(prompt, default):
    """A number from the user, the default on a blank line, None if it is not a number."""
    text = input(prompt).strip()
    if text == "":
        return default
    try:
        value = float(text)
    except ValueError:
        print("That is not a number.")
        return None
    if not math.isfinite(value):
        print("That is not a usable number.")
        return None
    return value


class Desk:
    def __init__(self, start_cash=10000.0, start_shares=0.0):
        self.start_cash = start_cash
        self.start_shares = start_shares
        self.ticker = None
        self.bars = []
        self.news = {}
        self.day = 0
        self.account = Account(start_cash, start_shares)
        self.equity = []
        self.manual_trades = []
        self.run_result = None
        self.view = "manual"
        self.last_event = "none yet"

    # ---- state ----------------------------------------------------------
    def loaded(self):
        if self.ticker is None:
            print("Load a dataset first (option 1).")
            return False
        return True

    def price(self):
        return self.bars[self.day]["close"]

    def reset_session(self):
        self.day = 0
        self.account = Account(self.start_cash, self.start_shares)
        self.equity = [self.account.equity(self.price())]
        self.manual_trades = []
        self.run_result = None
        self.view = "manual"

    def current_result(self):
        if self.view == "agent" and self.run_result is not None:
            return self.run_result
        return {"name": "Manual on " + str(self.ticker), "equity": list(self.equity),
                "trades": list(self.manual_trades)}

    def status(self):
       # if self.ticker is None:
           # print("No dataset loaded.  Starting cash " + str(self.start_cash)
               #   + ", shares " + str(self.start_shares) + ".")
         #   return
        print("day " + str(self.day) + "/" + str(len(self.bars) - 1)
              + " | price " + str(round(self.price(), 2))
              + " | cash " + str(round(self.account.cash, 2))
              + " | shares " + str(round(self.account.shares, 2))
              + " | equity " + str(round(self.account.equity(self.price()), 2)))
        print("latest event: " + self.last_event)

    # ---- menu actions ---------------------------------------------------
    def load_market(self, ticker):
        try:
            bars = load_bars(ticker)
        except FileNotFoundError:
            print("Cannot find data/training/" + ticker + ".csv (run from the project folder).")
            return
        except ValueError as error:
            print("Bad data file: " + str(error))
            return
        self.bars = bars
        self.news = load_news(ticker)
        self.ticker = ticker
        self.reset_session()
        self.last_event = "loaded " + ticker
        print("Loaded " + ticker + " (" + str(len(bars)) + " days, "
              + str(len(self.news)) + " days with news).")

    def set_start(self):
        cash = ask_number("Starting cash [" + str(self.start_cash) + "]: ", self.start_cash)
        shares = ask_number("Starting shares [" + str(self.start_shares) + "]: ",
                            self.start_shares)
        if cash is None or shares is None:
            return
        if cash < 0 or shares < 0:
            print("Cash and shares cannot be negative.")
            return
        self.start_cash = cash
        self.start_shares = shares
        if self.ticker is not None:
            self.reset_session()
            print("Session restarted at day 0 with the new balances.")

    def step(self):
        if not self.loaded():
            return
        if self.day >= len(self.bars) - 1:
            print("Already at the last day.")
            return
        self.day = self.day + 1
        self.equity.append(self.account.equity(self.price()))
        self.view = "manual"
        self.last_event = "stepped to day " + str(self.day)

    def trade(self, action):
        if not self.loaded():
            return
        amount = ask_number("How many shares to " + action.lower()
                            + " (-1 = all/max) [-1]: ", -1.0)
        if amount is None:
            return
        if amount == 0 or amount < -1:
            print("Enter a positive number of shares, or -1 for all/max.")
            return
        before = self.account.shares
        reply = self.account.execute((action, amount), self.price())   # manual: today's close
        if self.account.shares > before:
            self.manual_trades.append((self.day, "BUY", self.price()))
        elif self.account.shares < before:
            self.manual_trades.append((self.day, "SELL", self.price()))
        self.equity[-1] = self.account.equity(self.price())
        self.view = "manual"
        self.last_event = action + " " + str(amount) + " -> " + reply
        print("-> " + reply)

    def run_agent(self):
        if not self.loaded():
            return
        sim = Simulator(self.bars, self.news, self.start_cash, self.start_shares)
        self.run_result = sim.run(TradingAgent(), "TradingAgent on " + self.ticker)
        self.view = "agent"
        self.last_event = "ran TradingAgent to the end"
        print("Ran TradingAgent on " + self.ticker + ":")
        analytics.print_summary(self.run_result)

    def show_price_chart(self):
        if self.loaded():
            analytics.plot_price_with_trades(self.bars, self.current_result())

    def show_equity_and_drawdown(self):
        if self.loaded():
            result = self.current_result()
            analytics.plot_equity(result)
            analytics.plot_drawdown(result)

    def save_or_load(self):
        choice = input("[s]ave or [l]oad? ").strip().lower()
        if choice == "s":
            self.save()
        elif choice == "l":
            self.load()
        else:
            print("Please type s or l.")

    def save(self):
        if not self.loaded():
            return
        try:
            storage.save_session(SESSION_FILE, self.ticker, self.day, self.account.cash,
                                 self.account.shares, self.start_cash, self.start_shares,
                                 self.equity, self.manual_trades)
            result = self.current_result()
            storage.append_result(RESULTS_FILE, result["name"], result["equity"][-1],
                                  len(result["trades"]))
            storage.write_leaderboard(RESULTS_FILE, LEADERBOARD_FILE)
        except OSError as error:
            print("Could not save: " + str(error))
            return
        print("Saved the session to " + SESSION_FILE + ".")
        print("Saved the run to " + RESULTS_FILE + " and the leaderboard to "
              + LEADERBOARD_FILE + ".")

    def load(self):
        try:
            data = storage.load_session(SESSION_FILE)
        except FileNotFoundError:
            print("No saved session yet (" + SESSION_FILE + ").")
            return
        except ValueError as error:
            print("Cannot load: " + str(error))
            return
        self.start_cash = data["start_cash"]
        self.start_shares = data.get("start_shares", 0.0)
        self.load_market(data["ticker"])
        if self.ticker != data["ticker"]:
            return
        if data["day"] < 0 or data["day"] > len(self.bars) - 1:
            print("Saved day is outside this dataset.")
            return
        self.day = data["day"]
        self.account = Account(data["cash"], data["shares"])
        self.equity = data["equity"] if len(data["equity"]) == self.day + 1 \
            else [self.account.equity(self.price())]
        self.manual_trades = data["trades"]
        self.last_event = "loaded session"
        print("Loaded session: " + self.ticker + " day " + str(self.day) + ".")
        rows = storage.read_leaderboard(LEADERBOARD_FILE)
        if rows:
            print("Leaderboard, best final equity first:")
            for row in rows:
                parts = row.split(",")
                print("  " + parts[0] + ". " + parts[1] + " " + parts[2])

    # ---- the menu loop (café-register pattern) --------------------------
    def run(self):
        print("Welcome. Starting cash " + str(self.start_cash) + ", shares "
              + str(self.start_shares) + ".")
        choice = ""
        while choice != "0":
            print(MENU)
            try:
                choice = input("Choose: ").strip()
            except EOFError:
                break
            if choice == "1":
                ticker = input("Ticker (VOLT, ZNTH, NOVA, QBIT) [" + DEFAULT_TICKER
                               + "]: ").strip().upper()
                self.load_market(ticker if ticker != "" else DEFAULT_TICKER)
            elif choice == "2":
                self.set_start()
            elif choice == "3":
                self.step()
            elif choice == "4":
                self.trade("BUY")
            elif choice == "5":
                self.trade("SELL")
            elif choice == "6":
                self.run_agent()
            elif choice == "7":
                self.show_price_chart()
            elif choice == "8":
                self.show_equity_and_drawdown()
            elif choice == "9":
                self.save_or_load()
            elif choice == "0":
                print("Goodbye.")
                break
            else:
                print("Please choose a number from the menu.")
            self.status()


def read_start(args):
    """Optional command-line balances; every one has a default."""
    cash = 10000.0
    shares = 0.0
    try:
        if len(args) > 1:
            cash = float(args[1])
        if len(args) > 2:
            shares = float(args[2])
    except ValueError:
        print("Ignoring unreadable starting balances; using the defaults.")
        return 10000.0, 0.0
    if cash < 0 or shares < 0 or not math.isfinite(cash) or not math.isfinite(shares):
        print("Ignoring unusable starting balances; using the defaults.")
        return 10000.0, 0.0
    return cash, shares


if __name__ == "__main__":
    start_cash, start_shares = read_start(sys.argv)
    Desk(start_cash, start_shares).run()
    Desk.load_market(DEFAULT_TICKER)      # start with ZNTH already loaded
    Desk.run()
