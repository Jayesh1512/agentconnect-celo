"""
Payment utility functions for AgentConnect.

This module provides helper functions for setting up payment capabilities in agents.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, Union, Tuple

from agentconnect.utils import wallet_manager

logger = logging.getLogger(__name__)


def append_data_suffix(transaction: Dict[str, Any], suffix: str) -> Dict[str, Any]:
    """
    Append an ERC-8021 attribution suffix to a transaction's calldata (in place).

    No-op when ``suffix`` is empty or the calldata already ends with it.
    """
    if not suffix:
        return transaction
    suffix_hex = suffix[2:] if suffix.startswith("0x") else suffix
    data = transaction.get("data") or "0x"
    data_hex = data.hex() if isinstance(data, (bytes, bytearray)) else data
    data_hex = data_hex[2:] if data_hex.startswith("0x") else data_hex
    if not data_hex.endswith(suffix_hex):
        transaction["data"] = "0x" + data_hex + suffix_hex
    return transaction


def code_from_data_suffix(suffix: str) -> str:
    """
    Extract the attribution code from an ERC-8021 Schema 0 suffix
    (``[code][length:1][schema:1][marker:16]``). Returns "" if it can't be decoded.
    """
    try:
        raw = bytes.fromhex(suffix[2:] if suffix.startswith("0x") else suffix)
        body, length = raw[:-18], raw[-18]
        return body[-length:].decode() if raw[-17] == 0 and length else ""
    except (ValueError, IndexError):
        return ""


def verify_payment_environment() -> bool:
    """
    Verify that the environment is ready for payments.

    Payments use a local key wallet on Celo, so no API keys are required.

    Returns:
        Always True (kept for backward compatibility)
    """
    return True


def validate_cdp_environment() -> Tuple[bool, str]:
    """
    Validate that the payment packages (AgentKit) are installed.

    The name is kept for backward compatibility; Coinbase CDP keys are no
    longer used.

    Returns:
        Tuple of (valid: bool, message: str)
    """
    try:
        import coinbase_agentkit  # noqa: F401
    except ImportError:
        return (
            False,
            "AgentKit not installed. Install it with: pip install coinbase-agentkit",
        )

    try:
        import coinbase_agentkit_langchain  # noqa: F401
    except ImportError:
        return (
            False,
            "AgentKit LangChain integration not installed. Install it with: pip install coinbase-agentkit-langchain",
        )

    return True, "Payment environment is properly configured"


def get_wallet_metadata(
    agent_id: str, wallet_data_dir: Optional[Union[str, Path]] = None
) -> Optional[Dict[str, Any]]:
    """
    Get wallet metadata for an agent if it exists.

    Args:
        agent_id: The ID of the agent
        wallet_data_dir: Optional custom directory for wallet data storage

    Returns:
        Dictionary with wallet metadata if it exists, None otherwise
    """
    if not wallet_manager.wallet_exists(agent_id, wallet_data_dir):
        return None

    try:
        wallet_json = wallet_manager.load_wallet_data(agent_id, wallet_data_dir)
        if not wallet_json:
            logger.warning("Invalid wallet data found for agent %s", agent_id)
            return None

        # Parse the JSON into a dictionary
        wallet_data = json.loads(wallet_json)

        # Extract relevant metadata
        metadata = {
            "chain_id": wallet_data.get("chain_id", "Unknown"),
            "has_private_key": "private_key" in wallet_data,
        }

        # Don't include sensitive data like the private key
        return metadata
    except Exception:
        logger.error(
            "Error retrieving wallet metadata for agent %s", agent_id, exc_info=True
        )
        return None


def backup_wallet_data(
    agent_id: str,
    data_dir: Optional[Union[str, Path]] = None,
    backup_dir: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    """
    Create a backup of wallet data for an agent.

    Args:
        agent_id: The ID of the agent
        data_dir: Optional custom directory for wallet data storage
        backup_dir: Optional directory for storing backups
                   If None, creates a backup directory under data_dir

    Returns:
        Path to the backup file if successful, None otherwise
    """
    if not wallet_manager.wallet_exists(agent_id, data_dir):
        logger.warning("No wallet data found for agent %s to backup", agent_id)
        return None

    try:
        # Determine the source directory and file
        data_dir_path = Path(data_dir) if data_dir else wallet_manager.DEFAULT_DATA_DIR
        source_file = data_dir_path / f"{agent_id}_wallet.json"

        # Determine the backup directory
        if backup_dir:
            backup_dir_path = Path(backup_dir)
        else:
            backup_dir_path = data_dir_path / "backups"

        # Create backup directory if it doesn't exist
        backup_dir_path.mkdir(parents=True, exist_ok=True)

        # Create a timestamped filename for the backup
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_file = backup_dir_path / f"{agent_id}_wallet_{timestamp}.json"

        # Read the original wallet data
        with open(source_file, "r") as f:
            wallet_data = f.read()

        # Write to the backup file
        with open(backup_file, "w") as f:
            f.write(wallet_data)

        return str(backup_file)
    except Exception:
        logger.error(
            "Error backing up wallet data for agent %s", agent_id, exc_info=True
        )
        return None


def check_agent_payment_readiness(agent) -> Dict[str, Any]:
    """
    Check if an agent is ready for payments.

    Args:
        agent: The agent to check

    Returns:
        A dictionary with status information
    """
    status = {
        "payments_enabled": getattr(agent, "enable_payments", False),
        "wallet_provider_available": hasattr(agent, "wallet_provider")
        and agent.wallet_provider is not None,
        "agent_kit_available": hasattr(agent, "agent_kit")
        and agent.agent_kit is not None,
        "payment_address": (
            getattr(agent.profile, "payment_address", None)
            if hasattr(agent, "profile")
            else None
        ),
        "ready": False,
    }

    # Check overall readiness
    status["ready"] = (
        status["payments_enabled"]
        and status["wallet_provider_available"]
        and status["agent_kit_available"]
        and status["payment_address"] is not None
    )
    return status
