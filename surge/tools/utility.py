"""Utility functions for the Surge protocol."""

def calculate_funding_rates(
    oi_long: float,
    oi_short: float, 
    skew: float,
    funding_2_raw: float,
    price: float,
    pair_config: dict
) -> dict:
    """Calculate funding rates for a trading pair.
    
    Calculates various funding rates based on market conditions including
    skew-based funding, pool funding, and final rates for longs/shorts.
    
    Args:
        oi_long: Total long open interest
        oi_short: Total short open interest
        skew: Current market skew (oi_long - oi_short) * price
        funding_2_raw: Raw secondary funding before limits
        price: Current market price
        pair_config: Trading pair configuration parameters
    
    Returns:
        dict: Calculated funding rates containing:
            funding_1: Base funding amount
            funding_2: Secondary funding amount
            funding_2_raw: Raw secondary funding
            funding_2_max: Maximum secondary funding
            funding_2_min: Minimum secondary funding
            funding_long_apr: Annual funding rate for longs
            funding_long_24h: 24h funding rate for longs
            funding_short_apr: Annual funding rate for shorts
            funding_short_24h: 24h funding rate for shorts
            funding_pool_24h: 24h funding rate for pool
    """
    # Calculate base funding components
    funding_1 = skew * pair_config['funding_1']
    funding_2_max = oi_long * price
    funding_2_min = -oi_short * price
    funding_2 = min(max(funding_2_raw, funding_2_min), funding_2_max) * pair_config['funding_2']
    
    # Handle zero open interest case
    if oi_long == 0 or oi_short == 0:
        funding_long = 0
        funding_short = 0
        funding_share = 0
        funding_pool = 0
    else:
        # Calculate funding based on market direction
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

        # Calculate pool funding
        oi_net = oi_long + oi_short
        funding_pool_0 = oi_net * price * pair_config['funding_pool_0']
        funding_pool_1 = abs(skew) * pair_config['funding_pool_1']
        funding_pool = funding_pool_0 + funding_pool_1
        funding_pool_index = funding_pool / oi_net

        # Calculate final funding rates
        funding_long = (funding_long_index + funding_pool_index) / price
        funding_short = (funding_short_index + funding_pool_index) / price
        funding_pool += funding_share

    return {
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
    } 
