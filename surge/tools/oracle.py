import aiohttp
from typing import List
from .api import Api

DEFAULT_ORACLE_URL = 'https://hermes.pyth.network/v2'

class Oracle(Api):
    def __init__(self, session: aiohttp.ClientSession, base_url: str = DEFAULT_ORACLE_URL) -> None:
        super().__init__(session, base_url)

    async def get_crypto_feeds(self, pair_ids: List[str]) -> dict:
        feeds = {}
        data = await self.get('price_feeds')
        for pair_id in pair_ids:
            for feed in data:
                if pair_id == feed['attributes']['symbol'][7:]:
                    feeds[pair_id] = feed
                    break

        return feeds

    async def get_prices(self, pair_ids: List[str]) -> dict:
        feeds = await self.get_crypto_feeds(pair_ids)
        feed_ids = {feed['id']:pair_id for pair_id, feed in feeds.items()}

        prices = {}
        query = '?' + '&'.join([f'ids[]={feed_id}' for feed_id in feed_ids.keys()])
        data = await self.get(f'updates/price/latest{query}')
        for update in data['parsed']:
            pair_id = feed_ids[update['id']]
            sig = int(update['price']['price'])
            exp = int(update['price']['expo'])
            price = sig * 10 ** exp
            prices[pair_id] = price

        return prices