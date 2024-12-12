import radix_engine_toolkit as ret
from typing import Tuple
import aiohttp
import random

from .api import Api

DEFAULT_GATEWAY_URL = 'https://mainnet.radixdlt.com'
DEFAULT_NETWORK_ID = 1

class Gateway(Api):
    def __init__(self, session: aiohttp.ClientSession, base_url: str = DEFAULT_GATEWAY_URL, network_id: int = DEFAULT_NETWORK_ID) -> None:
        super().__init__(session, base_url)
        self.network_id = network_id

    def random_nonce(self) -> int:
        return random.randint(0, 0xFFFFFFFF)
    
    async def ledger_state(self) -> dict:
        data = await self.post('transaction/construction')

        network = data['ledger_state']['network']
        if network == 'mainnet':
            network_id = 1
        elif network == 'stokenet':
            network_id = 2
        state_version = data['ledger_state']['state_version']
        epoch = data['ledger_state']['epoch']

        return {
            'network': network,
            'network_id': network_id,
            'state_version': state_version,
            'epoch': epoch,
        }
        
    async def network_configuration(self) -> str:
        data = await self.post('status/network-configuration')        
        return {
            'network_id': data['network_id'],
            'network_name': data['network_name'],
            'xrd': data['well_known_addresses']['xrd'],
            'faucet': data['well_known_addresses']['faucet'],
            'ed25519_virtual_badge': data['well_known_addresses']['ed25519_signature_virtual_badge'],
            'secp256k1_virtual_badge': data['well_known_addresses']['secp256k1_signature_virtual_badge'],
        }

    async def get_xrd_balance(self, account: ret.Address) -> float:
        network_config = await self.network_configuration()
        xrd = network_config['xrd']

        body = {
            'address': account.as_str(),
            'resource_address': xrd,
        }
        data = await self.post('state/entity/page/fungible-vaults/', body)
        amount = 0
        for item in data['items']:
            amount += float(item['amount'])
        return amount
        
    async def get_component_history(self, component: str, limit: int = 30) -> dict:
        body = {
            "limit_per_page": limit,
            "affected_global_entities_filter": [component],
            "opt_ins": {
                "receipt_events": True,
            }
        }
        data = await self.post('stream/transactions', body)
        return data

    async def submit_transaction(self, transaction: str) -> dict:
        body = {
            "notarized_transaction_hex": transaction
        }
        data = await self.post('transaction/submit', body)
        return data

    async def get_transaction_details(self, intent: str) -> dict:
        body = {
            'intent_hash': intent,
            "opt_ins": {
                "receipt_state_changes": True,
            },
        }
        data = await self.post('transaction/committed-details', body)
        return data
            
    async def get_new_addresses(self, intent: str) -> list:
        details = None
        while details is None:
            details = await self.get_transaction_details(intent)
        addresses = []
        for e in details['transaction']['receipt']['state_updates']['new_global_entities']:
            addresses.append(e['entity_address'])
        return addresses
    
    async def get_transaction_status(self, intent: str) -> dict:
        details = None
        while details is None:
            details = await self.get_transaction_details(intent)
        status = details['transaction']['transaction_status']
        return status

    async def preview_transaction(self, manifest: ret.ManifestBuilder | str) -> dict:
        if isinstance(manifest, ret.ManifestBuilder):
            manifest = manifest.build(self.network_id).instructions().as_str()
        body = {
            "manifest": manifest,
            "start_epoch_inclusive": 0,
            "end_epoch_exclusive": 1,
            "tip_percentage": 0,
            "nonce": self.random_nonce(),
            "signer_public_keys": [],
            "flags": {
                "use_free_credit": True,
                "assume_all_signature_proofs": True,
                "skip_epoch_check": True
            }
        }
        data = await self.post('transaction/preview', body)
        return data

    async def build_transaction(
            self,
            builder: ret.ManifestBuilder | str, 
            private_key: ret.PrivateKey,
            epochs_valid: int = 2
        ) -> Tuple[str, str]:

        public_key = private_key.public_key()
        ledger_state = await self.ledger_state()
        epoch = ledger_state['epoch']

        if isinstance(builder, ret.ManifestBuilder):
            manifest: ret.TransactionManifest = builder.build(self.network_id)
        else:
            manifest: ret.TransactionManifest = ret.TransactionManifest(ret.Instructions.from_string(builder, self.network_id), [])

        manifest.statically_validate()
        header: ret.TransactionHeader = ret.TransactionHeader(
            network_id=self.network_id,
            start_epoch_inclusive=epoch,
            end_epoch_exclusive=epoch + epochs_valid,
            nonce=self.random_nonce(),
            notary_public_key=public_key,
            notary_is_signatory=False,
            tip_percentage=0,
        )
        transaction: ret.NotarizedTransaction = (
            ret.TransactionBuilder()
                .header(header)
                .manifest(manifest)
                .sign_with_private_key(private_key)
                .notarize_with_private_key(private_key)
        )
        intent = transaction.intent_hash().as_str()
        payload = bytearray(transaction.compile()).hex()
        return payload, intent
    
    async def build_publish_transaction(
        self,
        account: str,
        code: bytes,
        definition: bytes,
        owner_role: ret.OwnerRole,
        public_key: ret.PublicKey,
        private_key: ret.PrivateKey,
        metadata: dict = {},
        epochs_valid: int = 2
    ) -> Tuple[str, str]:
        
        ledger_state = await self.ledger_state()
        epoch = ledger_state['epoch']

        manifest: ret.TransactionManifest = (
            ret.ManifestBuilder().account_lock_fee(account, ret.Decimal('500'))
            .package_publish_advanced(
                owner_role=owner_role,
                code=code,
                definition=definition,
                metadata=metadata,
                package_address=None,
            )
            .build(self.network_id)
        )
        manifest.statically_validate()
        header: ret.TransactionHeader = ret.TransactionHeader(
            network_id=self.network_id,
            start_epoch_inclusive=epoch,
            end_epoch_exclusive=epoch + epochs_valid,
            nonce=self.random_nonce(),
            notary_public_key=public_key,
            notary_is_signatory=False,
            tip_percentage=0,
        )
        transaction: ret.NotarizedTransaction = (
            ret.TransactionBuilder()
                .header(header)
                .manifest(manifest)
                .sign_with_private_key(private_key)
                .notarize_with_private_key(private_key)
        )
        intent = transaction.intent_hash().as_str()
        payload = bytearray(transaction.compile()).hex()
        return payload, intent
