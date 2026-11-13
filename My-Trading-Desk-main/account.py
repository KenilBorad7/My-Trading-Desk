# account.py -- the authority: owns cash and shares, validates every order.
# Reference: <full name>
import math

FEE = 0.001


class Account:
    def __init__(self, cash=10000.0, shares=0.0):
        self.cash = float(cash)
        self.shares = float(shares)

    def equity(self, price):
        return self.cash + self.shares * price

    def execute(self, order, price):
        """Fill (action, amount) at price. Returns 'ACCEPT' or the exact REJECT string."""
        try:
            action = order[0]
            amount = float(order[1])
        except (TypeError, ValueError, IndexError):
            return "ACCEPT"                       # malformed order = nothing to do
        if not math.isfinite(amount):
            return "ACCEPT"
        if action == "BUY":
            if amount < 0:                        # -1: as many whole shares as cash covers
                amount = int(self.cash / (price * (1.0 + FEE)))
                if amount * price * (1.0 + FEE) > self.cash:
                    amount = amount - 1
            if amount <= 0:
                return "ACCEPT"
            cost = amount * price * (1.0 + FEE)
            if cost > self.cash:
                return "REJECT currency balance: " + str(round(self.cash, 2))
            self.cash = self.cash - cost
            self.shares = self.shares + amount
            return "ACCEPT"
        if action == "SELL":
            if amount < 0:
                amount = self.shares
            if amount <= 0:
                return "ACCEPT"
            if amount > self.shares:
                return "REJECT stock owned: " + str(round(self.shares, 2))
            self.cash = self.cash + amount * price * (1.0 - FEE)
            self.shares = self.shares - amount
            return "ACCEPT"
        return "ACCEPT"
