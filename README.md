# Tool that uses binance API to grab coin prices
Just grabbing prices for given coins, acts like HTTP server with fastapi using python 3.11

# Example output from Binance API
https://api.binance.com/api/v3/uiKlines?symbol=DOGEUSDT&interval=1m&limit=1
```json
[
  [
    1499040000000,      // Kline open time
    "0.01634790",       // Open price
    "0.80000000",       // High price
    "0.01575800",       // Low price
    "0.01577100",       // Close price
    "148976.11427815",  // Volume
    1499644799999,      // Kline close time
    "2434.19055334",    // Quote asset volume
    308,                // Number of trades
    "1756.87402397",    // Taker buy base asset volume
    "28.46694368",      // Taker buy quote asset volume
    "0"                 // Unused field. Ignore.
  ]
]
```

Example .env file
```
HTTP_THREADS=15
PORT_TO_RUN_UVICORN=21591
```

#multithreaded #coins #cryptocurreny #crypto #binance #api #python