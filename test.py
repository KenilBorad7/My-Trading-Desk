# test.py -- tests the critical main functions of every part of the program (30 cases).
# Run it from the project folder:   python test.py
# Every test case prints PASS or FAIL, and the totals are printed at the end.

import market_data
import analytics
import storage
import desk
from account import Account
from engine import Simulator
from agent import TradingAgent

passed = 0
failed = 0


def check(description, condition):
    """Record one test case: PASS if the condition is True, FAIL otherwise."""
    global passed, failed
    if condition:
        passed = passed + 1
        print("  PASS  " + description)
    else:
        failed = failed + 1
        print("  FAIL  " + description)


def raises(error_type, action):
    """True if running action() raises error_type. action is a lambda: a small one-line function."""
    try:
        action()
    except error_type:
        return True
    return False


print("\n== market_data.py: load_bars, load_news")
bars = market_data.load_bars("VOLT")
check("VOLT loads 750 days, each with the five price columns as floats",
      len(bars) == 750 and sorted(bars[0]) == ["close", "high", "low", "open", "volume"]
      and isinstance(bars[0]["close"], float))
check("a missing news file gives {}, not a crash",
      market_data.load_news("test_tmp_NONE", folder="") == {})
check("a missing price file raises FileNotFoundError",
      raises(FileNotFoundError, lambda: market_data.load_bars("test_tmp_NONE", folder="")))


print("\n== account.py: execute, equity")
a = Account(500.0, 0.0)
a.execute(("BUY", -1), 25.0)
check("BUY -1 with $500 at $25 buys 19 shares, not 20 (the contract's example)", a.shares == 19)
check("the 0.1% fee is taken: 24.525 cash left", round(a.cash, 3) == 24.525)
a = Account(100.0, 0.0)
check("buying too much gives the exact REJECT string and changes nothing",
      a.execute(("BUY", 10), 25.0) == "REJECT currency balance: 100.0"
      and a.cash == 100.0 and a.shares == 0)
check("selling too much gives the exact REJECT string",
      Account(0.0, 5.0).execute(("SELL", 6), 25.0) == "REJECT stock owned: 5.0")
a = Account(0.0, 4.0)
a.execute(("SELL", -1), 25.0)
check("SELL -1 sells everything at price x 0.999", a.shares == 0 and round(a.cash, 2) == 99.9)
check("equity = cash + shares x price", Account(1000.0, 2.0).equity(10.0) == 1020.0)


print("\n== engine.py: Simulator.run")
four_days = [{"open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0, "volume": 1.0},
             {"open": 20.0, "high": 20.0, "low": 20.0, "close": 21.0, "volume": 1.0},
             {"open": 30.0, "high": 30.0, "low": 30.0, "close": 31.0, "volume": 1.0},
             {"open": 40.0, "high": 40.0, "low": 40.0, "close": 41.0, "volume": 1.0}]


class BuyOnceAgent:
    """A test agent: buys 10 shares on its first day, then holds, and remembers what it saw."""
    def __init__(self):
        self.seen = []

    def decide(self, bar, headlines, cash, shares, last_response):
        self.seen.append(bar)
        if len(self.seen) == 1:
            return ("BUY", 10)
        return ("HOLD", 0)


class CrashingAgent:
    def decide(self, bar, headlines, cash, shares, last_response):
        raise RuntimeError("broken on purpose")


test_agent = BuyOnceAgent()
result = Simulator(four_days, {}, 1000.0, 0.0).run(test_agent, "buy once")
check("no look-ahead: the agent never sees the last day", test_agent.seen == four_days[:3])
check("an order fills at the next day's open", result["trades"] == [(1, "BUY", 20.0)])
check("one equity value per day", len(result["equity"]) == 4)
print("  (the 'Agent error' lines below are expected: that agent fails on purpose)")
result = Simulator(four_days, {}).run(CrashingAgent(), "crash")
check("a crashing agent only holds; the engine carries on", result["trades"] == [])
result = Simulator(four_days, {}, 1000.0).run(BuyOnceAgent(), "late", start_day=2)
check("starting on day 2 gives equity for days 2 and 3 only", len(result["equity"]) == 2)


print("\n== analytics.py: the three metrics")
equity = [100.0, 120.0, 90.0, 110.0]                  # the worked example in the project rules
check("total return is 10%", round(analytics.total_return(equity), 4) == 0.1)
check("max drawdown is -25% (120 down to 90)", analytics.max_drawdown(equity) == -0.25)
check("sharpe-like is 0.264 (mean / standard deviation)",
      round(analytics.sharpe_like(equity), 3) == 0.264)
check("starting with no money gives 0, not a division by zero",
      analytics.total_return([0.0, 0.0]) == 0.0 and analytics.max_drawdown([0.0, 0.0]) == 0.0)


print("\n== storage.py: saving and loading")
# storage.py writes real files with open(). So that this test leaves no files behind,
# pretend files kept in memory stand in for the disk: storage.open is looked up before
# Python's own open, so this replaces it inside storage.py only.
memory_files = {}


class MemoryFile:
    """Behaves like an open file for write(), reading line by line, and close()."""
    def __init__(self, name):
        self.name = name

    def write(self, text):
        memory_files[self.name] = memory_files[self.name] + text

    def __iter__(self):
        return iter(memory_files[self.name].splitlines(True))   # True keeps each "\n"

    def close(self):
        pass


def memory_open(path, mode="r", encoding=None):
    if mode == "w":
        memory_files[path] = ""                        # "w" starts the file empty
    elif mode == "a" and path not in memory_files:
        memory_files[path] = ""                        # "a" adds to the end
    elif mode == "r" and path not in memory_files:
        raise FileNotFoundError(path)                  # reading a file that is not there
    return MemoryFile(path)


storage.open = memory_open

storage.save_session("session.txt", "VOLT", 2, 8941.74, 10.0, 10000.0, 0.0,
                     [10000.0, 9990.5, 9998.94], [(1, "BUY", 105.72)])
data = storage.load_session("session.txt")
check("a saved session loads back the same",
      data["ticker"] == "VOLT" and data["day"] == 2 and data["cash"] == 8941.74
      and data["equity"] == [10000.0, 9990.5, 9998.94] and data["trades"] == [(1, "BUY", 105.72)])
check("a missing session raises FileNotFoundError",
      raises(FileNotFoundError, lambda: storage.load_session("no_such_file.txt")))
storage.append_result("results.txt", "Manual on VOLT", 9998.94, 1)
storage.append_result("results.txt", "TradingAgent on VOLT", 19720.91, 306)
storage.write_leaderboard("results.txt", "leaderboard.txt")
check("the leaderboard puts the best final equity first",
      storage.read_leaderboard("leaderboard.txt") ==
      ["1,TradingAgent on VOLT,19720.91", "2,Manual on VOLT,9998.94"])
del storage.open                                      # back to the real open()


print("\n== desk.py: starting balances, Step n days, manual trades")
# The desk asks with input(). Here a list of typed answers stands in for the keyboard.
typed = []
desk.input = lambda prompt: typed.pop(0)
d = desk.Desk(1000.0, 0.0)                            # a hand-made 4-day market, closes 10 to 13
d.ticker = "TEST"
d.bars = [{"open": c, "high": c, "low": c, "close": c, "volume": 1.0} for c in (10.0, 11.0, 12.0, 13.0)]
d.reset_session()

check("bad command-line balances fall back to the defaults",
      desk.read_start(["desk.py", "abc"]) == (10000.0, 0.0)
      and desk.read_start(["desk.py", "100", "2.5"]) == (10000.0, 0.0))
typed[:] = ["2"]
d.step()
check("Step 2 days moves to day 2, with one equity value per day", d.day == 2 and len(d.equity) == 3)
typed[:] = ["99"]
d.step()
check("Step past the end stops on the last day", d.day == 3)
typed[:] = ["2.5"]
d.trade("BUY")
check("a fraction of a share is refused", d.account.shares == 0)
typed[:] = ["10"]
d.trade("BUY")
check("buying 10 at today's close of 13 costs 130.13",
      d.account.shares == 10 and round(d.account.cash, 2) == 869.87)


print("\n== agent.py: TradingAgent")
check("news score: 'rally' and 'record' are +1 each",
      TradingAgent().news_score(["VOLT rally on record volume"]) == 2.0)
bar = {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1.0}
check("good news buys 40% of cash: int(4000 / 100.1) = 39 shares",
      TradingAgent().decide(bar, ["rally"], 10000.0, 0.0, None) == ("BUY", 39))
check("bad news while holding sells everything",
      TradingAgent().decide(bar, ["crash"], 0.0, 10.0, None) == ("SELL", -1))
news = market_data.load_news("VOLT")
first = Simulator(bars, news).run(TradingAgent(), "TradingAgent on VOLT")
second = Simulator(bars, news).run(TradingAgent(), "TradingAgent on VOLT")
check("a full VOLT run gives the same result twice and ends at 19,720.91",
      first == second and round(first["equity"][-1], 2) == 19720.91)


print()
print("Total: " + str(passed) + " passed, " + str(failed) + " failed.")
if failed == 0:
    print("ALL TESTS PASS.")
else:
    print("SOME TESTS FAILED: look for FAIL above.")
