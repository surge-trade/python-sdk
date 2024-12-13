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

        # Get network configuration
        network_config = await gateway.network_configuration()
       
        # Try to load existing account
        load_account_result = load_account(network_config['network_id'])
        if load_account_result:
            private_key, _, account = load_account_result
        else:
            # Create new account 
            print('No account found, creating new account...')
            private_key, _, account = new_account(network_config['network_id'])

            # Request test tokens from the faucet (only works on testnet)
            builder = ret.ManifestV1Builder()
            builder = builder.call_method(
                ret.ManifestBuilderAddress.STATIC(ret.Address(network_config['faucet'])),
                'lock_fee',
                [ret.ManifestBuilderValue.DECIMAL_VALUE(ret.Decimal('10'))]
            )
            builder = builder.call_method(
                ret.ManifestBuilderAddress.STATIC(ret.Address(network_config['faucet'])),
                'free',
                []
            )
            builder = builder.account_deposit_entire_worktop(account)
            payload, intent = await gateway.build_transaction(builder, private_key)
            await gateway.submit_transaction(payload)
            await gateway.get_transaction_status(intent)

        # Print the account address
        print('RADIX ACCOUNT:', account.as_str())

        # Load exchange variables
        exchange = Exchange(gateway, oracle, env_registry=ret.Address('component_tdx_2_1czj40n6730x4saae7mnpe20htre57rdwvzvnfcuvcusy9s0jn6qqmf'))
        await exchange.load_variables()

        # Check if user has a margin account, create one if they don't
        permissions = await exchange.get_permissions(private_key.public_key())
        if len(permissions['level_1']) == 0:
            margin_account = await exchange.create_margin_account(account, private_key)
        else:
            margin_account = permissions['level_1'][0]
        print('MARGIN ACCOUNT:', margin_account.as_str())

        # Create recovery key
        await exchange.create_recovery_key(account, private_key, margin_account)

        # Add collateral to margin account
        await exchange.add_collateral(
            account,
            private_key,
            margin_account,
            ret.Address(network_config['xrd']),
            ret.Decimal('100')
        )

        # Place a margin order to buy 0.001 BTC/USD with price and slippage limits
        await exchange.margin_order_request(
            account,
            private_key,
            margin_account,
            'BTC/USD',
            ret.Decimal('0.001'),
            price_limit=PriceLimit.gte(ret.Decimal('10000')),
            slippage_limit=SlippageLimit.percent(ret.Decimal('0.3'))
        )

        # Fetch various details about the exchange state
        pool_details = await exchange.pool_details()
        account_details = await exchange.account_details(margin_account)
        pair_details = await exchange.pair_details(['BTC/USD', 'ETH/USD'])

        # Cancel all active requests
        await exchange.cancel_requests(account, private_key, margin_account, [request['index'] for request in account_details['active_requests']])

        # Print the fetched details
        print(pool_details)
        print(account_details)
        print(pair_details)

if __name__ == '__main__':
    asyncio.run(main())