"""
Utility functions for API key management and configuration.
"""

from typing import Optional
from loguru import logger
from fastapi import WebSocket
from foundation_voice.utils.transport.sip_detection import SIPDetector
from foundation_voice.utils.transport.transport import TransportType


def _raise_missing_api_key(provider_name: str, key_name: str):
    """
    Raises a ValueError indicating a missing API key for a specific provider.

    Args:
        provider_name: The name of the provider (e.g., "OpenAI", "Cerebras").
        key_name: The name of the environment variable for the API key (e.g., "OPENAI_API_KEY").
    """
    raise ValueError(
        f"Missing API key for {provider_name} provider. "
        f"Please set the {key_name} environment variable or provide 'api_key' in the configuration."
    )


async def auto_detect_transport(
    websocket: WebSocket,
) -> tuple[TransportType, Optional[dict]]:
    """Auto-detect transport type with simplified logic"""
    query_params = dict(websocket.query_params)

    # 1. Check for explicit transport type
    explicit_transport = query_params.get("transport_type", "").lower()
    if explicit_transport in ["websocket", "webrtc", "daily"]:
        return TransportType(explicit_transport), None

    # 2. Try SIP detection (simple pattern-based approach)
    client_ip = websocket.client.host if websocket.client else "unknown"
    headers = dict(websocket.headers) if hasattr(websocket, "headers") else {}

    if SIPDetector.detect_sip_connection(client_ip, headers, query_params):
        sip_params = await SIPDetector.handle_sip_handshake(websocket)
        if sip_params:
            return TransportType.SIP, sip_params
        logger.debug("SIP detection failed, falling back to WebSocket")

    # 3. Default to WebSocket
    return TransportType.WEBSOCKET, None
