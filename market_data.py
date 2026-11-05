# market_data.py -- loading prices and news. Files are read as given, every run.
# Reference: <full name>
import pandas as pd

DATA_DIR = "data/training/"


def load_bars(ticker, folder=DATA_DIR):
    """Read TICKER.csv into a list of bar dicts. Raises FileNotFoundError / ValueError."""
    frame = pd.read_csv(folder + ticker + ".csv")
    needed = ["open", "high", "low", "close", "volume"]
    for name in needed:
        if name not in frame.columns:
            raise ValueError("column '" + name + "' missing in " + ticker + ".csv")
    bars = []
    for o, h, l, c, v in zip(frame["open"].tolist(), frame["high"].tolist(),
                             frame["low"].tolist(), frame["close"].tolist(),
                             frame["volume"].tolist()):
        bars.append({"open": float(o), "high": float(h), "low": float(l),
                     "close": float(c), "volume": float(v)})
    if len(bars) < 2:
        raise ValueError(ticker + ".csv needs at least 2 days")
    return bars


def load_news(ticker, folder=DATA_DIR):
    """Read TICKER_news.txt into {day: [headline, ...]}. A missing file gives {}."""
    news = {}
    try:
        handle = open(folder + ticker + "_news.txt", encoding="utf-8")
    except FileNotFoundError:
        return news
    for line in handle:
        if line.startswith("day"):
            continue
        line = line.strip()
        if line == "":
            continue
        parts = line.split(",", 1)
        try:
            day = int(parts[0])
        except ValueError:
            continue
        if len(parts) < 2:
            continue
        if day not in news:
            news[day] = []
        news[day].append(parts[1].strip())
    handle.close()
    return news
