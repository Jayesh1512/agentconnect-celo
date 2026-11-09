"""
x402 buyer helpers: let an agent pay HTTP 402 endpoints with its Celo wallet.

The agent signs a stablecoin (EIP-3009) authorization; the seller's x402 server
settles it through a facilitator such as https://x402.celo.org, which pays the gas.
Requires: ``pip install "x402[requests,evm]"``.
"""

import json
import logging
from typing import Any, Optional

from agentconnect.config import settings as global_settings

logger = logging.getLogger(__name__)

_V1_NETWORK = {"42220": "celo", "11142220": "celo-sepolia"}


def create_x402_session(account: Any, chain_id: Optional[str] = None, max_amount: Optional[str] = None):
    """
    Build a ``requests.Session`` that automatically pays 402 responses.

    Args:
        account: eth_account ``LocalAccount`` that signs the payments (the agent wallet).
        chain_id: EVM chain id (defaults to ``payments.chain_id``).
        max_amount: Per-payment USD cap, e.g. ``"$0.50"`` (defaults to
            ``payments.x402_max_amount_per_payment``). Anything above is refused
            before signing.
    """
    import requests
    from x402 import SchemeRegistration, x402ClientConfig
    from x402.http.clients import wrapRequestsWithPaymentFromConfig
    from x402.mechanisms.evm.exact import ExactEvmClientScheme
    from x402.mechanisms.evm.exact.v1 import ExactEvmSchemeV1Client

    payments = global_settings.payments
    chain_id = chain_id or payments.chain_id
    config = x402ClientConfig(
        schemes=[
            SchemeRegistration(
                network=f"eip155:{chain_id}", client=ExactEvmClientScheme(account)
            ),
            # x402 v1 servers (e.g. the buy gateway) name the network "celo"
            SchemeRegistration(
                network=_V1_NETWORK[chain_id],
                client=ExactEvmSchemeV1Client(account),
                x402_version=1,
            ),
        ],
        spend_controls={
            "max_amount_per_payment": max_amount or payments.x402_max_amount_per_payment
        },
    )
    return wrapRequestsWithPaymentFromConfig(requests.Session(), config)


def build_x402_tool(account: Any):
    """Return a LangChain tool that GETs a URL and pays if it answers 402."""
    from langchain_core.tools import StructuredTool

    session = create_x402_session(account)

    def pay_for_x402_resource(url: str) -> str:
        """GET `url`; if it requires an x402 payment, pay it from the agent wallet and return the response."""
        resp = session.get(url, timeout=60)
        receipt = resp.headers.get("payment-response")
        return json.dumps(
            {"status": resp.status_code, "payment_response": receipt, "body": resp.text[:4000]}
        )

    return StructuredTool.from_function(
        pay_for_x402_resource, name="pay_for_x402_resource"
    )
