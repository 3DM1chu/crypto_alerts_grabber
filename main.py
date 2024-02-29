import asyncio
import multiprocessing
import threading
from datetime import datetime
import json
from multiprocessing import Process
from typing import List
import aiohttp
import uvicorn
from fastapi import FastAPI, BackgroundTasks

from tokens import Token, PriceEntry

#HTTP_THREADS = int(config("HTTP_THREADS"))
token_names: List[str] = []


def turnJsonIntoTokenList(json_obj):
    tokens_to_return: List[Token] = []
    for token_from_file in json_obj:
        token = Token(token_from_file["symbol"])
        token.currency = token_from_file["currency"]
        for price_history_entry in token_from_file["price_history"]:
            timestamp_format = "%Y-%m-%d %H:%M:%S"
            # Parse the string into a datetime object
            timestamp = datetime.strptime(price_history_entry["timestamp"], timestamp_format)
            token.price_history.append(PriceEntry(price_history_entry["price"], timestamp))
        tokens_to_return.append(token)
    return tokens_to_return


def generateJsonHistoryOfOneToken(token: Token):
    token_json = {
        "symbol": token.symbol,
        "currency": token.currency,
        "price_history": []
    }
    for price_entry in token.price_history:
        if len(token.price_history) != 0:
            token_json["price_history"].append({"price": price_entry.price,
                                                "timestamp": price_entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')})
    return token_json


def generateJsonHistoryAllTokens():
    tokens_json = []
    for token in tokens:
        tokens_json.append(generateJsonHistoryOfOneToken(token))
    return tokens_json


def getAllTokenNames():
    tokens_to_ret = []
    for token in tokens:
        tokens_to_ret.append(token.symbol)
    return tokens_to_ret


async def fetch_token_price(session, token: Token, semaphore, id):
    print(f"Started fetching coin: {token.symbol}")
    await semaphore.acquire()

    urls = [
        f"https://api.binance.com/api/v3/uiKlines?symbol={token.symbol}USDT&interval=1m&limit=1",
        f"https://pexljc3fiphfkworlrtv52mi2q0cqhke.lambda-url.eu-central-1.on.aws/?coin={token.symbol}USDT",
        f"https://cold-condor-42.deno.dev/{token.symbol}USDT"
    ]

    url = urls[id % len(urls)]
    try:
        async with session.get(url) as resp:
            data = await resp.text()
            data = json.loads(data)
            coin_data = data[0]
            current_price = float(coin_data[4])
            print(current_price)
            token.addPriceEntry(current_price, datetime.now())
    except:
        x = "err of URL: " + url
        print(x)

    semaphore.release()


async def fetch_all_token_prices(tokens):
    semaphore = asyncio.Semaphore(15)  # Limiting to 10 concurrent requests
    id = 0
    async with aiohttp.ClientSession() as session:
        while True:  # Run indefinitely
            async with semaphore:
                #print(tokenss)
                #_token_symbols = json.loads(requests.get("http://localhost:5678/fetcher_tokens").json())
               # for token_symbol in _token_symbols:
                #    if not tokenAlreadyExists(token_symbol):
                #        tokens.append(Token(token_symbol))
                tasks = [fetch_token_price(session, token, semaphore, id) for token in tokens]
                await asyncio.gather(*tasks)


app = FastAPI()


@app.get("/fetcher_tokens")
async def getTokensForLocal():
    return json.dumps(getAllTokenNames())


@app.put("/putToken/{token}")
async def addTokenToCheck(token: str):
    tokens.append(Token(token))
    return {"tokens": generateJsonHistoryAllTokens()}


@app.get("/prices/{coin}")
async def getTokenPrice(coin: str):
    return {"coin": coin}


@app.get("/tokens")
async def getTokensPrice():
    return json.dumps(tokens)


def test_mp(_q, l):
    l.acquire()
    try:
        asyncio.run(asyncio.sleep(5))
        asyncio.run(fetch_all_token_prices(_q))
    finally:
        l.release()


if __name__ == "__main__":
    lock = multiprocessing.Lock()
    manager = multiprocessing.Manager()
    tokens: List[Token] = manager.list()

    #proc = Process(target=uvicorn.run,
    #               #kwargs={"app": "main:app", "port": 21591, "log_level": "info", "host": "192.168.15.91"},
    #               kwargs={"app": "main:app", "port": 21591, "log_level": "info", "host": "0.0.0.0"},
    #               daemon=True)
    #proc.start()

    p = Process(target=test_mp, args=(tokens, lock))
    p.start()

    #asyncio.run(fetch_all_token_prices(tokens))
    #proc.start()
    #t1 = threading.Thread(target=fetch_all_token_prices, args=(tokens, lock), daemon=True)
    #t1.start()
    #p = multiprocessing.Process(target=fetch_all_token_prices, args=(tokens, lock), daemon=True)
    #p.start()
    #p.join()
    #uvicorn.run(app, host="192.168.15.91", port=21591, log_level="info")
    uvicorn.run(app, host="0.0.0.0", port=21591, log_level="info")
