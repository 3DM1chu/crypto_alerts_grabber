import asyncio
import multiprocessing
from datetime import datetime
import json
from multiprocessing import Process
from typing import List
import aiohttp
import decouple
import uvicorn
from fastapi import FastAPI

from tokens import Token, PriceEntry

HTTP_THREADS = int(decouple.config("HTTP_THREADS"))
PORT_TO_RUN_UVICORN = int(decouple.config("PORT_TO_RUN_UVICORN"))
URL_OF_COORDINATOR = str(decouple.config("URL_OF_COORDINATOR"))
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
    return [generateJsonHistoryOfOneToken(token) for token in tokens]


def getAllTokenNames():
    return [token.symbol for token in tokens]


async def fetch_token_price(session, token: Token, semaphore, _id):
    print(f"Started fetching coin: {token.symbol}")
    await semaphore.acquire()

    urls = [
        f"https://api.binance.com/api/v3/uiKlines?symbol={token.symbol}USDT&interval=1m&limit=1",
        f"https://pexljc3fiphfkworlrtv52mi2q0cqhke.lambda-url.eu-central-1.on.aws/?coin={token.symbol}USDT",
        f"https://cold-condor-42.deno.dev/{token.symbol}USDT"
    ]

    url = urls[_id % len(urls)]
    try:
        async with session.get(url) as resp:
            data = await resp.text()
            data = json.loads(data)
            coin_data = data[0]
            current_price = float(coin_data[4])
            print(current_price)
            token.addPriceEntry(current_price, datetime.now())
            async with aiohttp.ClientSession() as sessionx:
                data_to_send = {"token": {"coin_name": token.symbol, "current_price": token.getCurrentPrice(),
                                          "current_time": token.getCurrentPriceDatetime()}}
                await sessionx.post(f"{URL_OF_COORDINATOR}/addTokenPrice", data=json.dumps(data_to_send))
    except:
        x = "err of URL: " + url
        print(x)

    semaphore.release()


async def fetch_all_token_prices(_tokens):
    semaphore = asyncio.Semaphore(HTTP_THREADS)  # Limiting to 10 concurrent requests
    task_id = 0
    async with aiohttp.ClientSession() as session:
        while True:  # Run indefinitely
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
async def addTokenToCheck(token: str):
    _id, _token_existing = next((_id, _token) for _id, _token in enumerate(tokens) if _token.symbol == token)
    if _token_existing is not None:
        tokens.pop(_id)
    return {"tokens": generateJsonHistoryAllTokens()}


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
