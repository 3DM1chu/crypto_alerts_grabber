from datetime import datetime
from typing import List


class PriceEntry:
    def __init__(self, price: float, timestamp: datetime):
        self.price = price
        self.timestamp = timestamp


class Token:
    def __init__(self, symbol):
        self.symbol = symbol  # BTC
        self.currency: str = "USD"
        self.price_history: List[PriceEntry] = []

    def getCurrentPrice(self):
        if len(self.price_history) == 0:
            return 0.0
        return self.price_history[-1].price

    def getCurrentPriceDatetime(self):
        if len(self.price_history) == 0:
            return datetime.now()
        return self.price_history[-1].timestamp

    def addPriceEntry(self, price: float, _timestamp: datetime):
        if self.getCurrentPrice() == price:
            return
        self.price_history.append(PriceEntry(price=price, timestamp=_timestamp))

