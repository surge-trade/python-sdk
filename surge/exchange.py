"""
Main interface to the Surge protocol.

This module provides the Exchange class which handles all interactions with
the Surge protocol, including querying account details, managing positions,
and executing trades.
"""

from typing import List, Optional, Dict
import radix_engine_toolkit as ret

from .tools.gateway import Gateway
from .tools.oracle import Oracle
from .types import *

ENV_REGISTRY = ret.Address('component_tdx_2_1czj40n6730x4saae7mnpe20htre57rdwvzvnfcuvcusy9s0jn6qqmf')

class Exchange:
    """
    Main interface for interacting with the Surge protocol.
    
    This class provides methods to:
    - Query account details and positions
    - Get pool and pair information
    - Create trading accounts
    - Place and manage orders
    - Handle collateral
    """

    def __init__(self, gateway: Gateway, oracle: Oracle, env_registry: ret.Address = ENV_REGISTRY) -> None:
        """
        Initialize the Exchange interface.

        Args:
            gateway: Gateway instance for interacting with the Radix network
            oracle: Oracle instance for getting price data
            env_registry: Address of the environment registry component
        """
        self.env_registry = env_registry
        self.gateway = gateway
        self.oracle = oracle

    async def load_variables(self) -> Dict[str, str]:
        """
        Load protocol component addresses from the environment registry.

        Returns:
            Dict mapping variable names to component addresses
        """
        variables = [
            "protocol_resource",
            "lp_resource",
            "referral_resource",
            "recovery_key_resource",
            "base_resource",
            "keeper_reward_resource",
            "fee_oath_resource",
            "token_wrapper_component",
            "config_component",
            "pool_component",
            "referral_generator_component",
            "permission_registry_component",
            "oracle_component",
            "fee_distributor_component",
            "fee_delegator_component",
            "exchange_component",
            "account_package",
        ]

        manifest = ret.ManifestV1Builder()
        manifest = manifest.call_method(
            ret.ManifestBuilderAddress.STATIC(self.env_registry),
            'get_variables',
            [ret.ManifestBuilderValue.ARRAY_VALUE(ret.ManifestBuilderValueKind.STRING_VALUE, [
                ret.ManifestBuilderValue.STRING_VALUE(variable) for variable in variables
            ])]
        )

        result = await self.gateway.preview_transaction(manifest)
        variables = {}
        for elem in result['receipt']['output'][0]['programmatic_json']['entries']:
            key = elem['key']['value']
            value = elem['value']['value']
            variables[key] = value

        for key, value in variables.items():
            setattr(self, key, ret.Address(value))

        return variables
        
    async def account_details(self, account: ret.Address) -> AccountDetails:
        """
        Get detailed information about a margin trading account.

        Args:
            account: Address of the margin trading account

        Returns:
            AccountDetails containing positions, collateral, and account overview
        """
        manifest = ret.ManifestV1Builder()
        manifest = manifest.call_method(
            ret.ManifestBuilderAddress.STATIC(self.exchange_component),
            'get_account_details',
            [
                ret.ManifestBuilderValue.ADDRESS_VALUE(ret.ManifestBuilderAddress.STATIC(account)),
                ret.ManifestBuilderValue.U64_VALUE(30),
                ret.ManifestBuilderValue.ENUM_VALUE(0, []),
            ]
        )
        result = await self.gateway.preview_transaction(manifest)
        result = result['receipt']['output'][0]['programmatic_json']['fields']

        pair_ids = AccountDetails.get_pair_ids(result)
        prices = await self.oracle.get_prices(pair_ids)
        
        return AccountDetails.from_json(result, prices)
            
    async def pool_details(self) -> PoolDetails:
        """
        Get details about the protocol's liquidity pool.

        Returns:
            PoolDetails containing pool state and metrics
        """
        manifest = ret.ManifestV1Builder()
        manifest = manifest.call_method(
            ret.ManifestBuilderAddress.STATIC(self.exchange_component),
            'get_pool_details',
            []
        )
        result = await self.gateway.preview_transaction(manifest)
        result = result['receipt']['output'][0]['programmatic_json']['fields']
        return PoolDetails.from_json(result)
    
    async def pair_details(self, pair_ids: List[str]) -> List[PairDetails]:
        """
        Get detailed information about trading pairs.

        Args:
            pair_ids: List of pair IDs to query (e.g. ["BTC-USD", "ETH-USD"])

        Returns:
            List of PairDetails containing pair state and configuration
        """
        manifest = ret.ManifestV1Builder()
        manifest = manifest.call_method(
            ret.ManifestBuilderAddress.STATIC(self.exchange_component),
            'get_pair_details',
            [ret.ManifestBuilderValue.ARRAY_VALUE(ret.ManifestBuilderValueKind.STRING_VALUE, [
                ret.ManifestBuilderValue.STRING_VALUE(pair_id) for pair_id in pair_ids
            ])]
        )
        result = await self.gateway.preview_transaction(manifest)
        prices = await self.oracle.get_prices(pair_ids)
        
        return [
            PairDetails.from_json(elem, prices) 
            for elem in result['receipt']['output'][0]['programmatic_json']['elements']
        ]
    
    async def get_permissions(self, public_key: ret.PublicKey) -> Permissions:
        """
        Get the permissions of an account.
        """
        network_config = await self.gateway.network_configuration()

        public_key_hash = ret.Hash.from_unhashed_bytes(public_key.value).as_str()[-58:]
        rule = f'{network_config["ed25519_virtual_badge"]}:[{public_key_hash}]'

        manifest = f'''
            CALL_METHOD
                Address("{self.exchange_component.as_str()}")
                "get_permissions"
                Enum<2u8>(
                    Enum<0u8>(
                        Enum<0u8>(
                            Enum<0u8>(
                                NonFungibleGlobalId("{rule}")
                            )
                        )
                    )
                )
            ;
        '''

        result = await self.gateway.preview_transaction(manifest)
        result = result['receipt']['output'][0]['programmatic_json']['fields']
        return Permissions.from_json(result)
    
    async def create_margin_account(
            self, 
            account: ret.Address, 
            private_key: ret.PrivateKey,
        ) -> ret.Address:
        """
        Create a new margin trading account.

        Args:
            account: Account that will own the trading account
            private_key: Private key to sign the transaction

        Returns:
            Address of the newly created trading account
        """
        network_config = await self.gateway.network_configuration()

        public_key_hash = ret.Hash.from_unhashed_bytes(private_key.public_key().value).as_str()[-58:]
        initial_rule = f'{network_config["ed25519_virtual_badge"]}:[{public_key_hash}]'

        manifest = f'''
            CALL_METHOD
                Address("{account.as_str()}")
                "lock_fee"
                Decimal("10")
            ;
            CALL_METHOD
                Address("{self.exchange_component.as_str()}")
                "create_account"
                Enum<0u8>()
                Enum<2u8>(
                    Enum<0u8>(
                        Enum<0u8>(
                            Enum<0u8>(
                                NonFungibleGlobalId("{initial_rule}")
                            )
                        )
                    )
                )
                Array<Bucket>()
                Enum<0u8>()
                Enum<0u8>()
            ;
        '''

        payload, intent = await self.gateway.build_transaction(manifest, private_key)
        await self.gateway.submit_transaction(payload)
        await self.gateway.get_transaction_status(intent)
        addresses = await self.gateway.get_new_addresses(intent)
        trading_account_component = addresses[0]
        return ret.Address(trading_account_component)
    
    async def create_recovery_key(
            self, 
            account: ret.Address, 
            private_key: ret.PrivateKey,
            margin_account: ret.Address
        ) -> None:
        """
        Create a recovery key for a margin account.

        Args:
            account: Account submitting the transaction
            private_key: Private key to sign the transaction
            margin_account: Margin account to create the recovery key for
        """
        builder = ret.ManifestV1Builder()
        builder = builder.account_lock_fee(account, ret.Decimal('10'))
        builder = builder.call_method(
            ret.ManifestBuilderAddress.STATIC(self.exchange_component),
            'create_recovery_key',
            [
                ret.ManifestBuilderValue.ENUM_VALUE(0, []),  # Fee oath
                ret.ManifestBuilderValue.ADDRESS_VALUE(ret.ManifestBuilderAddress.STATIC(margin_account)),  # Margin account
            ]
        )
        builder = builder.account_deposit_entire_worktop(account)

        payload, intent = await self.gateway.build_transaction(builder, private_key)
        await self.gateway.submit_transaction(payload)
        await self.gateway.get_transaction_status(intent)
    
    async def add_collateral(
            self, 
            account: ret.Address, 
            private_key: ret.PrivateKey, 
            margin_account: ret.Address, 
            resource: ret.Address, 
            amount: ret.Decimal,
        ) -> None:
        """
        Add collateral to a margin account.

        Args:
            account: Account submitting the transaction
            private_key: Private key to sign the transaction 
            margin_account: Margin account to add collateral to
            resource: Resource address of the collateral to add
            amount: Amount of collateral to add
        """
        builder = ret.ManifestV1Builder()
        builder = builder.account_lock_fee(account, ret.Decimal('10'))
        builder = builder.account_withdraw(account, resource, amount)
        builder = builder.take_all_from_worktop(resource, ret.ManifestBuilderBucket('bucket1'))
        builder = builder.call_method(
            ret.ManifestBuilderAddress.STATIC(self.exchange_component),
            'add_collateral',
            [
                ret.ManifestBuilderValue.ENUM_VALUE(0, []), # Fee oath
                ret.ManifestBuilderValue.ADDRESS_VALUE(ret.ManifestBuilderAddress.STATIC(margin_account)), # Margin account
                ret.ManifestBuilderValue.ARRAY_VALUE(ret.ManifestBuilderValueKind.BUCKET_VALUE, [ # Tokens
                    ret.ManifestBuilderValue.BUCKET_VALUE(ret.ManifestBuilderBucket('bucket1'))
                ]),
            ]
        )

        payload, intent = await self.gateway.build_transaction(builder, private_key)
        await self.gateway.submit_transaction(payload)
        await self.gateway.get_transaction_status(intent)

    async def remove_collateral_request(
            self, 
            account: ret.Address, 
            private_key: ret.PrivateKey, 
            margin_account: ret.Address, 
            resource: ret.Address, 
            amount: ret.Decimal
        ) -> None:
        """
        Request to remove collateral from a margin account.

        Args:
            account: Account submitting the transaction
            private_key: Private key to sign the transaction
            margin_account: Margin account to remove collateral from
            resource: Resource address of the collateral to remove
            amount: Amount of collateral to remove
        """
        builder = ret.ManifestV1Builder()
        builder = builder.account_lock_fee(account, ret.Decimal('10'))
        builder = builder.call_method(
            ret.ManifestBuilderAddress.STATIC(self.exchange_component),
            'remove_collateral_request',
            [
                ret.ManifestBuilderValue.ENUM_VALUE(0, []), # Fee oath
                ret.ManifestBuilderValue.U64_VALUE(10000000000), # Expiry seconds
                ret.ManifestBuilderValue.ADDRESS_VALUE(ret.ManifestBuilderAddress.STATIC(margin_account)), # Margin account
                ret.ManifestBuilderValue.ADDRESS_VALUE(ret.ManifestBuilderAddress.STATIC(account)), # Target account
                ret.ManifestBuilderValue.ARRAY_VALUE(ret.ManifestBuilderValueKind.TUPLE_VALUE, [ # Claims
                    ret.ManifestBuilderValue.TUPLE_VALUE([
                        ret.ManifestBuilderValue.ADDRESS_VALUE(ret.ManifestBuilderAddress.STATIC(resource)),
                        ret.ManifestBuilderValue.DECIMAL_VALUE(amount),
                    ]),
                ])
            ]
        )

        payload, intent = await self.gateway.build_transaction(builder, private_key)
        await self.gateway.submit_transaction(payload)
        await self.gateway.get_transaction_status(intent)

    async def margin_order_request(
            self, 
            account: ret.Address, 
            private_key: ret.PrivateKey, 
            margin_account: ret.Address, 
            pair: str, 
            size: ret.Decimal, 
            reduce_only: bool = False, 
            price_limit: Optional[PriceLimit] = None, 
            slippage_limit: Optional[SlippageLimit] = None
        ) -> None:
        """
        Submit a margin order request.

        Args:
            account: Account submitting the transaction
            margin_account: Trading account to use
            private_key: Private key to sign the transaction
            pair: Trading pair (e.g. "BTC-USD")
            size: Order size (positive for long, negative for short)
            reduce_only: Whether the order can only reduce position size
            price_limit: Optional price limit for the order
            slippage_limit: Optional slippage limit for the order
        """
        builder = ret.ManifestV1Builder()
        builder = builder.account_lock_fee(account, ret.Decimal('10'))
        builder = builder.call_method(
            ret.ManifestBuilderAddress.STATIC(self.exchange_component),
            'margin_order_request',
            [
                ret.ManifestBuilderValue.ENUM_VALUE(0, []),  # Fee oath
                ret.ManifestBuilderValue.U64_VALUE(0),  # Delay seconds
                ret.ManifestBuilderValue.U64_VALUE(10000000000),  # Expiry seconds
                ret.ManifestBuilderValue.ADDRESS_VALUE(ret.ManifestBuilderAddress.STATIC(margin_account)),  # Margin account
                ret.ManifestBuilderValue.STRING_VALUE(pair),  # Pair
                ret.ManifestBuilderValue.DECIMAL_VALUE(size),  # Size
                ret.ManifestBuilderValue.BOOL_VALUE(reduce_only),  # Reduce only
                (price_limit or PriceLimit.none()).to_manifest_value(),  # Price limit
                (slippage_limit or SlippageLimit.none()).to_manifest_value(),  # Slippage limit
                ret.ManifestBuilderValue.ARRAY_VALUE(ret.ManifestBuilderValueKind.ENUM_VALUE, []),  # Activate requests
                ret.ManifestBuilderValue.ARRAY_VALUE(ret.ManifestBuilderValueKind.ENUM_VALUE, []), # Cancel requests
                ret.ManifestBuilderValue.U8_VALUE(1), # Status
            ]
        )

        payload, intent = await self.gateway.build_transaction(builder, private_key)
        await self.gateway.submit_transaction(payload)
        await self.gateway.get_transaction_status(intent)

    async def margin_order_tp_sl_request(
            self, 
            account: ret.Address, 
            private_key: ret.PrivateKey, 
            margin_account: ret.Address, 
            pair: str, 
            size: ret.Decimal, 
            reduce_only: bool = False, 
            price_limit: Optional[PriceLimit] = None, 
            slippage_limit: Optional[SlippageLimit] = None,
            price_tp: Optional[ret.Decimal] = None,
            price_sl: Optional[ret.Decimal] = None
        ) -> None:
        """
        Submit a margin order with take profit and stop loss request.

        Args:
            account: Account submitting the transaction
            margin_account: Trading account to use
            private_key: Private key to sign the transaction
            pair: Trading pair (e.g. "BTC-USD")
            size: Order size (positive for long, negative for short)
            reduce_only: Whether the order can only reduce position size
            price_limit: Optional price limit for the order
            slippage_limit: Optional slippage limit for the order
            price_tp: Optional take profit price
            price_sl: Optional stop loss price
        """
        if price_tp is not None:
            price_tp = ret.ManifestBuilderValue.ENUM_VALUE(1, [ret.ManifestBuilderValue.DECIMAL_VALUE(price_tp)])
        else:
            price_tp = ret.ManifestBuilderValue.ENUM_VALUE(0, [])
        if price_sl is not None:
            price_sl = ret.ManifestBuilderValue.ENUM_VALUE(1, [ret.ManifestBuilderValue.DECIMAL_VALUE(price_sl)])
        else:
            price_sl = ret.ManifestBuilderValue.ENUM_VALUE(0, [])

        builder = ret.ManifestV1Builder()
        builder = builder.account_lock_fee(account, ret.Decimal('10'))
        builder = builder.call_method(
            ret.ManifestBuilderAddress.STATIC(self.exchange_component),
            'margin_order_tp_sl_request',
            [
                ret.ManifestBuilderValue.ENUM_VALUE(0, []),  # Fee oath
                ret.ManifestBuilderValue.U64_VALUE(0),  # Delay seconds
                ret.ManifestBuilderValue.U64_VALUE(10000000000),  # Expiry seconds
                ret.ManifestBuilderValue.ADDRESS_VALUE(ret.ManifestBuilderAddress.STATIC(margin_account)),  # Margin account
                ret.ManifestBuilderValue.STRING_VALUE(pair),  # Pair
                ret.ManifestBuilderValue.DECIMAL_VALUE(size),  # Size
                ret.ManifestBuilderValue.BOOL_VALUE(reduce_only),  # Reduce only
                (price_limit or PriceLimit.none()).to_manifest_value(),  # Price limit
                (slippage_limit or SlippageLimit.none()).to_manifest_value(),  # Slippage limit
                price_tp,  # Price TP
                price_sl,  # Price SL
            ]
        )

        payload, intent = await self.gateway.build_transaction(builder, private_key)
        await self.gateway.submit_transaction(payload)
        await self.gateway.get_transaction_status(intent)

    async def cancel_requests(
            self, 
            account: ret.Address, 
            private_key: ret.PrivateKey, 
            margin_account: ret.Address, 
            indexes: List[int]
        ) -> None:
        """
        Cancel active requests.

        Args:
            account: Account submitting the transaction
            private_key: Private key to sign the transaction 
            margin_account: Trading account containing the requests
            indexes: List of request indexes to cancel
        """

        builder = ret.ManifestV1Builder()
        builder = builder.account_lock_fee(account, ret.Decimal('10'))
        builder = builder.call_method(
            ret.ManifestBuilderAddress.STATIC(self.exchange_component),
            'cancel_requests',
            [
                ret.ManifestBuilderValue.ENUM_VALUE(0, []),  # Fee oath
                ret.ManifestBuilderValue.ADDRESS_VALUE(ret.ManifestBuilderAddress.STATIC(margin_account)),  # Margin account
                ret.ManifestBuilderValue.ARRAY_VALUE(ret.ManifestBuilderValueKind.U64_VALUE, [ # Indexes
                    ret.ManifestBuilderValue.U64_VALUE(index) for index in indexes
                ]),  
            ]
        )

        payload, intent = await self.gateway.build_transaction(builder, private_key)
        await self.gateway.submit_transaction(payload)
        await self.gateway.get_transaction_status(intent)

