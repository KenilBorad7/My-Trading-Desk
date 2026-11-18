# gui.py -- the optional graphical face of the trading desk (tkinter).
# It follows desk.py step for step: the same rules, the same messages, the same files.
# Reference: Atharva Kulkarni

import math
import tkinter as tk

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
TICKERS = ("VOLT", "ZNTH", "NOVA", "QBIT")
FONT = "Arial"


def read_number(text):
    """A number from an entry box, or None if it is not a usable number (like ask_number)."""
    try:
        value = float(text.strip())
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


class TradingDeskGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("InsightX - Glacial Pace Capital Trading Desk")
        self.root.geometry("760x640")
        self.root.minsize(700, 600)

        # The same manual-session state as Desk in desk.py.
        self.start_cash = 10000.0
        self.start_shares = 0.0
        self.ticker = None
        self.bars = []
        self.news = {}
        self.day = 0
        self.account = Account(self.start_cash, self.start_shares)
        self.equity = []
        self.manual_trades = []
        self.run_result = None
        self.view = "manual"
        self.last_event = "none yet"

        # Text shown in the window; changing one of these updates its label.
        self.market_text = tk.StringVar(value="Market: not loaded")
        self.day_text = tk.StringVar(value="Day: -")
        self.price_text = tk.StringVar(value="Price: -")
        self.cash_text = tk.StringVar(value="Cash: -")
        self.shares_text = tk.StringVar(value="Shares: -")
        self.equity_text = tk.StringVar(value="Equity: -")
        self.agent_text = tk.StringVar(value="Not run yet.")
        self.event_text = tk.StringVar(value="Latest event: none yet")
        self.message_text = tk.StringVar(value="Choose a market to begin.")
        self.leaderboard_text = tk.StringVar(value="Leaderboard: no saved runs yet.")

        self.build_window()
        self.load_market(DEFAULT_TICKER)
        self.refresh_leaderboard()

    # The window
    def build_window(self):
        tk.Label(self.root, text="INSIGHTX | TRADING DESK",
                 font=(FONT, 18, "bold")).pack(pady=(12, 0))
        tk.Label(self.root, text="Glacial Pace Capital trading simulator",
                 font=(FONT, 10)).pack(pady=(0, 8))

        # Market buttons
        row = tk.Frame(self.root)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text="Market:", font=(FONT, 10, "bold")).pack(side="left")
        for ticker in TICKERS:
            tk.Button(row, text=ticker, width=7,
                      command=lambda name=ticker: self.load_market(name)).pack(side="left", padx=3)
        tk.Label(row, textvariable=self.market_text).pack(side="right")

        # Account: the status line, then the starting balances
        box = tk.LabelFrame(self.root, text=" Manual account ", font=(FONT, 10, "bold"))
        box.pack(fill="x", padx=16, pady=6)
        status = tk.Frame(box)
        status.pack(fill="x", padx=8, pady=4)
        for column, variable in enumerate((self.day_text, self.price_text, self.cash_text,
                                           self.shares_text, self.equity_text)):
            tk.Label(status, textvariable=variable, anchor="w").grid(row=0, column=column,
                                                                     sticky="w", padx=(0, 18))
        row = tk.Frame(box)
        row.pack(fill="x", padx=8, pady=(2, 8))
        tk.Label(row, text="Starting cash:").pack(side="left")
        self.start_cash_entry = tk.Entry(row, width=10)
        self.start_cash_entry.insert(0, "10000")
        self.start_cash_entry.pack(side="left", padx=(4, 12))
        tk.Label(row, text="Starting shares:").pack(side="left")
        self.start_shares_entry = tk.Entry(row, width=8)
        self.start_shares_entry.insert(0, "0")
        self.start_shares_entry.pack(side="left", padx=4)
        tk.Button(row, text="Set / reset balances",
                  command=self.set_start).pack(side="left", padx=10)

        # Trading: Step n days, then manual buy and sell
        box = tk.LabelFrame(self.root, text=" Trade by hand ", font=(FONT, 10, "bold"))
        box.pack(fill="x", padx=16, pady=6)
        row = tk.Frame(box)
        row.pack(fill="x", padx=8, pady=4)
        tk.Label(row, text="Days to step:").pack(side="left")
        self.days_entry = tk.Entry(row, width=6)
        self.days_entry.insert(0, "1")
        self.days_entry.pack(side="left", padx=4)
        tk.Button(row, text="Step n days", width=12, command=self.step).pack(side="left", padx=6)
        row = tk.Frame(box)
        row.pack(fill="x", padx=8, pady=(2, 8))
        tk.Label(row, text="Shares (-1 = all/max):").pack(side="left")
        self.shares_entry = tk.Entry(row, width=8)
        self.shares_entry.insert(0, "-1")
        self.shares_entry.pack(side="left", padx=4)
        tk.Button(row, text="Buy", width=10,
                  command=lambda: self.trade("BUY")).pack(side="left", padx=6)
        tk.Button(row, text="Sell", width=10,
                  command=lambda: self.trade("SELL")).pack(side="left")

        # The agent
        box = tk.LabelFrame(self.root, text=" Agent back-test ", font=(FONT, 10, "bold"))
        box.pack(fill="x", padx=16, pady=6)
        row = tk.Frame(box)
        row.pack(fill="x", padx=8, pady=4)
        tk.Button(row, text="Run agent from day 0",
                  command=lambda: self.run_agent(False)).pack(side="left")
        tk.Button(row, text="Run agent from today (current cash and shares)",
                  command=lambda: self.run_agent(True)).pack(side="left", padx=8)
        tk.Label(box, textvariable=self.agent_text, justify="left",
                 anchor="w").pack(fill="x", padx=8, pady=(2, 8))

        # Charts, saving, quitting
        row = tk.Frame(self.root)
        row.pack(fill="x", padx=16, pady=6)
        tk.Label(row, text="Charts:", font=(FONT, 10, "bold")).pack(side="left")
        tk.Button(row, text="Price + trades", command=self.show_price_chart).pack(side="left", padx=4)
        tk.Button(row, text="Equity", command=self.show_equity_chart).pack(side="left", padx=4)
        tk.Button(row, text="Drawdown", command=self.show_drawdown_chart).pack(side="left", padx=4)
        tk.Button(row, text="Quit", width=8, command=self.root.destroy).pack(side="right")
        tk.Button(row, text="Load", width=8, command=self.load).pack(side="right", padx=4)
        tk.Button(row, text="Save", width=8, command=self.save).pack(side="right")

        # Messages
        tk.Label(self.root, textvariable=self.event_text, anchor="w").pack(fill="x", padx=20,
                                                                         pady=(10, 0))
        tk.Label(self.root, textvariable=self.message_text, anchor="w", justify="left",
                 wraplength=700, fg="#245b35").pack(fill="x", padx=20, pady=2)
        tk.Label(self.root, textvariable=self.leaderboard_text, anchor="w", justify="left",
                 wraplength=700).pack(fill="x", padx=20, pady=(4, 10))

    # State and display (as in desk.py)
    def loaded(self):
        if self.ticker is None:
            self.set_message("Load a market first.")
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
        self.agent_text.set("Not run yet.")

    def current_result(self):
        if self.view == "agent" and self.run_result is not None:
            return self.run_result
        return {"name": "Manual on " + str(self.ticker), "equity": list(self.equity),
                "trades": list(self.manual_trades)}

    def status(self):
        """The window's version of the desk's status line."""
        self.event_text.set("Latest event: " + self.last_event)
        if self.ticker is None:
            return
        self.market_text.set("Market: " + self.ticker)
        self.day_text.set("Day: " + str(self.day) + "/" + str(len(self.bars) - 1))
        self.price_text.set("Price: " + str(round(self.price(), 2)))
        self.cash_text.set("Cash: " + str(round(self.account.cash, 2)))
        self.shares_text.set("Shares: " + str(round(self.account.shares, 2)))
        self.equity_text.set("Equity: " + str(round(self.account.equity(self.price()), 2)))

    def set_message(self, message):
        self.message_text.set(message)

    # The actions (each one matches a desk.py method)
    def load_market(self, ticker):
        try:
            bars = load_bars(ticker)
        except FileNotFoundError:
            self.set_message("Cannot find data/training/" + ticker + ".csv (run from the project folder).")
            return
        except ValueError as error:
            self.set_message("Bad data file: " + str(error))
            return
        except OSError as error:
            self.set_message("Cannot read data/training/" + ticker + ".csv: " + str(error.strerror))
            return
        try:
            news = load_news(ticker)
        except (OSError, ValueError):
            news = {}
        self.bars = bars
        self.news = news
        self.ticker = ticker
        self.reset_session()
        self.last_event = "loaded " + ticker
        self.status()
        self.set_message("Loaded " + ticker + " (" + str(len(bars)) + " days, "
                         + str(len(news)) + " days with news).")

    def set_start(self):
        cash = read_number(self.start_cash_entry.get())
        shares = read_number(self.start_shares_entry.get())
        if cash is None or shares is None:
            self.set_message("That is not a number.")
            return
        if cash < 0 or shares < 0:
            self.set_message("Cash and shares cannot be negative.")
            return
        if shares != int(shares):                      # no fractions of a share
            self.set_message("Enter a whole number of shares only")
            return
        self.start_cash = cash
        self.start_shares = shares
        if self.ticker is not None:
            self.reset_session()
            self.last_event = "new starting balances"
            self.status()
        self.set_message("Session restarted at day 0 with the new balances.")

    def step(self):
        """Move forward n days (n from the box; blank = 1 day)."""
        if not self.loaded():
            return
        last_day = len(self.bars) - 1
        if self.day >= last_day:
            self.set_message("Already at the last day.")
            return
        text = self.days_entry.get().strip()
        if text == "":
            n = 1
        else:
            try:
                n = int(text)
            except ValueError:
                self.set_message("Enter a whole number of days, for example 5.")
                return
        if n < 1:
            self.set_message("The number of days must be 1 or more.")
            return
        message = "Stepped " + str(n) + " day(s)."
        if n > last_day - self.day:                    # do not go past the last day
            n = last_day - self.day
            message = "Only " + str(n) + " day(s) left, stepped to the last day."
        for _ in range(n):                             # one day at a time: one equity value per day
            self.day = self.day + 1
            self.equity.append(self.account.equity(self.price()))
        self.view = "manual"
        self.last_event = "stepped " + str(n) + " day(s) to day " + str(self.day)
        self.status()
        self.set_message(message)

    def trade(self, action):
        if not self.loaded():
            return
        text = self.shares_entry.get().strip()
        amount = -1.0 if text == "" else read_number(text)
        if amount is None:
            self.set_message("That is not a number.")
            return
        if amount != int(amount):                      # no fractions of a share
            self.set_message("Enter a whole number of shares only")
            return
        amount = int(amount)
        if amount == 0 or amount < -1:
            self.set_message("Enter a positive number of shares, or -1 for all/max.")
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
        self.status()
        self.set_message("-> " + reply)

    def run_agent(self, from_today):
        if not self.loaded():
            return
        if self.day == 0:
            from_today = False                         # today is day 0: the same as a full run
        if from_today and self.day >= len(self.bars) - 1:
            self.set_message("Already at the last day, nothing left for the agent to trade.")
            return
        if from_today:
            # the agent takes over the money you hold right now
            sim = Simulator(self.bars, self.news, self.account.cash, self.account.shares)
            start_day = self.day
            name = "TradingAgent on " + self.ticker + " from day " + str(start_day)
        else:
            sim = Simulator(self.bars, self.news, self.start_cash, self.start_shares)
            start_day = 0
            name = "TradingAgent on " + self.ticker
        try:
            result = sim.run(TradingAgent(), name, start_day=start_day)
        except ValueError as error:
            self.set_message("Cannot run the agent: " + str(error))
            return
        if from_today:
            # days 0..today come from your manual session, the rest from the agent
            result["equity"] = self.equity[:start_day] + result["equity"]
            result["trades"] = list(self.manual_trades) + result["trades"]
        self.run_result = result
        self.view = "agent"
        s = analytics.summary(result)
        self.agent_text.set(
            result["name"] + "\n"
            + "final equity " + str(round(s["final"], 2))
            + "   |   total return " + str(round(s["return"] * 100, 1)) + "%" + "\n"
            + "sharpe-like " + str(round(s["sharpe"], 3))
            + "   |   max drawdown " + str(round(abs(s["max_dd"]) * 100, 1)) + "%"
            + "   |   trades " + str(s["trades"]))
        self.last_event = "ran TradingAgent from day " + str(start_day) + " to the end"
        self.status()
        self.set_message("The charts now show this agent run, until you step or trade again.")

    # Charts
    def show_price_chart(self):
        if self.loaded():
            # the desk runs the agent on prices + news, so show that rule's two averages
            analytics.plot_price_with_trades(self.bars, self.current_result(),
                                             TradingAgent.SHORT, TradingAgent.LONG)

    def show_equity_chart(self):
        if self.loaded():
            analytics.plot_equity(self.current_result())

    def show_drawdown_chart(self):
        if self.loaded():
            analytics.plot_drawdown(self.current_result())

    # Saving and loading
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
            self.set_message("Could not save: " + str(error))
            return
        self.last_event = "saved"
        self.status()
        self.set_message("Saved the session to " + SESSION_FILE + ", the run to " + RESULTS_FILE
                         + " and the leaderboard to " + LEADERBOARD_FILE + ".")
        self.refresh_leaderboard()

    def load(self):
        try:
            data = storage.load_session(SESSION_FILE)
        except FileNotFoundError:
            self.set_message("No saved session yet (" + SESSION_FILE + ").")
            return
        except ValueError as error:
            self.set_message("Cannot load: " + str(error))
            return
        except OSError as error:
            self.set_message("Cannot load: " + str(error.strerror))
            return
        self.start_cash = data["start_cash"]
        self.start_shares = data.get("start_shares", 0.0)
        self.load_market(data["ticker"])
        if self.ticker != data["ticker"]:
            return
        if data["day"] < 0 or data["day"] > len(self.bars) - 1:
            self.set_message("Saved day is outside this dataset.")
            return
        self.day = data["day"]
        self.account = Account(data["cash"], data["shares"])
        self.equity = data["equity"] if len(data["equity"]) == self.day + 1 \
            else [self.account.equity(self.price())]
        self.manual_trades = data["trades"]
        self.start_cash_entry.delete(0, tk.END)        # show the loaded balances in the boxes
        self.start_cash_entry.insert(0, str(self.start_cash))
        self.start_shares_entry.delete(0, tk.END)
        self.start_shares_entry.insert(0, str(self.start_shares))
        self.last_event = "loaded session"
        self.status()
        self.set_message("Loaded session: " + self.ticker + " day " + str(self.day) + ".")
        self.refresh_leaderboard()

    def refresh_leaderboard(self):
        rows = storage.read_leaderboard(LEADERBOARD_FILE)
        lines = []
        for row in rows[:5]:                           # the top five saved runs
            parts = row.split(",")
            if len(parts) >= 3:                        # skip a damaged line
                lines.append(parts[0] + ". " + parts[1] + "  " + parts[2])
        if lines:
            self.leaderboard_text.set("Leaderboard, best final equity first:\n" + "\n".join(lines))
        else:
            self.leaderboard_text.set("Leaderboard: no saved runs yet.")


def main():
    root = tk.Tk()
    TradingDeskGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
