import asyncio
import ccxt.async_support as ccxt
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    api_key = os.getenv("INDODAX_API_KEY")
    secret = os.getenv("INDODAX_SECRET")
    
    exchange = ccxt.indodax({
        "apiKey": api_key,
        "secret": secret,
        "enableRateLimit": True,
    })
    
    await exchange.load_markets()
    market = exchange.markets['ETH/IDR']
    print(market['id'])
    print(market.get('active'), market.get('symbol'))
        
    await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
