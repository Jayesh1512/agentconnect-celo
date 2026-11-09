Agent Payments
================

.. _agent_payment:

AgentConnect integrates `Coinbase AgentKit <https://docs.cdp.coinbase.com/agentkit/docs/welcome>`_
so agents can pay each other on-chain for services, no manual wallet code, no manual
transaction logic. One constructor flag gives an agent a wallet, a set of payment tools,
and a published payment address.

.. admonition:: At a glance
   :class: tip

   - ``enable_payments=True`` on ``AIAgent`` creates a wallet, adds payment tools, and
     publishes the agent's payment address for discovery.
   - Costs and payment instructions live in the agent's ``profile`` and ``personality``;
     the LLM decides when to charge or pay based on that context.
   - Wallets persist to disk between restarts. Same agent ID, same wallet.
   - Payments run on **Celo mainnet** by default (``payments.chain_id: "42220"``): local-key wallets,
     x402 buying and selling (USA₮ by default) through Celo's facilitator, an ERC-8004 identity,
     and an ERC-8021 attribution suffix on every transaction the agent sends.

Prerequisites
-----------------

The AgentKit packages (no API keys needed; each agent holds a local key on `Celo <https://celo.org>`_):

.. code-block:: bash

    pip install coinbase-agentkit coinbase-agentkit-langchain

Pick the chain in ``agentconnect.yaml`` (defaults to Celo mainnet):

.. code-block:: yaml

    payments:
      chain_id: "42220"                  # Celo mainnet (default)
      rpc_url: "https://forno.celo.org"
      # Celo Sepolia testnet: chain_id "11142220", rpc_url "https://forno.celo-sepolia.celo-testnet.org"
      # Celo mainnet: chain_id "42220", rpc_url "https://forno.celo.org"

Fund the agent's address (``agent.profile.payment_address``) with a little CELO for gas and
the stablecoin it will spend. These are real funds on mainnet: start with a few cents, or switch
to Celo Sepolia and use the `Celo faucet <https://faucet.celo.org>`_.

Enabling Payments
---------------------

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity

    agent = AIAgent(
        agent_id="service_provider",
        name="Research Provider",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key="your_openai_api_key",
        identity=AgentIdentity.create_key_based(),
        enable_payments=True,
    )

This one flag creates a Celo wallet for the agent (or loads an existing one for the same
``agent_id``), adds payment tools to its toolset, and writes the resulting wallet address
to ``agent.profile.payment_address``. Because ``payment_address`` lives on the profile,
it's included automatically wherever that profile is discovered, no separate step to
publish it.

.. admonition:: Missing packages fail silently
   :class: warning

   If ``enable_payments=True`` but AgentKit isn't installed, the agent builds
   successfully with payments disabled rather than raising. Check your logs for
   ``Payment capabilities disabled due to invalid CDP environment`` if payment tools
   seem to be missing.

Paying x402 Endpoints (Celo Facilitator)
--------------------------------------------

Agents with ``enable_payments=True`` also get a ``pay_for_x402_resource`` tool. It calls a
URL and, if the server answers ``402 Payment Required``, signs a stablecoin authorization
with the agent wallet and retries. The seller's x402 server settles it through a
facilitator such as ``https://x402.celo.org``, which pays the gas, so the agent needs no
CELO for these payments.

.. code-block:: bash

    pip install "x402[requests,evm,extensions]"

Each payment is capped by ``payments.x402_max_amount_per_payment`` (default ``$0.50``);
larger prices are refused before anything is signed. If
``payments.attribution_data_suffix`` is set, the buyer also attaches its ERC-8021 code to the
payment (builder-code extension). Because the facilitator submits the transaction, the tag
reaches the chain only when the seller declares the extension and the facilitator supports
it; x402 v1 servers have no extensions. The buyer side needs no facilitator
API key (the seller's server holds that). Start with small amounts.

Attribution (ERC-8021)
--------------------------

Set ``payments.attribution_data_suffix`` to the ERC-8021 suffix for your code (for example the
``celo.dataSuffix`` from Loops). Every transaction the agent sends itself (token transfers, native
transfers, swaps, ERC-8004 registration) then carries it. Check one transaction with
``verifyTx`` from ``@celo/attribution-tags``.

x402 payments are different: the *facilitator* submits those transactions, so the buyer's suffix
cannot be appended. The buyer attaches its code to the payment (builder-code extension), and it
reaches the chain only if the seller declares the extension and the facilitator supports it.

Selling over x402 (USA₮)
----------------------------

An agent can charge for a route and get paid into its own wallet:

.. code-block:: python

    from fastapi import FastAPI
    from agentconnect.utils.x402_seller import build_routes, create_x402_paywall, pay_to_address

    pay_to = pay_to_address(agent.wallet_provider.get_address())   # payments.x402_pay_to or the agent wallet
    routes = build_routes("/api/rates", "10000", pay_to)           # 0.01 USA₮ (6 decimals), payments.x402_seller_asset
    app = FastAPI()
    app.middleware("http")(create_x402_paywall(routes))

An unpaid request gets ``402`` with the price, asset and ``payTo``. Settlement goes through Celo's
hosted facilitator (``https://api.x402.celo.org`` on mainnet) and needs an ``X402_API_KEY``, which a
human creates at https://x402.celo.org. Without it the route still issues challenges and verifies
payments, but the facilitator rejects settlement. ``agentconnect/utils/celo_tokens.py`` holds the
supported tokens (USDC, USDT, USAT on mainnet; USDC on Celo Sepolia).

ERC-8004 identity
---------------------

``agentconnect.utils.erc8004`` registers the agent in the ERC-8004 Identity Registry on Celo from
the agent wallet (which then owns the identity NFT):

.. code-block:: python

    from agentconnect.utils import erc8004

    card = erc8004.build_agent_card("My agent", "What it does", [{"name": "web", "endpoint": "https://…"}])
    agent_id = erc8004.register_agent(agent.wallet_provider, erc8004.card_to_data_uri(card))

Record the returned id in ``payments.erc8004_agent_id``.

Configuring Wallets
-----------------------

Wallets are stored as JSON files named ``{agent_id}_wallet.json`` in a directory set by
``payments.wallet_data_dir`` in ``agentconnect.yaml``:

.. code-block:: yaml

    payments:
      default_token_symbol: "USDC"           # or "ETH" for native
      wallet_data_dir: "data/agent_wallets"

Override the directory per agent instead of globally:

.. code-block:: python

    agent = AIAgent(
        # ... other parameters ...
        enable_payments=True,
        wallet_data_dir="custom/wallet/directory",
    )

.. admonition:: Wallet data is unencrypted on disk
   :class: warning

   The default storage writes wallet private keys as plain JSON (file mode 0600). Fine for small balances and demos,
   not for production wallets holding real assets. Encrypt this data yourself before
   deploying with real funds.

Advertising and Charging for Services
-----------------------------------------

Two things make an agent a paid service provider: a capability description that states
the cost, and personality instructions telling the LLM when to ask for payment.

.. code-block:: python

    from agentconnect.core.types import AgentProfile, Capability, AgentType

    research_agent = AIAgent(
        agent_id="research_agent",
        # ... other parameters ...
        profile=AgentProfile(
            agent_id="research_agent",
            agent_type=AgentType.AI,
            name="Research Specialist",
            summary="Provides in-depth research services for 2 USDC per request",
            capabilities=[
                Capability(
                    name="research_service",
                    description="Conducts in-depth research on any topic for 2 USDC per request",
                ),
            ],
            tags=["research", "paid-service"],
            custom_metadata={"payment_info": {"cost": "2 USDC", "payment_token": "USDC"}},
        ),
        enable_payments=True,
        personality="""You are a Research Specialist that provides detailed research reports.

        PAYMENT INSTRUCTIONS:
        1. When a collaboration request comes in, state that your service costs 2 USDC.
        2. Wait for payment confirmation and verify the transaction hash.
        3. Only after confirmation, deliver the research.
        4. Thank the agent for their payment.
        """,
    )

The cost in ``summary``/``capabilities`` is what other agents see during discovery,
before they ever talk to this one. The personality is what makes the LLM actually enforce
payment during the conversation. Both are needed; a listed price with no enforcement
instructions is just a suggestion the LLM can ignore.

Making Payments
-------------------

On the paying side, personality instructions describe when to spend rather than when to
charge:

.. code-block:: python

    customer_agent = AIAgent(
        agent_id="customer_agent",
        # ... other parameters ...
        enable_payments=True,
        personality="""You are an agent that uses paid services when needed.

        When using services from other agents:
        1. Review the cost before agreeing to the service.
        2. Pay the requested amount using your payment tools.
        3. Keep track of transaction hashes for verification.
        4. Don't pay twice for the same service.
        """,
    )

Nothing here calls a payment function directly. The LLM reads the conversation, decides
a payment is warranted, and calls one of the tools below on its own.

Available Payment Tools
---------------------------

Added to the agent's toolset automatically when ``enable_payments=True``:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Tool
     - Source
     - Does
   * - ``get_wallet_details``
     - ``WalletActionProvider``
     - Address, network, and balances
   * - ``get_balance``
     - ``WalletActionProvider``
     - Native currency balance (CELO)
   * - ``native_transfer``
     - ``WalletActionProvider``
     - Transfers native currency
   * - ``pay_for_x402_resource``
     - ``agentconnect.utils.x402_client``
     - GETs a URL and, on HTTP 402, pays it over x402 (capped per payment)
   * - ``get_balance`` (ERC-20)
     - ``Erc20ActionProvider``
     - Balance of a specific token; added when the configured token isn't the native token (``CELO``)
   * - ``transfer`` (ERC-20)
     - ``Erc20ActionProvider``
     - Transfers a specific token amount

Verifying Readiness
-----------------------

.. code-block:: python

    from agentconnect.utils.payment_helper import check_agent_payment_readiness

    status = check_agent_payment_readiness(agent)
    if status["ready"]:
        print(f"Ready with address: {status['payment_address']}")
    else:
        print(status)   # inspect which flag is False

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Field
     - True means
   * - ``payments_enabled``
     - ``enable_payments=True`` was set
   * - ``wallet_provider_available``
     - The Celo wallet initialized successfully
   * - ``agent_kit_available``
     - AgentKit initialized successfully
   * - ``payment_address``
     - The wallet address was written to the agent's profile
   * - ``ready``
     - All of the above are true

Wallet Utilities
--------------------

.. code-block:: python

    from agentconnect.utils import wallet_manager
    from agentconnect.utils.payment_helper import backup_wallet_data

    wallet_manager.wallet_exists(agent.agent_id)             # already has a wallet?
    backup_wallet_data(agent.agent_id, backup_dir="wallet_backups")
    wallet_manager.delete_wallet_data(agent.agent_id)         # force a fresh wallet next start

Security Considerations
---------------------------

- **Unencrypted storage**: wallet private keys are plain JSON on disk (file mode 0600) by default. Encrypt before
  production use with real funds.
- **Wallet files**: keep ``wallet_data_dir`` out of version control.
- **Small balances**: mainnet is the default, so keep agent wallets lightly funded (or use Celo Sepolia while developing).
- **Access control**: anything that can construct an agent with ``enable_payments=True``
  can spend from that agent's wallet. Treat agent creation as a privileged action.

Troubleshooting
-------------------

- **Payment tools missing even though ``enable_payments=True``**: check your logs for
  ``Payment capabilities disabled due to invalid CDP environment``. This is the silent
  failure mode described above under Enabling Payments.
- **Confirming the payment environment directly**:

  .. code-block:: python

      from agentconnect.utils.payment_helper import validate_cdp_environment

      is_valid, message = validate_cdp_environment()
      if not is_valid:
          print(message)

- **Missing packages**: install ``coinbase-agentkit`` and
  ``coinbase-agentkit-langchain`` together; a partial install is the most common cause of
  import errors.
- **Corrupted wallet data**: delete it with ``wallet_manager.delete_wallet_data(agent_id)``
  and restart; a fresh wallet is created automatically.

.. admonition:: On the horizon
   :class: note

   Coinbase AgentKit is the first payment integration. Additional protocols are planned
   as agent-to-agent payment standards mature, without changing how ``enable_payments``
   works today.

Next Steps
-------------

- `Autonomous Workflow example <https://github.com/AKKI0511/AgentConnect/blob/main/examples/autonomous_workflow/run_workflow_demo.py>`_
  — a complete two-agent economy: a paid research provider and a paying coordinator
- :doc:`../core/agents/ai_agent` — ``enable_payments`` and ``wallet_data_dir`` alongside
  every other ``AIAgent`` parameter
- :doc:`../core/agent_profile_and_capabilities` — writing capability descriptions other
  agents can discover
