"""
x402 seller: charge for an API route in a Celo stablecoin (default USA₮), settled
through Celo's hosted facilitator (https://x402.celo.org).

The route's ``payTo`` is the agent's own wallet. Settlement needs a facilitator API
key (``X402_API_KEY``); without it the route still answers 402 challenges and
verifies payments, but settlement is rejected by the facilitator.
Requires: ``pip install "x402[fastapi,evm,extensions]"``.
"""

import logging
import os
from typing import Any, Optional

from agentconnect.config import settings as global_settings
from agentconnect.utils.celo_tokens import get_token
from agentconnect.utils.payment_helper import code_from_data_suffix

logger = logging.getLogger(__name__)

FACILITATOR_URLS = {
    "42220": "https://api.x402.celo.org",
    "11142220": "https://api.x402.sepolia.celo.org",
}


def pay_to_address(wallet_address: Optional[str] = None) -> str:
    """The address buyers pay: ``payments.x402_pay_to`` or, by default, the agent wallet."""
    pay_to = global_settings.payments.x402_pay_to or wallet_address
    if not pay_to:
        raise ValueError("No payTo address: set payments.x402_pay_to or pass the agent wallet")
    return pay_to


def build_routes(
    path: str,
    amount_atomic: str,
    pay_to: str,
    description: str = "",
    symbol: Optional[str] = None,
    chain_id: Optional[str] = None,
) -> dict:
    """Route config charging ``amount_atomic`` (token base units) for ``GET path``."""
    payments = global_settings.payments
    chain_id = chain_id or payments.chain_id
    token = get_token(chain_id, symbol or payments.x402_seller_asset)
    route: dict[str, Any] = {
        "accepts": {
            "scheme": "exact",
            "payTo": pay_to,
            "network": f"eip155:{chain_id}",
            "price": {
                "amount": amount_atomic,
                "asset": token.address,
                "extra": {"name": token.eip712_name, "version": token.eip712_version},
            },
        },
        "description": description,
        "mime_type": "application/json",
    }
    code = code_from_data_suffix(payments.attribution_data_suffix)
    if code:  # attribution: declare our app code for the ERC-8021 builder-code extension
        from x402.extensions.builder_code import (
            BUILDER_CODE,
            declare_builder_code_extension,
        )

        route["extensions"] = {BUILDER_CODE: declare_builder_code_extension(code)}
    return {f"GET {path}": route}


class _ApiKeyAuth:
    """Sends the Celo facilitator API key on every facilitator call."""

    def __init__(self, api_key: str) -> None:
        self._h = {"X-API-Key": api_key}

    def get_auth_headers(self):
        from x402.http.facilitator_client_base import AuthHeaders

        return AuthHeaders(verify=self._h, settle=self._h, supported=self._h)


def create_x402_paywall(
    routes: dict,
    chain_id: Optional[str] = None,
    api_key: Optional[str] = None,
    facilitator_url: Optional[str] = None,
    sync_facilitator_on_start: bool = True,
):
    """
    Build a FastAPI middleware that protects ``routes`` with x402 via the Celo facilitator.

    Usage: ``app.middleware("http")(create_x402_paywall(routes))``.
    """
    from x402 import x402ResourceServer
    from x402.http import FacilitatorConfig, HTTPFacilitatorClient
    from x402.http.middleware.fastapi import payment_middleware
    from x402.mechanisms.evm.exact import ExactEvmServerScheme

    chain_id = chain_id or global_settings.payments.chain_id
    api_key = api_key or os.getenv("X402_API_KEY")
    if not api_key:
        logger.warning(
            "X402_API_KEY not set: 402 challenges and verification work, but the Celo "
            "facilitator will reject settlement."
        )
    url = facilitator_url or FACILITATOR_URLS[chain_id]
    facilitator = HTTPFacilitatorClient(
        FacilitatorConfig(url=url, auth_provider=_ApiKeyAuth(api_key) if api_key else None)
    )
    server = x402ResourceServer(facilitator)
    server.register(f"eip155:{chain_id}", ExactEvmServerScheme())
    return payment_middleware(routes, server, sync_facilitator_on_start=sync_facilitator_on_start)
