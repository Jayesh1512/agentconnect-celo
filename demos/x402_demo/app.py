"""
x402 payment demo UI: chat with a real AIAgent (payments enabled) that pays x402
endpoints from its own Celo wallet. Run from the repo root:

    pip install fastapi uvicorn "x402[requests,evm,extensions]"
    OPENAI_API_KEY=... uvicorn demos.x402_demo.app:app --port 8765
"""

import base64
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from web3 import Web3

load_dotenv()

import agentconnect.utils.x402_client as x402_client  # noqa: E402
from agentconnect.agents import AIAgent  # noqa: E402
from agentconnect.config import settings  # noqa: E402
from agentconnect.core.types import (  # noqa: E402
    AgentIdentity,
    AgentProfile,
    AgentType,
    Capability,
    ModelName,
    ModelProvider,
)

EVENTS: list = []
TOKENS = {
    "USDC": "0xcebA9300f2b948710d2653dD7B07f33A8B32118C",
    "USAT": "0xD2ab3C9A02DBBAB236BfEC45D1d755DF4267F771",
}


def emit(kind: str, **data) -> None:
    EVENTS.append({"n": len(EVENTS), "t": time.time(), "kind": kind, **data})


# Trace the agent's x402 tool so the UI can show each call and its settlement.
_build = x402_client.build_x402_tool


def _traced_build(account):
    tool = _build(account)
    inner = tool.func

    def pay_for_x402_resource(url: str) -> str:
        """GET `url`; if it requires an x402 payment, pay it from the agent wallet and return the response."""
        emit("tool_call", tool="pay_for_x402_resource", url=url)
        out = inner(url)
        res = json.loads(out)
        receipt = res.get("payment_response")
        tx = None
        if receipt:
            try:
                tx = json.loads(base64.b64decode(receipt)).get("transaction")
            except Exception:  # receipt format varies across x402 versions
                tx = None
        emit("tool_result", status=res.get("status"), tx=tx, body=res.get("body", "")[:300])
        return out

    from langchain_core.tools import StructuredTool

    return StructuredTool.from_function(
        pay_for_x402_resource, name="pay_for_x402_resource"
    )


x402_client.build_x402_tool = _traced_build

agent = AIAgent(
    agent_id="agentconnect",
    identity=AgentIdentity.create_key_based(),
    provider_type=ModelProvider.OPENAI,
    model_name=ModelName.GPT4O_MINI,
    api_key=os.environ["OPENAI_API_KEY"],
    profile=AgentProfile(
        agent_id="agentconnect",
        agent_type=AgentType.AI,
        name="AgentConnect",
        summary="Agent that pays for web services over x402 on Celo",
        description="Pays x402 (HTTP 402) endpoints from its own Celo wallet.",
        capabilities=[
            Capability(
                name="pay_x402",
                description="Call paid HTTP APIs and pay them over x402",
                input_schema={"query": "string"},
                output_schema={"response": "string"},
            )
        ],
    ),
    personality=(
        "You are a payments-capable agent. For questions that need a paid API, call "
        "pay_for_x402_resource with the URL, then answer concisely from the response and "
        "state what you paid. Never pay more than the configured cap."
    ),
    enable_payments=True,
)

app = FastAPI()

if os.getenv("X402_SELLER") == "1":  # sell a USAT-priced route through the Celo facilitator
    from agentconnect.utils.x402_seller import build_routes, create_x402_paywall, pay_to_address

    _pay_to = pay_to_address(agent.wallet_provider.get_address())
    app.middleware("http")(
        create_x402_paywall(
            build_routes("/api/x402/rates", "10000", _pay_to, description="Agent-sold data, 0.01 USAT")
        )
    )

    @app.get("/api/x402/rates")
    def paid_rates():
        return {"message": "paid with x402 on Celo", "pay_to": _pay_to}


class Chat(BaseModel):
    query: str


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/api/status")
def status():
    w3 = agent.wallet_provider.web3
    addr = agent.wallet_provider.get_address()
    abi = [{"name": "balanceOf", "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}],
            "stateMutability": "view", "type": "function"}]
    bal = {"CELO": float(Web3.from_wei(w3.eth.get_balance(addr), "ether"))}
    for sym, a in TOKENS.items():
        bal[sym] = w3.eth.contract(address=Web3.to_checksum_address(a), abi=abi).functions.balanceOf(addr).call() / 1e6
    return {
        "address": addr, "chain_id": settings.payments.chain_id,
        "cap": settings.payments.x402_max_amount_per_payment,
        "tag": x402_client.code_from_data_suffix(settings.payments.attribution_data_suffix),
        "pay_to": settings.payments.x402_pay_to or addr,
        "seller_asset": settings.payments.x402_seller_asset,
        "erc8004_agent_id": settings.payments.erc8004_agent_id,
        "balances": bal,
    }


@app.get("/api/events")
def events(since: int = 0):
    return EVENTS[since:]


@app.post("/api/chat")
async def chat(c: Chat):
    emit("user", text=c.query)
    emit("thinking")
    try:
        answer = await agent.chat(c.query)
    except Exception as e:  # surface failures in the UI instead of hanging it
        emit("error", text=str(e)[:300])
        return {"answer": f"Error: {e}"}
    emit("answer", text=answer)
    return {"answer": answer}
