import aiohttp
import asyncio
import radix_engine_toolkit as ret

from surge.tools.gateway import Gateway
from surge.tools.oracle import Oracle
from surge.tools.accounts import load_account, new_account
from surge.exchange import Exchange
from surge.types import PriceLimit, SlippageLimit

async def main():
    async with aiohttp.ClientSession() as session:
        # Setup Gateway and Oracle
        gateway = Gateway(session, base_url='https://mainnet.radixdlt.com', network_id=1)
        oracle = Oracle(session)


        # Load exchange variables
        exchange = Exchange(gateway, oracle, env_registry=ret.Address('component_rdx1cr7gxwrvkjfh74f6w5hws7njt9z6ng5uqwdp23x972gx94lfg7cwn4'))
        await exchange.load_variables()

        # Fetch various details about the exchange state
        pool_details = await exchange.pool_details()
        pair_details = await exchange.pair_details(['BTC/USD', 'ETH/USD'])

        # Print the fetched details
        print(pool_details)
        print(pair_details)

if __name__ == '__main__':
    asyncio.run(main())