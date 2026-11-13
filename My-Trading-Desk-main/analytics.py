# analytics.py -- indicators built by hand, three metrics, three charts.
# Reference: <full name>
import numpy as np
import matplotlib.pyplot as plt


def daily_returns(equity):
    values = np.array(equity)                      # array first, then slice by position
    return values[1:] / values[:-1] - 1


def moving_average(values, window):
    closes = np.array(values)
    ma = []
    for i in range(window, len(closes) + 1):
        ma.append(closes[i - window:i].mean())
    return np.array(ma)


def total_return(equity):
    return (equity[-1] - equity[0]) / equity[0]


def drawdown_series(equity):
    peak = equity[0]
    series = []
    for value in equity:
        if value > peak:
            peak = value
        series.append((value - peak) / peak)
    return series


def max_drawdown(equity):
    return min(drawdown_series(equity))            # negative, e.g. -0.16


def sharpe_like(equity):
    returns = daily_returns(equity)
    if len(returns) < 2:
        return 0.0
    spread = returns.std()
    if spread == 0:
        return 0.0
    return float(returns.mean() / spread)


def summary(result):
    equity = result["equity"]
    return {"final": equity[-1], "return": total_return(equity),
            "max_dd": max_drawdown(equity), "sharpe": sharpe_like(equity),
            "trades": len(result["trades"])}


def print_summary(result):
    s = summary(result)
    print(result["name"])
    print("  final equity : " + str(round(s["final"], 2)))
    print("  total return : " + str(round(s["return"] * 100, 1)) + "%")
    print("  sharpe-like  : " + str(round(s["sharpe"], 3)))
    print("  max drawdown : " + str(round(-s["max_dd"] * 100, 1)) + "%")
    print("  trades       : " + str(s["trades"]))


def _finish(save_path):
    if save_path:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()


def plot_equity(result, save_path=None):
    plt.figure()
    plt.plot(result["equity"], label="equity")
    plt.title("Equity curve: " + result["name"])
    plt.xlabel("day")
    plt.ylabel("cash + shares x close (USD)")
    plt.legend()
    _finish(save_path)


def plot_drawdown(result, save_path=None):
    plt.figure()
    plt.plot(drawdown_series(result["equity"]), color="red", label="drawdown")
    plt.title("Drawdown: " + result["name"])
    plt.xlabel("day")
    plt.ylabel("fraction below best so far")
    plt.legend()
    _finish(save_path)


def plot_price_with_trades(bars, result, window=10, save_path=None):
    closes = np.array([bar["close"] for bar in bars])
    plt.figure()
    plt.plot(closes, color="gray", label="close")
    if len(closes) >= window:
        ma = moving_average(closes, window)
        plt.plot(range(window - 1, len(closes)), ma, color="blue", linewidth=1,
                 label=str(window) + "-day average")
    buys = [t for t in result["trades"] if t[1] == "BUY"]
    sells = [t for t in result["trades"] if t[1] == "SELL"]
    if buys:
        plt.scatter([t[0] for t in buys], [t[2] for t in buys], marker="^",
                    color="green", label="buy")
    if sells:
        plt.scatter([t[0] for t in sells], [t[2] for t in sells], marker="v",
                    color="red", label="sell")
    plt.title("Price with trades: " + result["name"])
    plt.xlabel("day")
    plt.ylabel("price (USD)")
    plt.legend()
    _finish(save_path)
