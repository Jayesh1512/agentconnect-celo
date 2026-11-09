# AgentConnect on Celo — Agents on Open Rails entry

Agents that discover each other and **pay web services over x402 on Celo mainnet**, from their own wallet, with a hard per-payment cap.
Fork of [AKKI0511/AgentConnect](https://github.com/AKKI0511/AgentConnect); this repo moves its payments from Coinbase CDP wallets on Base to local-key wallets on Celo.

- **Live site:** https://agentconnect-celo.vercel.app (static, read-only; source in `site/`, the video file is hosted there but not committed)
- **Agent wallet (Celo mainnet):** [`0x1bBd102f47a02c3604C433B999Ef867A89b7899F`](https://celoscan.io/address/0x1bBd102f47a02c3604C433B999Ef867A89b7899F)
- **ERC-8004 identity:** [agent #10067](https://8004scan.io/agents/celo/10067)
- **Attribution tag:** `celo_7fc842cb4087`

## What is live on mainnet

Checked with `verifyTx` from `@celo/attribution-tags`.

| What | Transaction | Tag |
|---|---|---|
| 0.01 USDC self-transfer via the AgentKit wallet provider | [`0x25b5…ed6a`](https://celoscan.io/tx/0x25b5cda00ad590f5441901700eebc528beb40d52293e1059d918147f4090ed6a) | ✅ `celo_7fc842cb4087` |
| ERC-8004 identity registration (agent #10067) | [`0xa1b8…af7e`](https://celoscan.io/tx/0xa1b8472cb9362c15367f26b5ac96f64c77fb87d9c524957a86e3069c44d0af7e) | ✅ |
| 0.10 USDC → USA₮ swap (Uniswap v3, USDC→USDT→USAT) | [`0xb2f0…dce0`](https://celoscan.io/tx/0xb2f032417735b9d3adaf06c947cae6f53f9c34c3afa066fba367176834c4dce0) | ✅ |
| x402 payment to the buy gateway (VM service), 0.016753 **USDC**, HTTP 200 | [`0x58fb…e8e7`](https://celoscan.io/tx/0x58fbe13c459eebaf0cbc223c8da921debd172f9648ce1174d9ea123ac64fe8e7) | ❌ |
| x402 payment to the buy gateway (VM service), 0.016753 **USA₮**, HTTP 200 | [`0x1cc8…20ea`](https://celoscan.io/tx/0x1cc83ef179927ca7a87678c155c7c252b2e4b112014bb604fef2306b886120ea) | ❌ |

The paid calls come from the tagged wallet (it is the payer on both x402 settlements). The tag itself is **not** on the two x402 settlements:
the Celo facilitator (`0x0d74…FB48`, the signer listed by `https://api.x402.celo.org/supported`) submits those transactions, and the buy gateway speaks x402 v1, which has no extensions.

## What was built

- **Celo payments** (`agentconnect/core/agent.py`): each agent holds a local key wallet (`EthAccountWalletProvider`) on the chain set in `payments.chain_id` / `payments.rpc_url`. Key files are mode 0600.
- **Attribution** (`payments.attribution_data_suffix`): an ERC-8021 suffix is appended to every transaction the agent sends.
- **x402 buyer** (`agentconnect/utils/x402_client.py`): the `pay_for_x402_resource` agent tool signs a stablecoin authorization on a `402`, supports x402 v1 and v2, lets the agent choose which offered token to pay with, caps each payment (`payments.x402_max_amount_per_payment`, default `$0.50`; larger prices are refused before anything is signed), and attaches the ERC-8021 builder-code extension for v2 sellers that declare it.
- **Demo UI** (`demos/x402_demo/`): a chat page around a real `AIAgent` with payments enabled, showing wallet balances, the cap, the tag and a live payment timeline with Celoscan links.

## Run it

```bash
pip install fastapi uvicorn "x402[requests,evm,extensions]"   # plus the project's dependencies
# agentconnect.yaml
#   payments: {chain_id: "42220", rpc_url: "https://forno.celo.org", attribution_data_suffix: "0x…"}
OPENAI_API_KEY=... uvicorn demos.x402_demo.app:app --port 8765
```

Fund the agent wallet with a little CELO (gas) and USDC/USA₮ first. Do not expose the demo app publicly: it spends from a real wallet.

## Seller side (USA₮ via the Celo facilitator)

`agentconnect/utils/x402_seller.py` protects a FastAPI route with x402, priced in **USA₮** by default (`payments.x402_seller_asset`), with `payTo` set to the agent wallet (`payments.x402_pay_to`, default = the agent's own address, [`0x1bBd…899F`](https://celoscan.io/address/0x1bBd102f47a02c3604C433B999Ef867A89b7899F)) and our attribution code declared as the app code (ERC-8021 builder-code extension). Token addresses and EIP-712 domains are in `agentconnect/utils/celo_tokens.py`.

Verified against the live Celo mainnet facilitator (`https://api.x402.celo.org`): an unpaid request returns `402` for USA₮ → `payTo` = the agent wallet, and a payment from an unfunded buyer reaches the facilitator's `/verify` and is correctly rejected (`insufficient_funds`).
**Settlement requires an `X402_API_KEY`** (a human creates it at x402.celo.org), which we did not have, so no USA₮ has been received yet.

## ERC-8004 tooling

`agentconnect/utils/erc8004.py` builds the registration file, stores it on-chain as a `data:` URI, and registers it from the agent wallet (`register_agent`), reading the agent id from the `Registered` event. Agent #10067 was registered from the agent wallet (a one-off script using the same registry call); the id is recorded in `agentconnect.yaml` (`payments.erc8004_agent_id`).

## Defaults

`agentconnect.yaml` is committed: Celo **mainnet** (`42220`, `https://forno.celo.org`), the attribution suffix **turned on**, USA₮ as the seller asset, the $0.50 buyer cap. The library defaults are mainnet too.

## What is not done

- **No settled sale yet.** Without a facilitator API key there is no independent payer, no repeat counterparty, and no USA₮ received. The USA₮ settlement above is an *outbound* payment.
- **x402 settlements are not tagged** (see above); only the direct transactions are.
- **No named end user** yet; the demo task is a generic "pay a third-party rates API".
- Tests: `tests/config`, `tests/utils` (new offline tests for attribution, token registry, seller routes, buyer cap, builder-code) and `tests/imports` pass (26) except `test_lazy_submodule_access_core`, which also fails on the unmodified upstream code. The rest of the suite was not run. The seller was exercised against the live Celo mainnet facilitator's challenge/verify only, not settlement.
