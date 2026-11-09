"""Offline tests for the Celo payment helpers: attribution, x402 buyer/seller, ERC-8004."""

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agentconnect.utils import erc8004
from agentconnect.utils.celo_tokens import get_token
from agentconnect.utils.payment_helper import append_data_suffix, code_from_data_suffix

SUFFIX = "0x63656c6f5f376663383432636234303837110080218021802180218021802180218021"
USAT = "0xD2ab3C9A02DBBAB236BfEC45D1d755DF4267F771"


def test_code_from_data_suffix():
    assert code_from_data_suffix(SUFFIX) == "celo_7fc842cb4087"
    assert code_from_data_suffix("") == ""


def test_append_data_suffix_is_idempotent_and_handles_bytes():
    erc20 = "0xa9059cbb" + "00" * 64
    assert append_data_suffix({"data": erc20}, SUFFIX)["data"] == erc20 + SUFFIX[2:]
    assert append_data_suffix({"data": bytes.fromhex(erc20[2:])}, SUFFIX)["data"] == erc20 + SUFFIX[2:]
    assert append_data_suffix({"data": erc20 + SUFFIX[2:]}, SUFFIX)["data"] == erc20 + SUFFIX[2:]
    assert append_data_suffix({"to": "0x1"}, SUFFIX)["data"] == SUFFIX  # native transfer
    assert "data" not in append_data_suffix({"to": "0x1"}, "")


def test_celo_tokens_include_usat_on_mainnet():
    t = get_token("42220", "usat")
    assert t.address == USAT and t.decimals == 6 and t.eip712_name == "Tether America USD"
    with pytest.raises(ValueError):
        get_token("11142220", "USAT")  # not on testnet


def test_seller_routes_charge_usat_to_pay_to():
    from agentconnect.utils.x402_seller import build_routes, pay_to_address

    pay_to = pay_to_address("0x1bBd102f47a02c3604C433B999Ef867A89b7899F")
    routes = build_routes("/rates", "10000", pay_to, chain_id="42220", symbol="USAT")
    acc = routes["GET /rates"]["accepts"]
    assert acc["payTo"] == pay_to and acc["network"] == "eip155:42220"
    assert acc["price"]["asset"] == USAT and acc["price"]["amount"] == "10000"
    assert "builder-code" in routes["GET /rates"].get("extensions", {})  # tag declared when configured


def test_erc8004_card_and_data_uri():
    card = erc8004.build_agent_card("AgentConnect", "d", [{"name": "web", "endpoint": "https://x"}])
    uri = erc8004.card_to_data_uri(card)
    assert uri.startswith("data:application/json;base64,")
    assert json.loads(base64.b64decode(uri.split(",", 1)[1])) == card
    assert card["type"].endswith("eip-8004#registration-v1") and card["x402Support"] is False


def test_x402_buyer_pays_v2_seller_with_cap_and_builder_code():
    pytest.importorskip("x402")
    from eth_account import Account
    from x402.extensions.builder_code import BUILDER_CODE, declare_builder_code_extension

    from agentconnect.config import settings
    from agentconnect.utils.x402_client import create_x402_session

    pay_to = Account.create().address
    asset = get_token("42220", "USAT")
    seen = {}

    def reqs(amount):
        return {"scheme": "exact", "network": "eip155:42220", "asset": asset.address, "amount": amount,
                "payTo": pay_to, "maxTimeoutSeconds": 300,
                "extra": {"name": asset.eip712_name, "version": asset.eip712_version}}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            amount = "10000" if self.path == "/cheap" else "5000000"
            sig = self.headers.get("PAYMENT-SIGNATURE")
            if not sig:
                pr = {"x402Version": 2, "error": "payment required",
                      "resource": {"url": "http://x" + self.path, "description": "t", "mimeType": "application/json"},
                      "accepts": [reqs(amount)],
                      "extensions": {BUILDER_CODE: declare_builder_code_extension("celo_appcode1")}}
                self.send_response(402)
                self.send_header("PAYMENT-REQUIRED", base64.b64encode(json.dumps(pr).encode()).decode())
                self.send_header("content-length", "2")
                self.end_headers()
                self.wfile.write(b"{}")
                return
            seen["payload"] = json.loads(base64.b64decode(sig))
            self.send_response(200)
            self.send_header("content-length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    buyer = Account.create()
    session = create_x402_session(buyer, chain_id="42220", prefer_asset=asset.address)

    assert session.get(base + "/cheap", timeout=30).status_code == 200
    auth = seen["payload"]["payload"]["authorization"]
    assert auth["from"] == buyer.address and auth["to"] == pay_to and auth["value"] == "10000"
    code = code_from_data_suffix(settings.payments.attribution_data_suffix)
    if code:  # committed agentconnect.yaml turns the tag on
        assert seen["payload"]["extensions"][BUILDER_CODE]["info"]["s"] == [code]

    seen.clear()
    with pytest.raises(Exception, match="spend_controls"):  # $5 > $0.50 cap: refused before signing
        session.get(base + "/expensive", timeout=30)
    assert "payload" not in seen
    srv.shutdown()
