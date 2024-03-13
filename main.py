import asyncio
import multiprocessing
import random
import time
import traceback
from datetime import datetime, timedelta
import json
from multiprocessing import Process
from typing import List
import aiohttp
import decouple
import requests
import uvicorn
from fastapi import FastAPI
from urllib3.contrib.socks import SOCKSHTTPSConnection

from tokens import Token

HTTP_THREADS = int(decouple.config("HTTP_THREADS"))
PORT_TO_RUN_UVICORN = int(decouple.config("PORT_TO_RUN_UVICORN"))
URL_OF_COORDINATOR = str(decouple.config("URL_OF_COORDINATOR"))
token_names: List[str] = []
proxy = str(decouple.config("PROXY_SOCKS5"))


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
    return [generateJsonHistoryOfOneToken(token) for token in tokens]


def getAllTokenNames():
    return [token.symbol for token in tokens]


async def fetch_token_price(session, token: Token, semaphore, _id):
    await semaphore.acquire()

    urls = [
        f"https://api.binance.com/api/v3/uiKlines?symbol={token.symbol}USDT&interval=1m&limit=1",
        f"https://pexljc3fiphfkworlrtv52mi2q0cqhke.lambda-url.eu-central-1.on.aws/?coin={token.symbol}USDT",
        #f"https://cold-condor-42.deno.dev/{token.symbol}USDT"
    ]

    url = urls[_id % len(urls)]
    if 'api.binance' in url:
        proxy_use = proxy
    else:
        proxy_use = None
        await asyncio.sleep(random.randint(1, 5))
    try:
        async with session.get(url, proxy=proxy_use) as resp:
            data = resp.text()
            data = json.loads(data)
            token_data = data[0]
            current_price = float(token_data[4])
            token.addPriceEntry(current_price, datetime.now())
            data_to_send = {"symbol": token.symbol, "current_price": token.getCurrentPrice(),
                            "current_time": token.getCurrentPriceDatetime().strftime("%Y-%m-%d %H:%M:%S")}
            requests.post(f"{URL_OF_COORDINATOR}/addTokenPrice", data=json.dumps(data_to_send))
            print(f"Sent token {token.symbol}")
            """
            # Get the current time
            current_time = datetime.now()

            # Subtract 1 hour from the current time
            adjusted_time = current_time - timedelta(hours=1)

            # Convert adjusted time to Unix time
            adjusted_unix_time = int(adjusted_time.timestamp()) * 1000

            _data = requests.get(f"https://api.binance.com/api/v3/uiKlines?symbol={token.symbol}USDT&interval=1m"
                                 f"&limit=1&startTime={adjusted_unix_time}")
            _data = json.loads(_data.text)[0]
            price_1h_ago = float(_data[4])
            """
    except:
        print("Problem with URL: " + url)
        traceback.print_exc()

    semaphore.release()


async def fetch_all_token_prices(_tokens):
    semaphore = asyncio.Semaphore(HTTP_THREADS)  # Limiting to 10 concurrent requests
    task_id = 0
    async with aiohttp.ClientSession() as session:
        while True:  # Run indefinitely
            if semaphore.locked():
                await asyncio.sleep(2)
            async with semaphore:
                tasks = [fetch_token_price(session, token, semaphore, task_id + _id)
                         for _id, token in enumerate(_tokens)]
                await asyncio.gather(*tasks)
                task_id += len(_tokens)


app = FastAPI()


@app.put("/putToken/{token}")
async def addTokenToCheck(token: str):
    token_existing = len([_token for _token in tokens if _token.symbol == token]) > 0
    if not token_existing:
        tokens.append(Token(token))
        return {"tokens": generateJsonHistoryAllTokens()}
    else:
        return {"message": "Token already existing"}


@app.delete("/deleteToken/{token}")
async def deleteTokenFromChecking(token: str):
    if len(tokens) == 0:
        return {"tokens": []}
    _id, _token_existing = next((_id, _token) for _id, _token in enumerate(tokens) if _token.symbol == token)
    if _token_existing is not None:
        tokens.pop(_id)
        if len(tokens) == 0:
            return {"tokens": []}
        else:
            return {"tokens": generateJsonHistoryAllTokens()}
    else:
        return {"message": "Token not existing"}


@app.get("/tokens")
async def getTokensPrice():
    return json.dumps(tokens)


def start_fetching(_tokens):
    asyncio.run(asyncio.sleep(5))
    asyncio.run(fetch_all_token_prices(_tokens))


if __name__ == "__main__":
    manager = multiprocessing.Manager()
    tokens: List[Token] = manager.list()
    fetcher_process = Process(target=start_fetching, args=(tokens,))
    fetcher_process.start()
    uvicorn.run(app, host="0.0.0.0", port=PORT_TO_RUN_UVICORN, log_level="info")
