# storage.py -- plain-text save/load of the session, results and leaderboard.
# Reference: <full name>


def save_session(path, ticker, day, cash, shares, start_cash, start_shares, equity, trades):
    handle = open(path, "w")
    handle.write("ticker," + ticker + "\n")
    handle.write("day," + str(day) + "\n")
    handle.write("cash," + str(cash) + "\n")
    handle.write("shares," + str(shares) + "\n")
    handle.write("start," + str(start_cash) + "," + str(start_shares) + "\n")
    handle.write("equity," + ",".join([str(v) for v in equity]) + "\n")
    for day_no, action, price in trades:
        handle.write("trade," + str(day_no) + "," + action + "," + str(price) + "\n")
    handle.close()


def load_session(path):
    """Returns a dict, or raises FileNotFoundError / ValueError for a missing/bad file."""
    data = {"trades": [], "equity": []}
    handle = open(path)
    try:
        for line in handle:
            parts = line.strip().split(",")
            key = parts[0]
            if key == "ticker":
                data["ticker"] = parts[1]
            elif key == "day":
                data["day"] = int(parts[1])
            elif key == "cash":
                data["cash"] = float(parts[1])
            elif key == "shares":
                data["shares"] = float(parts[1])
            elif key == "start":
                data["start_cash"] = float(parts[1])
                data["start_shares"] = float(parts[2])
            elif key == "equity":
                data["equity"] = [float(v) for v in parts[1:] if v != ""]
            elif key == "trade":
                data["trades"].append((int(parts[1]), parts[2], float(parts[3])))
    except (IndexError, ValueError):
        raise ValueError("session file is damaged")
    finally:
        handle.close()
    for needed in ("ticker", "day", "cash", "shares", "start_cash"):
        if needed not in data:
            raise ValueError("session file is missing '" + needed + "'")
    return data


def append_result(path, name, final_equity, trade_count):
    handle = open(path, "a")
    handle.write(name + "," + str(round(final_equity, 2)) + "," + str(trade_count) + "\n")
    handle.close()


def read_results(path):
    """[(name, final_equity)] for every saved run; [] if no file yet."""
    results = []
    try:
        handle = open(path)
    except FileNotFoundError:
        return results
    for line in handle:
        parts = line.strip().rsplit(",", 2)
        if len(parts) == 3:
            try:
                results.append((parts[0], float(parts[1])))
            except ValueError:
                continue
    handle.close()
    return results


def write_leaderboard(results_path, leaderboard_path):
    """Rewrite the leaderboard from every saved run, best final equity first."""
    results = read_results(results_path)
    rows = [[final, name] for name, final in results]
    rows.sort()
    rows.reverse()
    handle = open(leaderboard_path, "w")
    handle.write("rank,name,final_equity\n")
    rank = 1
    for final, name in rows:
        handle.write(str(rank) + "," + name + "," + str(final) + "\n")
        rank = rank + 1
    handle.close()
    return rows


def read_leaderboard(path):
    lines = []
    try:
        handle = open(path)
    except FileNotFoundError:
        return lines
    for line in handle:
        if not line.startswith("rank"):
            lines.append(line.strip())
    handle.close()
    return lines
