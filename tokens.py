from datetime import datetime
from typing import List


class PriceEntry:
    def __init__(self, price: float, timestamp: datetime, volume_token: float):
        self.price = price
        self.timestamp = timestamp
        self.volume_token = volume_token


class Token:
    def __init__(self, symbol):
        self.symbol = symbol  # BTC
        self.currency: str = "USD"
        self.price_history: List[PriceEntry] = []

    def getCurrentPrice(self):
        return 0.0 if len(self.price_history) == 0 else self.price_history[-1].price

    def getCurrentPriceDatetime(self):
        if len(self.price_history) == 0:
            return datetime.now()
        return self.price_history[-1].timestamp

    def addPriceEntry(self, price: float, _timestamp: datetime, _volume_token: float):
        if self.getCurrentPrice() == price:
            return
        self.price_history.append(PriceEntry(price=price, timestamp=_timestamp, volume_token=_volume_token))

