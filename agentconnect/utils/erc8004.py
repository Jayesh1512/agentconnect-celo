"""
ERC-8004 agent identity on Celo: build a registration file and register it from the
agent wallet. The wallet that sends ``register()`` owns the identity NFT.
Docs: https://docs.celo.org/build-on-celo/build-with-ai/8004
"""

import base64
import json
from typing import Any, Dict, List, Optional

# Identity Registry, Celo mainnet
IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"

_ABI = [
    {"type": "function", "name": "register", "stateMutability": "nonpayable",
     "inputs": [{"name": "agentURI", "type": "string"}],
     "outputs": [{"name": "agentId", "type": "uint256"}]},
    {"type": "event", "name": "Registered", "anonymous": False,
     "inputs": [{"name": "agentId", "type": "uint256", "indexed": True},
                {"name": "agentURI", "type": "string", "indexed": False},
                {"name": "owner", "type": "address", "indexed": True}]},
]


def build_agent_card(
    name: str,
    description: str,
    services: Optional[List[Dict[str, str]]] = None,
    x402_support: bool = False,
) -> Dict[str, Any]:
    """Registration file (JSON) listing the agent's service endpoints."""
    return {
        "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
        "name": name,
        "description": description,
        "services": services or [],
        "x402Support": x402_support,
        "active": True,
        "supportedTrust": ["reputation"],
    }


def card_to_data_uri(card: Dict[str, Any]) -> str:
    """Store the card on-chain as a ``data:`` URI (no hosting needed)."""
    raw = json.dumps(card, separators=(",", ":")).encode()
    return "data:application/json;base64," + base64.b64encode(raw).decode()


def register_agent(wallet_provider: Any, agent_uri: str, registry: str = IDENTITY_REGISTRY) -> int:
    """
    Register an agent identity from ``wallet_provider`` (an AgentKit EVM wallet provider)
    and return the new agent id, read from the ``Registered`` event on the receipt.
    """
    from web3 import Web3

    contract = wallet_provider.web3.eth.contract(address=Web3.to_checksum_address(registry), abi=_ABI)
    tx_hash = wallet_provider.send_transaction(
        {"to": contract.address, "data": contract.encode_abi("register", args=[agent_uri])}
    )
    receipt = wallet_provider.wait_for_transaction_receipt(tx_hash)
    if receipt["status"] != 1:
        raise RuntimeError(f"ERC-8004 registration reverted: {tx_hash}")
    events = contract.events.Registered().process_receipt(receipt)
    return int(events[0]["args"]["agentId"])
