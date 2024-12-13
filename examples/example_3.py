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
        gateway = Gateway(session, base_url='https://stokenet.radixdlt.com', network_id=2)
        oracle = Oracle(session)

        # Load exchange variables
        exchange = Exchange(gateway, oracle, env_registry=ret.Address('component_tdx_2_1czj40n6730x4saae7mnpe20htre57rdwvzvnfcuvcusy9s0jn6qqmf'))
        await exchange.load_variables()

        # Fetch available pairs
        pairs = await exchange.available_pairs()
        print(pairs)

        # Fetch pair configurations
        pair_configs = await exchange.pair_configs()
        print(pair_configs)

        # Fetch available collaterals
        collaterals = await exchange.available_collaterals()
        print(collaterals)

        # Fetch collateral configurations
        collateral_configs = await exchange.collateral_configs()
        print(collateral_configs)

if __name__ == '__main__':
    asyncio.run(main())