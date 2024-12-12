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
        gateway = Gateway(session, base_url='https://stokenet.radixdlt.com', network_id=2)
        oracle = Oracle(session)

        network_config = await gateway.network_configuration()
        account_details = load_account(network_config['network_id'])
        if account_details is None:
            account_details = new_account(network_config['network_id'])
        private_key, _, account = account_details

        print('RADIX ACCOUNT:', account.as_str())

        exchange = Exchange(gateway, oracle)
        await exchange.load_variables()

        permissions = await exchange.get_permissions(private_key.public_key())
        if len(permissions['level_1']) == 0:
            margin_account = await exchange.create_margin_account(account, private_key)
        else:
            margin_account = permissions['level_1'][0]
        print('MARGIN ACCOUNT:', margin_account.as_str())

        await exchange.create_recovery_key(account, private_key, margin_account)

        await exchange.add_collateral(
            account,
            private_key,
            margin_account,
            ret.Address(network_config['xrd']),
            ret.Decimal('100')
        )
        
        await exchange.margin_order_request(
            account,
            private_key,
            margin_account,
            'BTC/USD',
            ret.Decimal('0.001'),
            price_limit=PriceLimit.gte(ret.Decimal('10000')),
            slippage_limit=SlippageLimit.percent(ret.Decimal('0.3'))
        )

        pool_details = await exchange.pool_details()
        account_details = await exchange.account_details(margin_account)
        pair_details = await exchange.pair_details(['BTC/USD', 'ETH/USD'])

        await exchange.cancel_requests(account, private_key, account_details['active_requests'])

        print(pool_details)
        print(account_details)
        print(pair_details)

if __name__ == '__main__':
    asyncio.run(main())