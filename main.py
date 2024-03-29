import asyncio
import multiprocessing
import time
import traceback
from datetime import datetime
import json
from multiprocessing import Process
from typing import List
import aiohttp
import decouple
import requests
import uvicorn
from fastapi import FastAPI
from aiohttp_socks import ProxyConnector
from python_socks import ProxyConnectionError

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
                                                "volume_token": price_entry.volume_token,
                                                "timestamp": price_entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')})
    return token_json


def generateJsonHistoryAllTokens():
    return [generateJsonHistoryOfOneToken(token) for token in tokens]


def getAllTokenNames():
    return [token.symbol for token in tokens]


async def fetch_token_price(token: Token, semaphore, _id):
    await semaphore.acquire()

    url = f"https://api.binance.com/api/v3/uiKlines?symbol={token.symbol}USDT&interval=1m&limit=1"
    use_proxy = len(proxy) != 0
    if use_proxy:
        connector = ProxyConnector.from_url(proxy)
        session = aiohttp.ClientSession(connector=connector)
    else:
        session = aiohttp.ClientSession()
    async with session:
        try:
            async with session.get(url) as resp:
                data = await resp.json()
                token_data = data[0]
                current_price = float(token_data[4])
                volume_token = float(token_data[5])
                token.addPriceEntry(current_price, datetime.now(), volume_token)
                data_to_send = {"symbol": token.symbol, "current_price": token.getCurrentPrice(),
                                "volume_token": volume_token,
                                "current_time": token.getCurrentPriceDatetime().strftime("%Y-%m-%d %H:%M:%S")}
                requests.post(f"{URL_OF_COORDINATOR}/addTokenPrice", data=json.dumps(data_to_send))
                if use_proxy:
                    await asyncio.sleep(3)
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
        except ProxyConnectionError:
            err = ""
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(5)

    semaphore.release()


async def fetch_all_token_prices(_tokens):
    semaphore = asyncio.Semaphore(HTTP_THREADS)  # Limiting to 10 concurrent requests
    task_id = 0
    while True:  # Run indefinitely
        if semaphore.locked():
            print("LOCKED???")
            time.sleep(1)
        async with semaphore:
            tasks = [asyncio.create_task(fetch_token_price(token, semaphore, task_id + _id))
                     for _id, token in enumerate(_tokens)]
            task_id += len(_tokens)
            _ = await asyncio.gather(*tasks)


app = FastAPI()


@app.put("/putToken/{token}")
async def addTokenToCheck(token: str):
    token_existing = len([_token for _token in tokens if _token.symbol == token]) > 0
    if token_existing:
        return {"message": "Token already existing"}
    tokens.append(Token(token))
    return {"tokens": generateJsonHistoryAllTokens()}


@app.delete("/deleteToken/{token}")
async def deleteTokenFromChecking(token: str):
    if len(tokens) == 0:
        return {"tokens": []}
    _id, _token_existing = next((_id, _token) for _id, _token in enumerate(tokens) if _token.symbol == token)
    if _token_existing is None:
        return {"message": "Token not existing"}
    tokens.pop(_id)
    return (
        {"tokens": []}
        if len(tokens) == 0
        else {"tokens": generateJsonHistoryAllTokens()}
    )


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
    uvicorn.run(app, host="0.0.0.0", port=PORT_TO_RUN_UVICORN, log_level="error")
