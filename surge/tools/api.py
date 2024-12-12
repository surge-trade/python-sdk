import aiohttp

class Api:
    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self.session = session
        self.gateway_url = base_url

    async def get(self, endpoint: str, headers: dict = None) -> dict:
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        async with self.session.get(
            f'{self.gateway_url}/{endpoint}',
            headers=headers
        ) as response:
            return await self._handle_response(response)

    async def post(self, endpoint: str, body: dict = None, headers: dict = None) -> dict:
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        if body is None:
            body = {}
            
        async with self.session.post(
            f'{self.gateway_url}/{endpoint}',
            json=body,
            headers=headers
        ) as response:
            return await self._handle_response(response)
            
    async def _handle_response(self, response: aiohttp.ClientResponse) -> dict:
        if response.status == 404:
            return None
        elif response.status >= 400:
            error_data = await response.json()
            raise Exception(f"API request failed with status {response.status}: {error_data}")
        
        try:
            return await response.json()
        except aiohttp.ContentTypeError:
            raise Exception("Invalid JSON response from API")
        except Exception as e:
            raise Exception(f"Error processing API response: {str(e)}")