"""Stablecoins settleable through Celo's x402 facilitator (EIP-3009), per chain id."""

from typing import Dict, NamedTuple


class CeloToken(NamedTuple):
    symbol: str
    address: str
    decimals: int
    eip712_name: str  # EIP-712 domain name/version the seller must advertise
    eip712_version: str


CELO_TOKENS: Dict[str, Dict[str, CeloToken]] = {
    "42220": {  # Celo mainnet
        "USDC": CeloToken("USDC", "0xcebA9300f2b948710d2653dD7B07f33A8B32118C", 6, "USDC", "2"),
        "USDT": CeloToken("USDT", "0x48065fbBE25f71C9282ddf5e1cD6D6A887483D5e", 6, "Tether USD", "1"),
        "USAT": CeloToken("USAT", "0xD2ab3C9A02DBBAB236BfEC45D1d755DF4267F771", 6, "Tether America USD", "1"),
    },
    "11142220": {  # Celo Sepolia
        "USDC": CeloToken("USDC", "0x01C5C0122039549AD1493B8220cABEdD739BC44E", 6, "USDC", "2"),
    },
}


def get_token(chain_id: str, symbol: str) -> CeloToken:
    """Return the token for a chain, e.g. ``get_token("42220", "USAT")``."""
    try:
        return CELO_TOKENS[chain_id][symbol.upper()]
    except KeyError:
        raise ValueError(f"{symbol} is not available on chain {chain_id}") from None
