# Installation

### Prerequisites

- Python 3.11 or higher
- Poetry (Python package manager)

### Installing AgentConnect

AgentConnect is currently available from source only. Direct installation via pip will be available soon.

### Development Installation

Clone the repository and install dependencies using Poetry:

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
poetry install --with demo,dev  # For development (recommended)
# For production only:
# poetry install --without dev
```

### Environment Setup

Copy the environment template and configure your API keys:

```bash
copy example.env .env  # Windows
cp example.env .env    # Linux/Mac
```

Edit the `.env` file to set your provider and API keys:

```
DEFAULT_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
```

For monitoring and additional features, you can configure optional settings:

```
# LangSmith for monitoring (recommended)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=AgentConnect

# Additional providers
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_API_KEY=your_google_api_key
```

### Payment Capabilities (Optional)

AgentConnect supports agent-to-agent payments on [Celo](https://celo.org) via Coinbase AgentKit. No API keys are needed: each agent gets a local wallet. Set `payments.chain_id` / `payments.rpc_url` in `agentconnect.yaml` to choose the chain.

By default, payment features use Celo mainnet (real funds: keep agent wallets lightly funded). To develop on the Celo Sepolia testnet instead, set `payments.chain_id: "11142220"` and fund wallets from the [Celo faucet](https://faucet.celo.org).

