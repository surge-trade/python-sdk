import aiohttp
from typing import List
from .api import Api

DEFAULT_ORACLE_URL = 'https://oracle.surge.trade'

class Oracle(Api):
    def __init__(self, session: aiohttp.ClientSession, base_url: str = DEFAULT_ORACLE_URL) -> None:
        super().__init__(session, base_url)

    async def get_prices(self) -> dict:
        data = await self.get(f'price_latest')
        prices = {}
        for item in data['prices']:
            pair_id = item['pair']
            price = float(item['quote'])
            prices[pair_id] = price

        return prices