"""
Types and data structures for the Surge protocol.

This module contains all the TypedDict and Enum definitions used to represent
Surge protocol data structures, along with methods to parse JSON responses from
the protocol into these types.
"""

import radix_engine_toolkit as ret
from typing import TypedDict, List, Optional, Union, Dict
from enum import Enum, auto
from dataclasses import dataclass

class RequestClaim(TypedDict):
    """A claim for removing collateral from a margin account."""
    resource: str  # Resource address
    size: float    # Amount to remove

class RemoveCollateralDetails(TypedDict):
    """Details for a remove collateral request."""
    target_account: str           # Account to send collateral to
    claims: List[RequestClaim]    # List of claims to remove

class RequestType(str, Enum):
    """Types of requests that can be made to the protocol."""
    REMOVE_COLLATERAL = 'Remove Collateral'
    MARKET_LONG = 'Market Long'
    MARKET_SHORT = 'Market Short'
    STOP_LONG = 'Stop Long'
    LIMIT_SHORT = 'Limit Short'
    LIMIT_LONG = 'Limit Long'
    STOP_SHORT = 'Stop Short'
    UNKNOWN = 'Unknown'

class RequestStatus(str, Enum):
    """Status of a request in the protocol."""
    DORMANT = 'Dormant'     # Request is waiting to be activated
    ACTIVE = 'Active'       # Request is active and can be executed
    EXECUTED = 'Executed'   # Request has been executed successfully
    CANCELED = 'Canceled'   # Request was canceled
    EXPIRED = 'Expired'     # Request expired before execution
    FAILED = 'Failed'       # Request failed during execution
    UNKNOWN = 'Unknown'     # Unknown status

class Position(TypedDict):
    """A margin trading position."""
    pair: str                   # Trading pair (e.g. "BTC/USD")
    size: float                 # Position size (positive for long, negative for short)
    value: float                # Current value of position
    entry_price: float          # Average entry price
    mark_price: float           # Current market price
    margin: float               # Required margin
    margin_maintenance: float   # Maintenance margin requirement
    pnl: float                  # Unrealized profit/loss
    roi: float                  # Return on investment (%)

    @staticmethod
    def from_json(elem: dict, prices: Dict[str, float]) -> 'Position':
        """Parse a position from JSON response."""
        fields = elem['fields']
        pair = fields[0]['value']
        size = float(fields[1]['value'])
        margin = float(fields[2]['value'])
        margin_maintenance = float(fields[3]['value'])
        cost = float(fields[4]['value'])
        funding = float(fields[5]['value'])

        mark_price = prices[pair]
        entry_price = cost / size
        value = size * mark_price
        margin = margin * mark_price
        margin_maintenance = margin_maintenance * mark_price
        pnl = value - cost - funding
        roi = pnl / abs(cost) * 100

        return {
            'pair': pair,
            'size': size,
            'value': value,
            'entry_price': entry_price,
            'mark_price': mark_price,
            'margin': margin,
            'margin_maintenance': margin_maintenance,
            'pnl': pnl,
            'roi': roi,
        }

class Collateral(TypedDict):
    """
    Represents collateral deposited in a margin account.
    
    Collateral is used to back margin trading positions and can be
    discounted based on the pair it's being used for.
    """
    pair: str                 # Pair used to value the collateral
    resource: str             # Resource address of the collateral token
    mark_price: float         # Current market price of the collateral
    amount: float             # Amount of collateral tokens
    value: float              # Total value of collateral (amount * mark_price)
    discount: float           # Discount factor applied to collateral value
    value_discounted: float   # Discounted value used for margin calculations
    margin: float             # Margin contribution of this collateral

    @staticmethod
    def from_json(elem: dict, prices: Dict[str, float]) -> 'Collateral':
        fields = elem['fields']
        pair = fields[0]['value']
        resource = fields[1]['value']
        amount = float(fields[2]['value'])
        discount = float(fields[3]['value'])
        margin = float(fields[4]['value'])

        mark_price = prices[pair]
        value = amount * mark_price
        value_discounted = value * discount
        margin = margin * mark_price

        return {
            'pair': pair,
            'resource': resource,
            'mark_price': mark_price,
            'amount': amount,
            'value': value,
            'discount': discount,
            'value_discounted': value_discounted,
            'margin': margin,
        }

class AccountOverview(TypedDict):
    """
    Overview of a margin account's financial status.
    
    Contains aggregated values and risk metrics calculated from
    the account's positions and collateral.
    """
    account_value: float                # Total account value including PnL
    account_value_discounted: float     # Account value with discounted collateral
    available_margin: float             # Margin available for new positions
    available_margin_maintenance: float # Margin available before liquidation
    balance: float                      # Account balance without positions
    total_pnl: float                    # Total unrealized profit/loss
    total_margin: float                 # Total margin required
    total_margin_maintenance: float     # Total maintenance margin required
    total_collateral_value: float       # Total value of all collateral
    total_collateral_value_discounted: float    # Total discounted collateral value

    @staticmethod
    def from_positions_and_collaterals(
        balance: float,
        positions: List[Position],
        collaterals: List[Collateral]
    ) -> 'AccountOverview':
        total_pnl = sum(p['pnl'] for p in positions)
        total_margin = sum(p['margin'] for p in positions) + sum(c['margin'] for c in collaterals)
        total_margin_maintenance = sum(p['margin_maintenance'] for p in positions) + sum(c['margin'] for c in collaterals)
        total_collateral_value = sum(c['value'] for c in collaterals)
        total_collateral_value_discounted = sum(c['value_discounted'] for c in collaterals)

        account_value = balance + total_pnl + total_collateral_value
        account_value_discounted = balance + total_pnl + total_collateral_value_discounted
        available_margin = account_value_discounted - total_margin
        available_margin_maintenance = account_value_discounted - total_margin_maintenance

        return {
            'account_value': account_value,
            'account_value_discounted': account_value_discounted,
            'available_margin': available_margin,
            'available_margin_maintenance': available_margin_maintenance,
            'balance': balance,
            'total_pnl': total_pnl,
            'total_margin': total_margin,
            'total_margin_maintenance': total_margin_maintenance,
            'total_collateral_value': total_collateral_value,
            'total_collateral_value_discounted': total_collateral_value_discounted,
        }

class PoolDetails(TypedDict):
    """
    Details about the protocol's liquidity pool.
    
    The liquidity pool provides counterparty for all trades and
    collects fees and funding payments.
    """
    token_amount: str              # Real sUSD balance
    balance: str                   # Virtual sUSD balance
    unrealized_pool_funding: str   # Unrealized funding payments balance
    pnl_snap: str                  # Snapshot of pool's PnL
    skew_ratio: str                # Current pool skew ratio
    skew_ratio_cap: str            # Maximum allowed skew ratio
    lp_supply: str                 # Total supply of LP token
    lp_price: str                  # Current price of LP token

    @staticmethod
    def from_json(result: List[dict]) -> 'PoolDetails':
        return {
            'token_amount': result[0]['value'],
            'balance': result[1]['value'],
            'unrealized_pool_funding': result[2]['value'],
            'pnl_snap': result[3]['value'],
            'skew_ratio': result[4]['value'],
            'skew_ratio_cap': result[5]['value'],
            'lp_supply': result[6]['value'],
            'lp_price': result[7]['value'],
        }

class PairConfig(TypedDict):
    """
    Configuration parameters for a trading pair.
    
    These parameters control trading limits, fees, funding rates,
    and other pair-specific behavior.
    """
    pair: str                       # Trading pair (e.g. "BTC/USD")
    price_max_age: int              # Maximum age of price data allowed (in seconds)
    oi_max: float                   # Maximum open interest allowed per side (in tokens)
    trade_size_min: float           # Minimum trade size (in tokens)
    update_price_delta_ratio: float # Price threshold for pair update
    update_period_seconds: float    # Time threshold for pair update (in seconds)
    margin: float                  # Initial margin requirement
    margin_maintenance: float      # Maintenance margin requirement
    funding_1: float               # Skew funding rate parameter
    funding_2: float               # Skew integral funding rate parameter
    funding_2_delta: float         # Skew integral growth rate parameter
    funding_2_decay: float         # Skew integral decay rate parameter
    funding_pool_0: float          # Constant pool funding rate parameter
    funding_pool_1: float          # Skew pool funding rate parameter
    funding_share: float           # Share of funding paid to pool
    fee_0: float                   # Base trading fee
    fee_1: float                   # Price impact trading fee

    @staticmethod
    def from_json(fields: List[dict]) -> 'PairConfig':
        return {
            'pair': fields[0]['value'],
            'price_max_age': int(fields[1]['value']),
            'oi_max': float(fields[2]['value']),
            'trade_size_min': float(fields[3]['value']),
            'update_price_delta_ratio': float(fields[4]['value']),
            'update_period_seconds': float(fields[5]['value']),
            'margin': float(fields[6]['value']),
            'margin_maintenance': float(fields[7]['value']),
            'funding_1': float(fields[8]['value']),
            'funding_2': float(fields[9]['value']),
            'funding_2_delta': float(fields[10]['value']),
            'funding_2_decay': float(fields[11]['value']),
            'funding_pool_0': float(fields[12]['value']),
            'funding_pool_1': float(fields[13]['value']),
            'funding_share': float(fields[14]['value']),
            'fee_0': float(fields[15]['value']),
            'fee_1': float(fields[16]['value']),
        }

class PairDetails(TypedDict):
    """
    Detailed information about a trading pair's current state.
    
    Includes open interest, funding rates, and other metrics that
    affect trading conditions.
    """
    pair: str                     # Trading pair (e.g. "BTC/USD")
    oi_long: float                # Total long open interest
    oi_short: float               # Total short open interest
    oi_net: float                 # Net open interest
    cost: float                   # Total cost basis of positions
    skew: float                   # Current market skew
    funding_1: float              # Current base funding amount
    funding_2: float              # Current secondary funding amount
    funding_2_raw: float          # Raw secondary funding before limits
    funding_2_max: float          # Maximum secondary funding
    funding_2_min: float          # Minimum secondary funding
    funding_long_apr: float       # Annual funding rate for longs
    funding_long_24h: float       # 24h funding rate for longs
    funding_short_apr: float      # Annual funding rate for shorts
    funding_short_24h: float      # 24h funding rate for shorts
    funding_pool_24h: float       # 24h funding rate for pool
    pair_config: PairConfig       # Pair configuration parameters

    @staticmethod
    def from_json(elem: dict, prices: Dict[str, float]) -> 'PairDetails':
        fields = elem['fields']
        pair = fields[0]['value']
        
        pool_position = fields[1]['fields']
        oi_long = float(pool_position[0]['value'])
        oi_short = float(pool_position[1]['value'])
        cost = float(pool_position[2]['value'])
        funding_2_raw = float(pool_position[5]['value'])

        pair_config = PairConfig.from_json(fields[2]['fields'])
        price = prices[pair]
        oi_net = oi_long + oi_short
        skew = (oi_long - oi_short) * price

        funding_1 = skew * pair_config['funding_1']
        funding_2_max = oi_long * price
        funding_2_min = -oi_short * price
        funding_2 = min(max(funding_2_raw, funding_2_min), funding_2_max) * pair_config['funding_2']
        
        if oi_long == 0 or oi_short == 0:
            funding_long = 0
            funding_short = 0
            funding_share = 0
            funding_pool = 0
        else:
            funding = funding_1 + funding_2
            if funding > 0:
                funding_long = funding
                funding_share = funding_long * pair_config['funding_share']
                funding_long_index = funding_long / oi_long
                funding_short_index = -(funding_long - funding_share) / oi_short
            else:
                funding_short = -funding
                funding_share = funding_short * pair_config['funding_share']
                funding_long_index = -(funding_short - funding_share) / oi_long
                funding_short_index = funding_short / oi_short

            funding_pool_0 = oi_net * price * pair_config['funding_pool_0']
            funding_pool_1 = abs(skew) * pair_config['funding_pool_1']
            funding_pool = funding_pool_0 + funding_pool_1
            funding_pool_index = funding_pool / oi_net

            funding_long = (funding_long_index + funding_pool_index) / price
            funding_short = (funding_short_index + funding_pool_index) / price
            funding_pool += funding_share

        return {
            'pair': pair,
            'oi_long': oi_long,
            'oi_short': oi_short,
            'oi_net': oi_net,
            'cost': cost,
            'skew': skew,
            'funding_1': funding_1,
            'funding_2': funding_2,
            'funding_2_raw': funding_2_raw,
            'funding_2_max': funding_2_max,
            'funding_2_min': funding_2_min,
            'funding_long_apr': funding_long,
            'funding_long_24h': funding_long / 365,
            'funding_short_apr': funding_short,
            'funding_short_24h': funding_short / 365,
            'funding_pool_24h': funding_pool / 365,
            'pair_config': pair_config,
        }

@dataclass
class GteLimit:
    value: ret.Decimal

@dataclass
class LteLimit:
    value: ret.Decimal

class PriceLimit:
    """
    Represents a price limit condition:
    None - No price limit
    Gte(value) - Price must be greater than or equal to value
    Lte(value) - Price must be less than or equal to value
    """
    class Type(Enum):
        NONE = auto()
        GTE = auto()
        LTE = auto()

    def __init__(self, type_: Type, value: Optional[ret.Decimal] = None):
        self.type = type_
        self.value = value

    def __str__(self) -> str:
        if self.type == PriceLimit.Type.NONE:
            return "None"
        elif self.type == PriceLimit.Type.GTE:
            return f"Gte({self.value.as_str()})"
        else:  # LTE
            return f"Lte({self.value.as_str()})"

    def __repr__(self) -> str:
        return f"PriceLimit.{str(self)}"

    @staticmethod
    def none() -> 'PriceLimit':
        return PriceLimit(PriceLimit.Type.NONE)

    @staticmethod
    def gte(value: ret.Decimal) -> 'PriceLimit':
        return PriceLimit(PriceLimit.Type.GTE, value)

    @staticmethod
    def lte(value: ret.Decimal) -> 'PriceLimit':
        return PriceLimit(PriceLimit.Type.LTE, value)

    def to_manifest_value(self) -> ret.ManifestBuilderValue:
        if self.type == PriceLimit.Type.NONE:
            return ret.ManifestBuilderValue.ENUM_VALUE(0, [])
        elif self.type == PriceLimit.Type.GTE:
            return ret.ManifestBuilderValue.ENUM_VALUE(1, [
                ret.ManifestBuilderValue.DECIMAL_VALUE(self.value)
            ])
        else:  # LTE
            return ret.ManifestBuilderValue.ENUM_VALUE(2, [
                ret.ManifestBuilderValue.DECIMAL_VALUE(self.value)
            ])

    @staticmethod
    def from_json(json_data: dict) -> 'PriceLimit':
        variant_id = int(json_data['variant_id'])
        if variant_id == 0:
            return PriceLimit.none()
        elif variant_id == 1:
            value = ret.Decimal(json_data['fields'][0]['value'])
            return PriceLimit.gte(value)
        else:
            value = ret.Decimal(json_data['fields'][0]['value'])
            return PriceLimit.lte(value)

class SlippageLimit:
    """
    Represents a slippage limit condition:
    None - No slippage limit
    Percent(value) - Maximum slippage as a percentage
    Absolute(value) - Maximum slippage as an absolute value
    """
    class Type(Enum):
        NONE = auto()
        PERCENT = auto()
        ABSOLUTE = auto()

    def __init__(self, type_: Type, value: Optional[ret.Decimal] = None):
        self.type = type_
        self.value = value

    def __str__(self) -> str:
        if self.type == SlippageLimit.Type.NONE:
            return "None"
        elif self.type == SlippageLimit.Type.PERCENT:
            return f"Percent({self.value})"
        else:  # ABSOLUTE
            return f"Absolute({self.value})"

    def __repr__(self) -> str:
        return f"SlippageLimit.{str(self)}"

    @staticmethod
    def none() -> 'SlippageLimit':
        return SlippageLimit(SlippageLimit.Type.NONE)

    @staticmethod
    def percent(value: ret.Decimal) -> 'SlippageLimit':
        return SlippageLimit(SlippageLimit.Type.PERCENT, value)

    @staticmethod
    def absolute(value: ret.Decimal) -> 'SlippageLimit':
        return SlippageLimit(SlippageLimit.Type.ABSOLUTE, value)

    def to_manifest_value(self) -> ret.ManifestBuilderValue:
        if self.type == SlippageLimit.Type.NONE:
            return ret.ManifestBuilderValue.ENUM_VALUE(0, [])
        elif self.type == SlippageLimit.Type.PERCENT:
            return ret.ManifestBuilderValue.ENUM_VALUE(1, [
                ret.ManifestBuilderValue.DECIMAL_VALUE(self.value)
            ])
        else:  # ABSOLUTE
            return ret.ManifestBuilderValue.ENUM_VALUE(2, [
                ret.ManifestBuilderValue.DECIMAL_VALUE(self.value)
            ])

    @staticmethod
    def from_json(json_data: dict) -> 'SlippageLimit':
        variant_id = int(json_data['variant_id'])
        if variant_id == 0:
            return SlippageLimit.none()
        elif variant_id == 1:
            value = ret.Decimal(json_data['fields'][0]['value'])
            return SlippageLimit.percent(value)
        else:
            value = ret.Decimal(json_data['fields'][0]['value'])
            return SlippageLimit.absolute(value)

class MarginOrderDetails(TypedDict):
    """
    Details of a margin trading order request.
    
    Contains all parameters needed to execute a margin trade,
    including size, limits, and dependencies.
    """
    pair: str                                # Trading pair for the order (e.g. "BTC/USD")
    size: float                              # Order size (positive=long, negative=short)
    reduce_only: bool                        # Whether order can only reduce position
    limit_price: Optional[PriceLimit]        # Optional price limit condition
    limit_slippage: Optional[SlippageLimit]  # Optional slippage limit
    activate_requests: List[str]             # Requests to activate if executed
    cancel_requests: List[str]               # Requests to cancel if executed

class Request(TypedDict):
    """
    A request in the protocol's request queue.
    
    Requests can be for removing collateral or placing orders,
    and can have various states and conditions.
    """
    type: RequestType              # Type of request
    index: int                     # Unique request index
    submission: str                # When request was submitted
    expiry: str                    # When request expires
    status: RequestStatus          # Current status
    request_details: Optional[Union[RemoveCollateralDetails, MarginOrderDetails]]  # Request-specific details

    @staticmethod
    def from_json(elem: dict) -> 'Request':
        request = elem['fields']

        index = request[0]['value']
        submission = request[2]['value']
        expiry = request[3]['value']
        status_id = int(request[4]['value'])
        request_variant_id = int(request[1]['variant_id'])
        request_inner = request[1]['fields'][0]['fields']

        # Map status ID to enum
        status = {
            0: RequestStatus.DORMANT,
            1: RequestStatus.ACTIVE,
            2: RequestStatus.EXECUTED,
            3: RequestStatus.CANCELED,
            4: RequestStatus.EXPIRED,
            5: RequestStatus.FAILED
        }.get(status_id, RequestStatus.UNKNOWN)

        if request_variant_id == 0:
            type = RequestType.REMOVE_COLLATERAL
            target_account = request_inner[0]['value']

            claims: List[RequestClaim] = []
            for claim in request_inner[1]['elements']:
                claim = claim['fields']
                claims.append({
                    'resource': claim[0]['value'],
                    'size': claim[1]['value'],
                })

            request_details: RemoveCollateralDetails = {
                'target_account': target_account,
                'claims': claims,
            }
        elif request_variant_id == 1:
            pair_id = request_inner[0]['value']
            size = float(request_inner[1]['value'])
            reduce_only = bool(request_inner[2]['value'])
            
            limit_price = PriceLimit.from_json(request_inner[3])
            limit_slippage = SlippageLimit.from_json(request_inner[4])

            activate_requests = [i['value'] for i in request_inner[5]['elements']]
            cancel_requests = [i['value'] for i in request_inner[6]['elements']]

            type = {
                (PriceLimit.Type.NONE, True): RequestType.MARKET_LONG,
                (PriceLimit.Type.NONE, False): RequestType.MARKET_SHORT,
                (PriceLimit.Type.GTE, True): RequestType.STOP_LONG,
                (PriceLimit.Type.LTE, False): RequestType.LIMIT_SHORT,
                (PriceLimit.Type.LTE, True): RequestType.LIMIT_LONG,
                (PriceLimit.Type.GTE, False): RequestType.STOP_SHORT,
            }.get((limit_price.type, size >= 0), RequestType.UNKNOWN)

            request_details: MarginOrderDetails = {
                'pair': pair_id,
                'size': size,
                'reduce_only': reduce_only,
                'limit_price': limit_price,
                'limit_slippage': limit_slippage,
                'activate_requests': activate_requests,
                'cancel_requests': cancel_requests,
            }
        else:
            type = RequestType.UNKNOWN
            request_details = None

        return {
            'type': type,
            'index': index,
            'submission': submission,
            'expiry': expiry,
            'status': status,
            'request_details': request_details,
        }

class AccountDetails(TypedDict):
    """
    Complete details of a margin trading account.
    
    Contains all positions, collateral, requests, and calculated
    metrics for the account.
    """
    balance: float                  # sUSD account balance
    positions: List[Position]       # Open trading positions
    collaterals: List[Collateral]   # Collateral tokens
    valid_requests_start: str       # Start index for valid requests (inclusive)
    active_requests: List[Request]  # Currently active requests
    requests_history: List[Request] # Historical requests
    overview: AccountOverview       # Account overview metrics

    @staticmethod
    def from_json(result: List[dict], prices: Dict[str, float]) -> 'AccountDetails':
        balance = float(result[0]['value'])
        positions = [Position.from_json(elem, prices) for elem in result[1]['elements']]
        collaterals = [Collateral.from_json(elem, prices) for elem in result[2]['elements']]
        
        valid_requests_start = result[3]['value']
        active_requests = [Request.from_json(elem) for elem in result[4]['elements']]
        requests_history = [Request.from_json(elem) for elem in result[5]['elements']]

        overview = AccountOverview.from_positions_and_collaterals(balance, positions, collaterals)

        return {
            'balance': balance,
            'positions': positions,
            'collaterals': collaterals,
            'valid_requests_start': valid_requests_start,
            'active_requests': active_requests,
            'requests_history': requests_history,
            'overview': overview,
        }

    @staticmethod
    def get_pair_ids(result: List[dict]) -> set[str]:
        pair_ids = set()
        for elem in result[1]['elements']:
            pair_ids.add(elem['fields'][0]['value'])
        for elem in result[2]['elements']:
            pair_ids.add(elem['fields'][0]['value'])
        return pair_ids

class Permissions(TypedDict):
    """
    Margin account permissions.
    """
    level_1: List[ret.Address]  # Level 1 permissions
    level_2: List[ret.Address]  # Level 2 permissions
    level_3: List[ret.Address]  # Level 3 permissions

    @staticmethod
    def from_json(json_data: List[dict]) -> 'Permissions':
        return {
            'level_1': [ret.Address(elem['value']) for elem in json_data[0]['elements']],
            'level_2': [ret.Address(elem['value']) for elem in json_data[1]['elements']],
            'level_3': [ret.Address(elem['value']) for elem in json_data[2]['elements']],
        }
